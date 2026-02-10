"""SQLite database client for taxonomy and annotations."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from uu_backend.config import get_settings
from uu_backend.models.taxonomy import (
    Classification,
    DocumentType,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    SchemaField,
)
from uu_backend.models.annotation import (
    Annotation,
    AnnotationCreate,
    AnnotationType,
    Label,
    LabelCreate,
    LabelUpdate,
)
from uu_backend.models.feedback import (
    Feedback,
    FeedbackCreate,
    FeedbackSource,
    FeedbackType,
    TrainingStatus,
)


class SQLiteClient:
    """SQLite client for taxonomy and classification data."""

    def __init__(self, db_path: str):
        """Initialize SQLite client with database path."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Document types table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS document_types (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    schema_fields TEXT NOT NULL DEFAULT '[]',
                    system_prompt TEXT,
                    post_processing TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Classifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS classifications (
                    document_id TEXT PRIMARY KEY,
                    document_type_id TEXT NOT NULL,
                    confidence REAL,
                    labeled_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_classifications_type
                ON classifications(document_type_id)
            """)

            # Labels table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS labels (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT NOT NULL DEFAULT '#3b82f6',
                    description TEXT,
                    shortcut TEXT,
                    entity_type TEXT,
                    document_type_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE SET NULL
                )
            """)
            
            # Migration: add document_type_id column if it doesn't exist
            cursor.execute("PRAGMA table_info(labels)")
            columns = [row[1] for row in cursor.fetchall()]
            if "document_type_id" not in columns:
                cursor.execute("ALTER TABLE labels ADD COLUMN document_type_id TEXT")

            # Annotations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS annotations (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    label_id TEXT NOT NULL,
                    annotation_type TEXT NOT NULL,
                    start_offset INTEGER,
                    end_offset INTEGER,
                    text TEXT,
                    page INTEGER,
                    x REAL,
                    y REAL,
                    width REAL,
                    height REAL,
                    key_text TEXT,
                    key_start INTEGER,
                    key_end INTEGER,
                    value_text TEXT,
                    value_start INTEGER,
                    value_end INTEGER,
                    entity_type TEXT,
                    normalized_value TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (label_id) REFERENCES labels(id)
                )
            """)

            # Annotation indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_annotations_document
                ON annotations(document_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_annotations_label
                ON annotations(label_id)
            """)

            # Feedback table for ML training
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    label_id TEXT NOT NULL,
                    label_name TEXT,
                    text TEXT NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    feedback_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    embedding TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (label_id) REFERENCES labels(id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_label
                ON feedback(label_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feedback_type
                ON feedback(feedback_type)
            """)

            # Model status table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS model_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trained_at TEXT NOT NULL,
                    sample_count INTEGER NOT NULL,
                    positive_samples INTEGER NOT NULL DEFAULT 0,
                    negative_samples INTEGER NOT NULL DEFAULT 0,
                    labels_count INTEGER NOT NULL DEFAULT 0,
                    accuracy REAL,
                    model_path TEXT
                )
            """)

            # Extractions table for structured data
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extractions (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL UNIQUE,
                    document_type_id TEXT NOT NULL,
                    extracted_data TEXT NOT NULL,
                    extracted_at TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE
                )
            """)

            # Prompt versions table for tracking extraction prompts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    document_type_id TEXT,
                    system_prompt TEXT NOT NULL,
                    user_prompt_template TEXT,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_type
                ON prompt_versions(document_type_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_active
                ON prompt_versions(is_active)
            """)

            # Evaluations table for extraction quality metrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    document_type_id TEXT NOT NULL,
                    prompt_version_id TEXT,
                    metrics TEXT NOT NULL,
                    extraction_time_ms INTEGER,
                    evaluated_by TEXT,
                    evaluated_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE,
                    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id) ON DELETE SET NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_document
                ON evaluations(document_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_type
                ON evaluations(document_type_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_prompt
                ON evaluations(prompt_version_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_date
                ON evaluations(evaluated_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_extractions_document
                ON extractions(document_id)
            """)

            conn.commit()

    # Document Type CRUD Operations

    def create_document_type(self, data: DocumentTypeCreate) -> DocumentType:
        """Create a new document type."""
        now = datetime.utcnow()
        doc_type = DocumentType(
            id=str(uuid4()),
            name=data.name,
            description=data.description,
            schema_fields=data.schema_fields,
            system_prompt=data.system_prompt,
            post_processing=data.post_processing,
            created_at=now,
            updated_at=now,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO document_types
                (id, name, description, schema_fields, system_prompt, post_processing, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_type.id,
                    doc_type.name,
                    doc_type.description,
                    json.dumps([f.model_dump() for f in doc_type.schema_fields]),
                    doc_type.system_prompt,
                    doc_type.post_processing,
                    doc_type.created_at.isoformat(),
                    doc_type.updated_at.isoformat(),
                ),
            )
            conn.commit()

        return doc_type

    def get_document_type(self, type_id: str) -> Optional[DocumentType]:
        """Get a document type by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM document_types WHERE id = ?",
                (type_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_document_type(row)

    def get_document_type_by_name(self, name: str) -> Optional[DocumentType]:
        """Get a document type by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM document_types WHERE name = ?",
                (name,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_document_type(row)

    def list_document_types(self) -> list[DocumentType]:
        """List all document types."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM document_types ORDER BY name"
            )
            rows = cursor.fetchall()

        return [self._row_to_document_type(row) for row in rows]

    def update_document_type(
        self, type_id: str, data: DocumentTypeUpdate
    ) -> Optional[DocumentType]:
        """Update a document type."""
        existing = self.get_document_type(type_id)
        if not existing:
            return None

        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.schema_fields is not None:
            updates["schema_fields"] = json.dumps(
                [f.model_dump() for f in data.schema_fields]
            )
        if data.system_prompt is not None:
            updates["system_prompt"] = data.system_prompt
        if data.post_processing is not None:
            updates["post_processing"] = data.post_processing

        if not updates:
            return existing

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [type_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE document_types SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()

        return self.get_document_type(type_id)

    def delete_document_type(self, type_id: str) -> bool:
        """Delete a document type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # First, remove any classifications using this type
            cursor.execute(
                "DELETE FROM classifications WHERE document_type_id = ?",
                (type_id,),
            )

            # Then delete the type
            cursor.execute(
                "DELETE FROM document_types WHERE id = ?",
                (type_id,),
            )
            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def _row_to_document_type(self, row: sqlite3.Row) -> DocumentType:
        """Convert a database row to a DocumentType model."""
        schema_fields_data = json.loads(row["schema_fields"])
        schema_fields = [SchemaField(**f) for f in schema_fields_data]

        return DocumentType(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            schema_fields=schema_fields,
            system_prompt=row["system_prompt"],
            post_processing=row["post_processing"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Classification CRUD Operations

    def classify_document(
        self,
        document_id: str,
        document_type_id: str,
        confidence: Optional[float] = None,
        labeled_by: Optional[str] = None,
    ) -> Classification:
        """Classify a document with a document type."""
        # Verify document type exists
        doc_type = self.get_document_type(document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {document_type_id} not found")

        now = datetime.utcnow()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Upsert classification
            cursor.execute(
                """
                INSERT INTO classifications
                (document_id, document_type_id, confidence, labeled_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    document_type_id = excluded.document_type_id,
                    confidence = excluded.confidence,
                    labeled_by = excluded.labeled_by,
                    created_at = excluded.created_at
                """,
                (
                    document_id,
                    document_type_id,
                    confidence,
                    labeled_by,
                    now.isoformat(),
                ),
            )
            conn.commit()

        return Classification(
            document_id=document_id,
            document_type_id=document_type_id,
            document_type_name=doc_type.name,
            confidence=confidence,
            labeled_by=labeled_by,
            created_at=now,
        )

    def get_classification(self, document_id: str) -> Optional[Classification]:
        """Get the classification for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.*, dt.name as document_type_name
                FROM classifications c
                LEFT JOIN document_types dt ON c.document_type_id = dt.id
                WHERE c.document_id = ?
                """,
                (document_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return Classification(
            document_id=row["document_id"],
            document_type_id=row["document_type_id"],
            document_type_name=row["document_type_name"],
            confidence=row["confidence"],
            labeled_by=row["labeled_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def delete_classification(self, document_id: str) -> bool:
        """Remove classification from a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM classifications WHERE document_id = ?",
                (document_id,),
            )
            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def get_documents_by_type(self, document_type_id: str) -> list[str]:
        """Get all document IDs classified with a specific type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT document_id FROM classifications WHERE document_type_id = ?",
                (document_type_id,),
            )
            rows = cursor.fetchall()

        return [row["document_id"] for row in rows]

    # Label CRUD Operations

    def create_label(self, data: LabelCreate) -> Label:
        """Create a new label."""
        now = datetime.utcnow()
        label = Label(
            id=str(uuid4()),
            name=data.name,
            color=data.color,
            description=data.description,
            shortcut=data.shortcut,
            entity_type=data.entity_type,
            document_type_id=data.document_type_id,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO labels (id, name, color, description, shortcut, entity_type, document_type_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    label.id,
                    label.name,
                    label.color,
                    label.description,
                    label.shortcut,
                    label.entity_type,
                    label.document_type_id,
                    now.isoformat(),
                ),
            )
            conn.commit()

        return label

    def get_label(self, label_id: str) -> Optional[Label]:
        """Get a label by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM labels WHERE id = ?", (label_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return Label(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            description=row["description"],
            shortcut=row["shortcut"],
            entity_type=row["entity_type"],
            document_type_id=row["document_type_id"] if "document_type_id" in row.keys() else None,
        )

    def get_label_by_name(self, name: str) -> Optional[Label]:
        """Get a label by name."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM labels WHERE name = ?", (name,))
            row = cursor.fetchone()

        if not row:
            return None

        return Label(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            description=row["description"],
            shortcut=row["shortcut"],
            entity_type=row["entity_type"],
            document_type_id=row["document_type_id"] if "document_type_id" in row.keys() else None,
        )

    def list_labels(self, document_type_id: Optional[str] = None, include_global: bool = True) -> list[Label]:
        """List labels, optionally filtered by document type.
        
        Args:
            document_type_id: If provided, filter to labels for this doc type
            include_global: If True and document_type_id is set, also include global labels (null doc type)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if document_type_id:
                if include_global:
                    # Get labels for this type OR global labels
                    cursor.execute(
                        "SELECT * FROM labels WHERE document_type_id = ? OR document_type_id IS NULL ORDER BY name",
                        (document_type_id,)
                    )
                else:
                    # Only labels for this specific type
                    cursor.execute(
                        "SELECT * FROM labels WHERE document_type_id = ? ORDER BY name",
                        (document_type_id,)
                    )
            else:
                cursor.execute("SELECT * FROM labels ORDER BY name")
            
            rows = cursor.fetchall()

        return [
            Label(
                id=row["id"],
                name=row["name"],
                color=row["color"],
                description=row["description"],
                shortcut=row["shortcut"],
                entity_type=row["entity_type"],
                document_type_id=row["document_type_id"] if "document_type_id" in row.keys() else None,
            )
            for row in rows
        ]

    def update_label(self, label_id: str, data: LabelUpdate) -> Optional[Label]:
        """Update a label."""
        existing = self.get_label(label_id)
        if not existing:
            return None

        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.color is not None:
            updates["color"] = data.color
        if data.description is not None:
            updates["description"] = data.description
        if data.shortcut is not None:
            updates["shortcut"] = data.shortcut
        if data.entity_type is not None:
            updates["entity_type"] = data.entity_type
        if data.document_type_id is not None:
            updates["document_type_id"] = data.document_type_id

        if not updates:
            return existing

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [label_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE labels SET {set_clause} WHERE id = ?", values)
            conn.commit()

        return self.get_label(label_id)

    def delete_label(self, label_id: str) -> bool:
        """Delete a label (and its annotations)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete annotations using this label
            cursor.execute("DELETE FROM annotations WHERE label_id = ?", (label_id,))
            # Delete the label
            cursor.execute("DELETE FROM labels WHERE id = ?", (label_id,))
            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    # Annotation CRUD Operations

    def create_annotation(self, document_id: str, data: AnnotationCreate) -> Annotation:
        """Create a new annotation."""
        now = datetime.utcnow()
        annotation_id = str(uuid4())

        # Get label info
        label = self.get_label(data.label_id)
        if not label:
            raise ValueError(f"Label {data.label_id} not found")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO annotations (
                    id, document_id, label_id, annotation_type,
                    start_offset, end_offset, text,
                    page, x, y, width, height,
                    key_text, key_start, key_end,
                    value_text, value_start, value_end,
                    entity_type, normalized_value,
                    created_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    annotation_id,
                    document_id,
                    data.label_id,
                    data.annotation_type.value,
                    data.start_offset,
                    data.end_offset,
                    data.text,
                    data.page,
                    data.x,
                    data.y,
                    data.width,
                    data.height,
                    data.key_text,
                    data.key_start,
                    data.key_end,
                    data.value_text,
                    data.value_start,
                    data.value_end,
                    data.entity_type,
                    data.normalized_value,
                    data.created_by,
                    now.isoformat(),
                ),
            )
            conn.commit()

        return Annotation(
            id=annotation_id,
            document_id=document_id,
            label_id=data.label_id,
            label_name=label.name,
            label_color=label.color,
            annotation_type=data.annotation_type,
            start_offset=data.start_offset,
            end_offset=data.end_offset,
            text=data.text,
            page=data.page,
            x=data.x,
            y=data.y,
            width=data.width,
            height=data.height,
            key_text=data.key_text,
            key_start=data.key_start,
            key_end=data.key_end,
            value_text=data.value_text,
            value_start=data.value_start,
            value_end=data.value_end,
            entity_type=data.entity_type,
            normalized_value=data.normalized_value,
            created_by=data.created_by,
            created_at=now,
        )

    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        """Get an annotation by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, l.name as label_name, l.color as label_color
                FROM annotations a
                LEFT JOIN labels l ON a.label_id = l.id
                WHERE a.id = ?
                """,
                (annotation_id,),
            )
            row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_annotation(row)

    def list_annotations(
        self,
        document_id: str,
        annotation_type: Optional[AnnotationType] = None,
        label_id: Optional[str] = None,
    ) -> list[Annotation]:
        """List annotations for a document."""
        query = """
            SELECT a.*, l.name as label_name, l.color as label_color
            FROM annotations a
            LEFT JOIN labels l ON a.label_id = l.id
            WHERE a.document_id = ?
        """
        params: list = [document_id]

        if annotation_type:
            query += " AND a.annotation_type = ?"
            params.append(annotation_type.value)

        if label_id:
            query += " AND a.label_id = ?"
            params.append(label_id)

        query += " ORDER BY a.created_at DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_annotation(row) for row in rows]

    def delete_annotation(self, annotation_id: str) -> bool:
        """Delete an annotation."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
            deleted = cursor.rowcount > 0
            conn.commit()

        return deleted

    def delete_document_annotations(self, document_id: str) -> int:
        """Delete all annotations for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM annotations WHERE document_id = ?", (document_id,))
            count = cursor.rowcount
            conn.commit()

        return count

    def get_annotation_stats(self, document_id: str) -> dict:
        """Get annotation statistics for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute(
                "SELECT COUNT(*) as total FROM annotations WHERE document_id = ?",
                (document_id,),
            )
            total = cursor.fetchone()["total"]

            # By type
            cursor.execute(
                """
                SELECT annotation_type, COUNT(*) as count
                FROM annotations WHERE document_id = ?
                GROUP BY annotation_type
                """,
                (document_id,),
            )
            by_type = {row["annotation_type"]: row["count"] for row in cursor.fetchall()}

            # By label
            cursor.execute(
                """
                SELECT l.name, COUNT(*) as count
                FROM annotations a
                LEFT JOIN labels l ON a.label_id = l.id
                WHERE a.document_id = ?
                GROUP BY a.label_id
                """,
                (document_id,),
            )
            by_label = {row["name"] or "Unknown": row["count"] for row in cursor.fetchall()}

        return {
            "document_id": document_id,
            "total_annotations": total,
            "by_type": by_type,
            "by_label": by_label,
        }

    def _row_to_annotation(self, row: sqlite3.Row) -> Annotation:
        """Convert a database row to an Annotation model."""
        return Annotation(
            id=row["id"],
            document_id=row["document_id"],
            label_id=row["label_id"],
            label_name=row["label_name"],
            label_color=row["label_color"],
            annotation_type=AnnotationType(row["annotation_type"]),
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            text=row["text"],
            page=row["page"],
            x=row["x"],
            y=row["y"],
            width=row["width"],
            height=row["height"],
            key_text=row["key_text"],
            key_start=row["key_start"],
            key_end=row["key_end"],
            value_text=row["value_text"],
            value_start=row["value_start"],
            value_end=row["value_end"],
            entity_type=row["entity_type"],
            normalized_value=row["normalized_value"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Feedback CRUD Operations

    def create_feedback(
        self,
        data: FeedbackCreate,
        embedding: Optional[list[float]] = None,
    ) -> Feedback:
        """Create a new feedback record."""
        now = datetime.utcnow()
        feedback_id = str(uuid4())

        # Get label name
        label = self.get_label(data.label_id)
        label_name = label.name if label else None

        embedding_json = json.dumps(embedding) if embedding else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback (
                    id, document_id, label_id, label_name, text,
                    start_offset, end_offset, feedback_type, source,
                    embedding, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    data.document_id,
                    data.label_id,
                    label_name,
                    data.text,
                    data.start_offset,
                    data.end_offset,
                    data.feedback_type.value,
                    data.source.value,
                    embedding_json,
                    now.isoformat(),
                ),
            )
            conn.commit()

        return Feedback(
            id=feedback_id,
            document_id=data.document_id,
            label_id=data.label_id,
            label_name=label_name,
            text=data.text,
            start_offset=data.start_offset,
            end_offset=data.end_offset,
            feedback_type=data.feedback_type,
            source=data.source,
            embedding=embedding,
            created_at=now,
        )

    def list_feedback(
        self,
        label_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        with_embeddings: bool = False,
    ) -> list[Feedback]:
        """List feedback records with optional filters."""
        query = "SELECT * FROM feedback WHERE 1=1"
        params: list = []

        if label_id:
            query += " AND label_id = ?"
            params.append(label_id)

        if feedback_type:
            query += " AND feedback_type = ?"
            params.append(feedback_type.value)

        query += " ORDER BY created_at DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [self._row_to_feedback(row, with_embeddings) for row in rows]

    def get_feedback_count(self) -> int:
        """Get total feedback count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM feedback")
            return cursor.fetchone()["count"]

    def get_positive_feedback(self, with_embeddings: bool = True) -> list[Feedback]:
        """Get all positive (correct/accepted) feedback for training."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM feedback
                WHERE feedback_type IN ('correct', 'accepted')
                ORDER BY created_at
                """
            )
            rows = cursor.fetchall()

        return [self._row_to_feedback(row, with_embeddings) for row in rows]

    def get_all_training_feedback(self, with_embeddings: bool = True) -> list[Feedback]:
        """Get all feedback for training (both positive and negative)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feedback ORDER BY created_at")
            rows = cursor.fetchall()

        return [self._row_to_feedback(row, with_embeddings) for row in rows]

    def get_training_status(self) -> TrainingStatus:
        """Get the current training status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Count feedback
            cursor.execute("SELECT COUNT(*) as count FROM feedback")
            total = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback WHERE feedback_type IN ('correct', 'accepted')"
            )
            positive = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM feedback WHERE feedback_type IN ('incorrect', 'rejected')"
            )
            negative = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(DISTINCT label_id) as count FROM feedback"
            )
            labels_count = cursor.fetchone()["count"]

            # Get latest model status
            cursor.execute(
                "SELECT * FROM model_status ORDER BY trained_at DESC LIMIT 1"
            )
            model_row = cursor.fetchone()

        min_samples = 20
        return TrainingStatus(
            is_trained=model_row is not None,
            sample_count=total,
            positive_samples=positive,
            negative_samples=negative,
            labels_count=labels_count,
            last_trained_at=datetime.fromisoformat(model_row["trained_at"]) if model_row else None,
            accuracy=model_row["accuracy"] if model_row else None,
            model_path=model_row["model_path"] if model_row else None,
            min_samples_required=min_samples,
            ready_to_train=positive >= min_samples and labels_count >= 2,
        )

    def save_model_status(
        self,
        sample_count: int,
        positive_samples: int,
        negative_samples: int,
        labels_count: int,
        accuracy: Optional[float],
        model_path: str,
    ) -> None:
        """Save model training status."""
        now = datetime.utcnow()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO model_status (
                    trained_at, sample_count, positive_samples, negative_samples,
                    labels_count, accuracy, model_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now.isoformat(),
                    sample_count,
                    positive_samples,
                    negative_samples,
                    labels_count,
                    accuracy,
                    model_path,
                ),
            )
            conn.commit()

    def _row_to_feedback(self, row: sqlite3.Row, with_embeddings: bool = False) -> Feedback:
        """Convert a database row to a Feedback model."""
        embedding = None
        if with_embeddings and row["embedding"]:
            embedding = json.loads(row["embedding"])

        return Feedback(
            id=row["id"],
            document_id=row["document_id"],
            label_id=row["label_id"],
            label_name=row["label_name"],
            text=row["text"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            feedback_type=FeedbackType(row["feedback_type"]),
            source=FeedbackSource(row["source"]),
            embedding=embedding,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Extraction CRUD Operations

    def save_extraction_result(self, result) -> None:
        """Save or update an extraction result."""
        from uu_backend.models.taxonomy import ExtractionResult
        
        # Convert fields to JSON
        fields_data = [
            {
                "field_name": f.field_name,
                "value": f.value,
                "confidence": f.confidence,
                "source_text": f.source_text,
            }
            for f in result.fields
        ]
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert - replace if exists
            cursor.execute(
                """
                INSERT OR REPLACE INTO extractions 
                (id, document_id, document_type_id, extracted_data, extracted_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    result.document_id,
                    result.document_type_id,
                    json.dumps(fields_data),
                    result.extracted_at.isoformat(),
                ),
            )
            conn.commit()

    def get_extraction(self, document_id: str) -> Optional[dict]:
        """Get extraction result for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM extractions WHERE document_id = ?",
                (document_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "document_id": row["document_id"],
            "document_type_id": row["document_type_id"],
            "fields": json.loads(row["extracted_data"]),
            "extracted_at": row["extracted_at"],
        }

    def delete_extraction(self, document_id: str) -> bool:
        """Delete extraction for a document."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM extractions WHERE document_id = ?",
                (document_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    # Prompt Version CRUD Operations

    def create_prompt_version(self, prompt_version) -> str:
        """Create a new prompt version."""
        from uu_backend.models.evaluation import PromptVersion
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # If setting as active, deactivate others for this document type
            if prompt_version.is_active:
                cursor.execute(
                    """
                    UPDATE prompt_versions 
                    SET is_active = 0 
                    WHERE document_type_id IS ? OR (document_type_id IS NULL AND ? IS NULL)
                    """,
                    (prompt_version.document_type_id, prompt_version.document_type_id)
                )
            
            cursor.execute(
                """
                INSERT INTO prompt_versions 
                (id, name, document_type_id, system_prompt, user_prompt_template, 
                 description, is_active, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt_version.id,
                    prompt_version.name,
                    prompt_version.document_type_id,
                    prompt_version.system_prompt,
                    prompt_version.user_prompt_template,
                    prompt_version.description,
                    1 if prompt_version.is_active else 0,
                    prompt_version.created_by,
                    prompt_version.created_at.isoformat(),
                ),
            )
            conn.commit()
            return prompt_version.id

    def get_prompt_version(self, version_id: str):
        """Get a prompt version by ID."""
        from uu_backend.models.evaluation import PromptVersion
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM prompt_versions WHERE id = ?",
                (version_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return PromptVersion(
            id=row["id"],
            name=row["name"],
            document_type_id=row["document_type_id"],
            system_prompt=row["system_prompt"],
            user_prompt_template=row["user_prompt_template"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def get_active_prompt_version(self, document_type_id: Optional[str] = None):
        """Get the active prompt version for a document type."""
        from uu_backend.models.evaluation import PromptVersion
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM prompt_versions 
                WHERE is_active = 1 
                AND (document_type_id = ? OR (document_type_id IS NULL AND ? IS NULL))
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (document_type_id, document_type_id)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        return PromptVersion(
            id=row["id"],
            name=row["name"],
            document_type_id=row["document_type_id"],
            system_prompt=row["system_prompt"],
            user_prompt_template=row["user_prompt_template"],
            description=row["description"],
            is_active=bool(row["is_active"]),
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_prompt_versions(
        self, 
        document_type_id: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> list:
        """List prompt versions with optional filters."""
        from uu_backend.models.evaluation import PromptVersion
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM prompt_versions WHERE 1=1"
            params = []
            
            if document_type_id is not None:
                query += " AND (document_type_id = ? OR document_type_id IS NULL)"
                params.append(document_type_id)
            
            if is_active is not None:
                query += " AND is_active = ?"
                params.append(1 if is_active else 0)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        return [
            PromptVersion(
                id=row["id"],
                name=row["name"],
                document_type_id=row["document_type_id"],
                system_prompt=row["system_prompt"],
                user_prompt_template=row["user_prompt_template"],
                description=row["description"],
                is_active=bool(row["is_active"]),
                created_by=row["created_by"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def update_prompt_version(self, version_id: str, updates: dict) -> bool:
        """Update a prompt version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # If setting as active, deactivate others
            if updates.get("is_active"):
                # Get current version to know document_type_id
                cursor.execute("SELECT document_type_id FROM prompt_versions WHERE id = ?", (version_id,))
                row = cursor.fetchone()
                if row:
                    doc_type_id = row["document_type_id"]
                    cursor.execute(
                        """
                        UPDATE prompt_versions 
                        SET is_active = 0 
                        WHERE id != ? AND (document_type_id IS ? OR (document_type_id IS NULL AND ? IS NULL))
                        """,
                        (version_id, doc_type_id, doc_type_id)
                    )
            
            # Build update query
            set_clauses = []
            params = []
            
            for key, value in updates.items():
                if key == "is_active":
                    set_clauses.append("is_active = ?")
                    params.append(1 if value else 0)
                else:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            
            if not set_clauses:
                return False
            
            params.append(version_id)
            query = f"UPDATE prompt_versions SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def delete_prompt_version(self, version_id: str) -> bool:
        """Delete a prompt version."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prompt_versions WHERE id = ?", (version_id,))
            conn.commit()
            return cursor.rowcount > 0

    # Evaluation CRUD Operations

    def save_evaluation(self, evaluation) -> None:
        """Save an evaluation result."""
        from uu_backend.models.evaluation import ExtractionEvaluation
        
        # Serialize metrics to JSON
        metrics_json = evaluation.metrics.model_dump_json()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluations 
                (id, document_id, document_type_id, prompt_version_id, metrics, 
                 extraction_time_ms, evaluated_by, evaluated_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.id,
                    evaluation.document_id,
                    evaluation.document_type_id,
                    evaluation.prompt_version_id,
                    metrics_json,
                    evaluation.extraction_time_ms,
                    evaluation.evaluated_by,
                    evaluation.evaluated_at.isoformat(),
                    evaluation.notes,
                ),
            )
            conn.commit()

    def get_evaluation(self, evaluation_id: str):
        """Get an evaluation by ID."""
        from uu_backend.models.evaluation import ExtractionEvaluation, ExtractionEvaluationMetrics
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.*, pv.name as prompt_version_name
                FROM evaluations e
                LEFT JOIN prompt_versions pv ON e.prompt_version_id = pv.id
                WHERE e.id = ?
                """,
                (evaluation_id,)
            )
            row = cursor.fetchone()
        
        if not row:
            return None
        
        metrics = ExtractionEvaluationMetrics.model_validate_json(row["metrics"])
        
        return ExtractionEvaluation(
            id=row["id"],
            document_id=row["document_id"],
            document_type_id=row["document_type_id"],
            prompt_version_id=row["prompt_version_id"],
            prompt_version_name=row["prompt_version_name"],
            metrics=metrics,
            extraction_time_ms=row["extraction_time_ms"],
            evaluated_by=row["evaluated_by"],
            evaluated_at=datetime.fromisoformat(row["evaluated_at"]),
            notes=row["notes"],
        )

    def list_evaluations(
        self,
        document_id: Optional[str] = None,
        document_type_id: Optional[str] = None,
        prompt_version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list, int]:
        """List evaluations with optional filters."""
        from uu_backend.models.evaluation import ExtractionEvaluation, ExtractionEvaluationMetrics
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query
            query = """
                SELECT e.*, pv.name as prompt_version_name
                FROM evaluations e
                LEFT JOIN prompt_versions pv ON e.prompt_version_id = pv.id
                WHERE 1=1
            """
            params = []
            
            if document_id:
                query += " AND e.document_id = ?"
                params.append(document_id)
            
            if document_type_id:
                query += " AND e.document_type_id = ?"
                params.append(document_type_id)
            
            if prompt_version_id:
                query += " AND e.prompt_version_id = ?"
                params.append(prompt_version_id)
            
            # Get total count
            count_query = query.replace("e.*, pv.name as prompt_version_name", "COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]
            
            # Get results with pagination
            query += " ORDER BY e.evaluated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        evaluations = []
        for row in rows:
            metrics = ExtractionEvaluationMetrics.model_validate_json(row["metrics"])
            evaluations.append(
                ExtractionEvaluation(
                    id=row["id"],
                    document_id=row["document_id"],
                    document_type_id=row["document_type_id"],
                    prompt_version_id=row["prompt_version_id"],
                    prompt_version_name=row["prompt_version_name"],
                    metrics=metrics,
                    extraction_time_ms=row["extraction_time_ms"],
                    evaluated_by=row["evaluated_by"],
                    evaluated_at=datetime.fromisoformat(row["evaluated_at"]),
                    notes=row["notes"],
                )
            )
        
        return evaluations, total

    def get_evaluation_summary(
        self,
        prompt_version_id: Optional[str] = None,
        document_type_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Get aggregated evaluation metrics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    COUNT(*) as total_evaluations,
                    e.prompt_version_id,
                    pv.name as prompt_version_name,
                    e.document_type_id,
                    MIN(e.evaluated_at) as earliest_evaluation,
                    MAX(e.evaluated_at) as latest_evaluation,
                    e.metrics
                FROM evaluations e
                LEFT JOIN prompt_versions pv ON e.prompt_version_id = pv.id
                WHERE 1=1
            """
            params = []
            
            if prompt_version_id:
                query += " AND e.prompt_version_id = ?"
                params.append(prompt_version_id)
            
            if document_type_id:
                query += " AND e.document_type_id = ?"
                params.append(document_type_id)
            
            query += " GROUP BY e.prompt_version_id, e.document_type_id"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        if not rows:
            return None
        
        # Aggregate metrics across evaluations
        from uu_backend.models.evaluation import ExtractionEvaluationMetrics
        
        results = []
        for row in rows:
            # Get all evaluations for this group
            eval_query = """
                SELECT metrics FROM evaluations 
                WHERE prompt_version_id IS ? AND document_type_id = ?
            """
            cursor.execute(eval_query, (row["prompt_version_id"], row["document_type_id"]))
            eval_rows = cursor.fetchall()
            
            # Calculate averages
            total = len(eval_rows)
            sum_accuracy = 0.0
            sum_precision = 0.0
            sum_recall = 0.0
            sum_f1 = 0.0
            field_stats = {}
            
            for eval_row in eval_rows:
                metrics = ExtractionEvaluationMetrics.model_validate_json(eval_row["metrics"])
                sum_accuracy += metrics.accuracy
                sum_precision += metrics.precision
                sum_recall += metrics.recall
                sum_f1 += metrics.f1_score
                
                # Aggregate field-level stats
                for field_eval in metrics.field_evaluations:
                    if field_eval.field_name not in field_stats:
                        field_stats[field_eval.field_name] = {
                            "correct": 0,
                            "total": 0,
                            "present": 0,
                            "extracted": 0,
                        }
                    stats = field_stats[field_eval.field_name]
                    stats["total"] += 1
                    if field_eval.is_correct:
                        stats["correct"] += 1
                    if field_eval.is_present:
                        stats["present"] += 1
                    if field_eval.is_extracted:
                        stats["extracted"] += 1
            
            # Calculate field-level metrics
            field_performance = {}
            for field_name, stats in field_stats.items():
                accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
                precision = stats["correct"] / stats["extracted"] if stats["extracted"] > 0 else 0.0
                recall = stats["correct"] / stats["present"] if stats["present"] > 0 else 0.0
                field_performance[field_name] = {
                    "accuracy": accuracy,
                    "precision": precision,
                    "recall": recall,
                }
            
            results.append({
                "prompt_version_id": row["prompt_version_id"],
                "prompt_version_name": row["prompt_version_name"],
                "document_type_id": row["document_type_id"],
                "total_evaluations": total,
                "avg_accuracy": sum_accuracy / total,
                "avg_precision": sum_precision / total,
                "avg_recall": sum_recall / total,
                "avg_f1_score": sum_f1 / total,
                "field_performance": field_performance,
                "earliest_evaluation": row["earliest_evaluation"],
                "latest_evaluation": row["latest_evaluation"],
            })
        
        return results[0] if len(results) == 1 else results


# Singleton instance
_client: Optional[SQLiteClient] = None


def get_sqlite_client() -> SQLiteClient:
    """Get the singleton SQLite client instance."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = SQLiteClient(settings.sqlite_database_path)
    return _client
