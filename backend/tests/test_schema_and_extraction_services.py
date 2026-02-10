"""Regression tests for schema suggestion and extraction refinement services."""

import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

# Minimal chromadb stub for test environments without optional dependency.
if "chromadb" not in sys.modules:
    chromadb_module = types.ModuleType("chromadb")
    chromadb_config_module = types.ModuleType("chromadb.config")

    class _DummyCollection:
        def get(self, **_kwargs):
            return {"ids": [], "documents": [], "metadatas": []}

        def upsert(self, **_kwargs):
            return None

        def delete(self, **_kwargs):
            return None

    class _DummyPersistentClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_or_create_collection(self, *args, **kwargs):
            return _DummyCollection()

    class _DummySettings:
        def __init__(self, *args, **kwargs):
            pass

    chromadb_module.PersistentClient = _DummyPersistentClient
    chromadb_config_module.Settings = _DummySettings
    sys.modules["chromadb"] = chromadb_module
    sys.modules["chromadb.config"] = chromadb_config_module

from uu_backend.database.sqlite_client import SQLiteClient
from uu_backend.models.annotation import Annotation, AnnotationType, LabelCreate
from uu_backend.models.document import Document, DocumentMetadata
from uu_backend.models.evaluation import PromptVersion
from uu_backend.models.taxonomy import (
    Classification,
    DocumentType,
    DocumentTypeCreate,
    FieldType,
    SchemaField,
)
from uu_backend.services.extraction_service import ExtractionService
from uu_backend.services.schema_based_suggestion_service import SchemaBasedSuggestionService


class _FakeParseClient:
    def __init__(self, extracted_data: dict):
        self._extracted_data = extracted_data
        self.beta = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(parse=self.parse),
            )
        )

    def parse(self, **_kwargs):
        parsed = SimpleNamespace(model_dump=lambda: self._extracted_data)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])


class _FakeOpenAIClient(_FakeParseClient):
    def __init__(self, extracted_data: dict, spans_payload: dict):
        super().__init__(extracted_data)
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=lambda **_kwargs: self._create(spans_payload)),
        )

    def _create(self, spans_payload: dict):
        import json

        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(spans_payload)))]
        )


class _FakeVectorStore:
    def __init__(self, document: Document):
        self._document = document

    def get_document(self, _document_id: str):
        return self._document


def _build_document(document_id: str, content: str) -> Document:
    return Document(
        id=document_id,
        filename="test.txt",
        file_type="text/plain",
        content=content,
        created_at=datetime.utcnow(),
        metadata=DocumentMetadata(filename="test.txt", file_type="text/plain"),
        chunks=[],
    )


def _create_doc_type_with_array_schema(client: SQLiteClient) -> DocumentType:
    schema_fields = [
        SchemaField(
            name="claim_data",
            type=FieldType.ARRAY,
            items=SchemaField(
                name="claim_data_item",
                type=FieldType.OBJECT,
                properties={
                    "item": SchemaField(name="item", type=FieldType.STRING),
                    "cost": SchemaField(name="cost", type=FieldType.STRING),
                },
            ),
        )
    ]
    return client.create_document_type(
        DocumentTypeCreate(name=f"Claim Type {uuid4()}", schema_fields=schema_fields)
    )


def _setup_schema_service_test(tmp_path: Path, document_id: str):
    db_client = SQLiteClient(str(tmp_path / "taxonomy.db"))
    doc_type = _create_doc_type_with_array_schema(db_client)
    db_client.classify_document(document_id, doc_type.id, confidence=0.99, labeled_by="test")
    db_client.create_label(LabelCreate(name="claim_data", document_type_id=doc_type.id))

    document_text = "Repair line: Labor $250"
    extracted_data = {"claim_data": [{"item": "Labor", "cost": "250"}]}
    spans_payload = {
        "spans": [
            {"field_name": "claim_data.item", "text": "Labor", "start_char": 13, "end_char": 18},
            {"field_name": "claim_data.cost", "text": "250", "start_char": 20, "end_char": 23},
        ]
    }

    service = SchemaBasedSuggestionService.__new__(SchemaBasedSuggestionService)
    service.sqlite_client = db_client
    service.vector_store = _FakeVectorStore(_build_document(document_id, document_text))
    service.client = _FakeOpenAIClient(extracted_data=extracted_data, spans_payload=spans_payload)

    return service, db_client


def test_schema_suggestion_generation_without_auto_accept(tmp_path: Path):
    document_id = str(uuid4())
    service, db_client = _setup_schema_service_test(tmp_path, document_id)

    response = service.suggest_annotations(document_id=document_id, auto_accept=False)

    assert len(response.suggestions) == 2
    persisted = db_client.list_annotations(document_id)
    assert persisted == []


def test_schema_suggestion_auto_accept_persists_annotations(tmp_path: Path):
    document_id = str(uuid4())
    service, db_client = _setup_schema_service_test(tmp_path, document_id)

    service.suggest_annotations(document_id=document_id, auto_accept=True)
    persisted = db_client.list_annotations(document_id)

    assert len(persisted) == 2
    assert all(a.start_offset is not None for a in persisted)
    assert all(a.end_offset is not None for a in persisted)


def test_schema_suggestion_metadata_round_trip(tmp_path: Path):
    document_id = str(uuid4())
    service, db_client = _setup_schema_service_test(tmp_path, document_id)

    service.suggest_annotations(document_id=document_id, auto_accept=True)
    persisted = db_client.list_annotations(document_id)

    metadata_keys = sorted((a.metadata or {}).get("key") for a in persisted)
    assert metadata_keys == ["cost", "item"]
    assert any((a.metadata or {}).get("value") == "Labor" for a in persisted)
    assert any((a.metadata or {}).get("value") == "250" for a in persisted)


class _FakeSQLiteForExtraction:
    def __init__(self):
        self.saved = None
        self.prompt_version = PromptVersion(
            id="pv-1",
            name="custom",
            document_type_id="doc-type-1",
            system_prompt="CUSTOM_SYSTEM_PROMPT",
            user_prompt_template=(
                "schema={schema_desc}\nannotations={annotation_context}\n"
                "initial={initial_context}\ncontent={content}\nCUSTOM_TEMPLATE"
            ),
            description=None,
            is_active=True,
            created_by="test",
            created_at=datetime.utcnow(),
        )

    def get_classification(self, _document_id: str):
        return Classification(
            document_id="doc-1",
            document_type_id="doc-type-1",
            document_type_name="Invoice",
            confidence=0.9,
            labeled_by="test",
            created_at=datetime.utcnow(),
        )

    def get_document_type(self, _document_type_id: str):
        return DocumentType(
            id="doc-type-1",
            name="Invoice",
            description=None,
            schema_fields=[SchemaField(name="invoice_number", type=FieldType.STRING)],
            system_prompt=None,
            post_processing=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def list_annotations(self, document_id: str, annotation_type=None, label_id=None):
        _ = (document_id, annotation_type, label_id)
        return [
            Annotation(
                id="ann-1",
                document_id="doc-1",
                label_id="label-1",
                label_name="invoice_number",
                label_color="#000000",
                annotation_type=AnnotationType.TEXT_SPAN,
                start_offset=0,
                end_offset=5,
                text="INV-1",
                created_by="test",
                created_at=datetime.utcnow(),
            )
        ]

    def get_prompt_version(self, _version_id: str):
        return self.prompt_version

    def save_extraction_result(self, result):
        self.saved = result


class _FakeChatClientForExtraction:
    def __init__(self):
        self.messages = None
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self.create),
        )

    def create(self, **kwargs):
        self.messages = kwargs["messages"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"invoice_number":"INV-1"}'))]
        )


def test_extraction_refinement_uses_prompt_version_without_name_error(monkeypatch):
    fake_sqlite = _FakeSQLiteForExtraction()
    fake_vector = _FakeVectorStore(
        _build_document("doc-1", "Invoice Number: INV-1")
    )
    fake_client = _FakeChatClientForExtraction()

    import uu_backend.services.extraction_service as extraction_module

    monkeypatch.setattr(extraction_module, "get_sqlite_client", lambda: fake_sqlite)
    monkeypatch.setattr(extraction_module, "get_vector_store", lambda: fake_vector)

    service = ExtractionService.__new__(ExtractionService)
    service.client = fake_client
    service.model = "gpt-5-mini"

    result = service.extract_from_annotations(
        "doc-1",
        use_llm_refinement=True,
        prompt_version_id="pv-1",
    )

    assert result.fields[0].field_name == "invoice_number"
    assert result.fields[0].value == "INV-1"
    assert fake_client.messages[0]["content"] == "CUSTOM_SYSTEM_PROMPT"
    assert "CUSTOM_TEMPLATE" in fake_client.messages[1]["content"]
