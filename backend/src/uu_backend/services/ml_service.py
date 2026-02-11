"""ML service for local label prediction using LightGBM."""

import logging
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer

from uu_backend.config import get_settings
from uu_backend.models.feedback import TrainingResult, TrainingStatus
from uu_backend.repositories import get_repository

logger = logging.getLogger(__name__)


class MLService:
    """Service for embedding generation, model training, and predictions."""

    MIN_SAMPLES = 20  # Minimum samples before training
    RETRAIN_THRESHOLD = 10  # Retrain after this many new feedback items

    def __init__(self):
        self.settings = get_settings()
        self.model_dir = Path(self.settings.file_storage_directory).parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "label_classifier.pkl"
        self.label_encoder_path = self.model_dir / "label_encoder.pkl"

        # Lazy-load the embedding model
        self._embedding_model: Optional[SentenceTransformer] = None
        self._classifier = None
        self._label_encoder = None
        self._labels_list: list[str] = []

        # Load existing model if available
        self._load_model()

    @property
    def embedding_model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._embedding_model is None:
            logger.info("Loading sentence transformer model...")
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence transformer loaded.")
        return self._embedding_model

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a text string."""
        embedding = self.embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        return self.embedding_model.encode(texts, convert_to_numpy=True)

    def _load_model(self) -> bool:
        """Load trained model from disk if available."""
        if self.model_path.exists() and self.label_encoder_path.exists():
            try:
                self._classifier = joblib.load(self.model_path)
                encoder_data = joblib.load(self.label_encoder_path)
                self._labels_list = encoder_data.get("labels", [])
                logger.info(f"Loaded classifier with {len(self._labels_list)} labels")
                return True
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        return False

    def _save_model(self) -> None:
        """Save trained model to disk."""
        if self._classifier is not None:
            joblib.dump(self._classifier, self.model_path)
            joblib.dump({"labels": self._labels_list}, self.label_encoder_path)
            logger.info(f"Saved classifier to {self.model_path}")

    def get_training_status(self) -> TrainingStatus:
        """Get current training status from database."""
        repository = get_repository()
        return repository.get_training_status()

    def should_use_local_model(self) -> bool:
        """Check if we have enough training data to use local model."""
        status = self.get_training_status()
        return (
            status.is_trained
            and self._classifier is not None
            and len(self._labels_list) >= 2
        )

    def should_retrain(self) -> bool:
        """Check if model should be retrained based on new feedback."""
        repository = get_repository()
        status = repository.get_training_status()

        if not status.ready_to_train:
            return False

        # If never trained, train now
        if not status.is_trained:
            return True

        # Check if we have enough new samples since last training
        # For simplicity, we just check if total samples increased significantly
        if status.sample_count >= status.min_samples_required:
            return True

        return False

    def train_model(self) -> TrainingResult:
        """Train the LightGBM classifier on feedback data."""
        try:
            # Import here to avoid loading at startup
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split

            repository = get_repository()

            # Get positive feedback for training
            feedback_list = repository.get_positive_feedback(with_embeddings=True)

            if len(feedback_list) < self.MIN_SAMPLES:
                return TrainingResult(
                    success=False,
                    message=f"Need at least {self.MIN_SAMPLES} positive samples, have {len(feedback_list)}",
                    sample_count=len(feedback_list),
                )

            # Prepare training data
            texts = []
            labels = []
            embeddings = []

            for fb in feedback_list:
                if fb.embedding:
                    embeddings.append(fb.embedding)
                    labels.append(fb.label_id)
                else:
                    # Generate embedding if not stored
                    texts.append(fb.text)
                    labels.append(fb.label_id)

            # Generate embeddings for texts without them
            if texts:
                new_embeddings = self.embed_texts(texts)
                embeddings.extend(new_embeddings.tolist())

            if len(embeddings) < self.MIN_SAMPLES:
                return TrainingResult(
                    success=False,
                    message=f"Not enough valid training samples: {len(embeddings)}",
                    sample_count=len(embeddings),
                )

            # Convert to numpy
            X = np.array(embeddings)
            y_labels = np.array(labels)

            # Create label encoding
            unique_labels = sorted(set(labels))
            if len(unique_labels) < 2:
                return TrainingResult(
                    success=False,
                    message="Need at least 2 different labels to train",
                    sample_count=len(embeddings),
                )

            label_to_idx = {label: idx for idx, label in enumerate(unique_labels)}
            y = np.array([label_to_idx[label] for label in y_labels])

            # Train/test split
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            # Train LightGBM
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            params = {
                "objective": "multiclass",
                "num_class": len(unique_labels),
                "metric": "multi_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.9,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
            }

            self._classifier = lgb.train(
                params,
                train_data,
                num_boost_round=100,
                valid_sets=[val_data],
                callbacks=[lgb.early_stopping(stopping_rounds=10)],
            )

            self._labels_list = unique_labels

            # Calculate validation accuracy
            y_pred = self._classifier.predict(X_val)
            y_pred_labels = np.argmax(y_pred, axis=1)
            accuracy = np.mean(y_pred_labels == y_val)

            # Save model
            self._save_model()

            # Count positive/negative samples
            all_feedback = repository.get_all_training_feedback(with_embeddings=False)
            positive_count = len([f for f in all_feedback if f.feedback_type.value in ("correct", "accepted")])
            negative_count = len([f for f in all_feedback if f.feedback_type.value in ("incorrect", "rejected")])

            # Save status to database
            repository.save_model_status(
                sample_count=len(embeddings),
                positive_samples=positive_count,
                negative_samples=negative_count,
                labels_count=len(unique_labels),
                accuracy=float(accuracy),
                model_path=str(self.model_path),
            )

            logger.info(f"Model trained: {len(embeddings)} samples, {len(unique_labels)} labels, {accuracy:.2%} accuracy")

            return TrainingResult(
                success=True,
                message=f"Model trained successfully with {accuracy:.1%} accuracy",
                accuracy=float(accuracy),
                sample_count=len(embeddings),
            )

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return TrainingResult(
                success=False,
                message=f"Training failed: {str(e)}",
            )

    def predict(
        self,
        texts: list[str],
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """
        Predict labels for texts.

        Returns list of dicts with:
        - label_id: predicted label
        - confidence: prediction confidence
        """
        if self._classifier is None or len(self._labels_list) == 0:
            return []

        # Generate embeddings
        embeddings = self.embed_texts(texts)

        # Get predictions
        predictions = self._classifier.predict(embeddings)

        results = []
        for i, text in enumerate(texts):
            probs = predictions[i]
            max_idx = np.argmax(probs)
            confidence = probs[max_idx]

            if confidence >= min_confidence:
                results.append({
                    "text": text,
                    "label_id": self._labels_list[max_idx],
                    "confidence": float(confidence),
                    "all_probs": {
                        self._labels_list[j]: float(probs[j])
                        for j in range(len(self._labels_list))
                    },
                })

        return results

    def predict_single(
        self,
        text: str,
        min_confidence: float = 0.3,
    ) -> Optional[dict]:
        """Predict label for a single text."""
        results = self.predict([text], min_confidence)
        return results[0] if results else None


# Singleton instance
_ml_service: Optional[MLService] = None


def get_ml_service() -> MLService:
    """Get or create the ML service singleton."""
    global _ml_service
    if _ml_service is None:
        _ml_service = MLService()
    return _ml_service
