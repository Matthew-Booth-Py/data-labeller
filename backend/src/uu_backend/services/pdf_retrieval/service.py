"""PDF-only intelligent retrieval service."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import fitz
from PIL import Image
from django.db import transaction
from collections.abc import Callable

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.services.contextual_retrieval.embedder import OpenAIEmbedder
from uu_backend.services.contextual_retrieval.models import SearchResult

from .artifact_store import PDFArtifactStore
from .document_intelligence import (
    AzureDocumentIntelligenceProvider,
    NormalizedDocumentAnalysis,
    NormalizedLine,
    NormalizedPage,
    NormalizedTable,
)
from .vector_index import PDFVectorIndex

logger = logging.getLogger(__name__)

PDF_RETRIEVAL_BACKEND = "intelligent_pdf_v1"


def _partial_pdf_analysis_error(actual_pages: int, expected_pages: int) -> ValueError:
    return ValueError(
        "Azure Document Intelligence returned "
        f"{actual_pages} pages for a {expected_pages}-page PDF. "
        "This usually means the configured resource cannot analyze the full PDF."
    )


@dataclass(slots=True)
class _TableFragment:
    page_model: orm.RetrievalPageModel
    bbox: list[float]
    source_bbox: list[float]
    markdown: str
    preview_png: bytes
    row_count: int
    column_count: int


@dataclass(slots=True)
class _PreparedTable:
    index: int
    page_model: orm.RetrievalPageModel
    label: str
    bbox: list[float]
    markdown: str
    heading_context: str
    fragments: list[_TableFragment]
    metadata: dict[str, Any]


@dataclass(slots=True)
class _PreparedImage:
    page_model: orm.RetrievalPageModel
    label: str
    bbox: list[float]
    preview_bytes: bytes
    media_type: str
    surrounding_text: str


class PDFRetrievalService:
    def __init__(self):
        self.settings = get_settings()
        self.artifacts = PDFArtifactStore()
        self.vector_index = PDFVectorIndex()
        self.embedder = OpenAIEmbedder()
        self._provider: AzureDocumentIntelligenceProvider | None = None

    @property
    def provider(self) -> AzureDocumentIntelligenceProvider:
        if self._provider is None:
            self._provider = AzureDocumentIntelligenceProvider(
                endpoint=self.settings.azure_di_endpoint,
                api_key=self.settings.azure_di_key,
            )
        return self._provider

    def index_document(
        self,
        *,
        document_id: str,
        file_path: str,
        filename: str,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> int:
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"PDF file not found: {file_path}")

        pdf_bytes = path.read_bytes()
        analysis = self.provider.analyze_pdf(pdf_bytes)
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(analysis.pages) != pdf.page_count:
            raise _partial_pdf_analysis_error(len(analysis.pages), pdf.page_count)

        document_model = orm.DocumentModel.objects.get(id=document_id)
        self.delete_document(document_id)

        if progress_callback:
            progress_callback("persisting_pages", 0, max(len(analysis.pages), 1))

        page_models, page_bitmaps, chunk_index = self._persist_pages(
            document_model=document_model,
            analysis=analysis,
            pdf=pdf,
            progress_callback=progress_callback,
        )

        prepared_tables = self._prepare_tables(
            analysis=analysis,
            page_models=page_models,
            page_bitmaps=page_bitmaps,
        )
        prepared_images = self._prepare_images(
            pdf=pdf,
            page_models=page_models,
        )

        if progress_callback:
            progress_callback(
                "summarizing",
                0,
                max(len(prepared_tables) + len(prepared_images), 1),
            )

        table_summaries = [
            self._summarize_table_with_context(
                markdown=prepared_table.markdown,
                filename=filename,
                page_number=prepared_table.page_model.page_number,
                heading_context=prepared_table.heading_context,
            )
            for prepared_table in prepared_tables
        ]
        image_captions = [
            self._caption_image(filename, prepared_image.page_model.page_number, prepared_image.surrounding_text)
            for prepared_image in prepared_images
        ]

        chunks: list[orm.RetrievalChunkModel] = []
        chunk_index = self._persist_tables(
            document_model=document_model,
            prepared_tables=prepared_tables,
            summaries=table_summaries,
            chunks=chunks,
            starting_chunk_index=chunk_index,
            progress_callback=progress_callback,
        )
        chunk_index = self._persist_images(
            document_model=document_model,
            prepared_images=prepared_images,
            captions=image_captions,
            chunks=chunks,
            starting_chunk_index=chunk_index,
            progress_callback=progress_callback,
        )

        page_chunks = list(
            orm.RetrievalChunkModel.objects.select_related("page", "asset")
            .filter(document_id=document_id, chunk_type="page")
            .order_by("chunk_index")
        )
        all_chunks = [*page_chunks, *chunks]
        if progress_callback:
            progress_callback("embedding", 0, max(len(all_chunks), 1))

        embeddings = self.embedder.embed([chunk.content for chunk in all_chunks])
        self.vector_index.upsert_document(document_id, all_chunks, embeddings)

        orm.DocumentModel.objects.filter(id=document_id).update(
            retrieval_index_backend=PDF_RETRIEVAL_BACKEND
        )
        return len(all_chunks)

    def search(
        self,
        *,
        query: str,
        top_k: int = 20,
        filter_doc_id: str | None = None,
        asset_types: set[str] | None = None,
    ) -> list[SearchResult]:
        query_embedding = self.embedder.embed_query(query)
        return self.vector_index.search(
            query_embedding,
            top_k=top_k,
            filter_doc_id=filter_doc_id,
            asset_types=asset_types,
        )

    def search_for_extraction(
        self,
        *,
        queries: list[str],
        top_k_per_query: int,
        filter_doc_id: str,
        asset_types: set[str] | None = None,
    ) -> list[SearchResult]:
        seen_chunk_ids: set[str] = set()
        results: list[SearchResult] = []
        for query in queries:
            for result in self.search(
                query=query,
                top_k=top_k_per_query,
                filter_doc_id=filter_doc_id,
                asset_types=asset_types,
            ):
                marker = result.chunk_id or f"{result.doc_id}_{result.chunk_index}"
                if marker in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(marker)
                results.append(result)
        results.sort(key=lambda item: item.score, reverse=True)
        return results

    def delete_document(self, document_id: str) -> dict[str, int]:
        artifact_paths = list(
            orm.RetrievalArtifactModel.objects.filter(document_id=document_id).values_list(
                "relative_path", flat=True
            )
        )
        vector_deleted = self.vector_index.delete_document(document_id)
        with transaction.atomic():
            orm.RetrievalCitationModel.objects.filter(document_id=document_id).delete()
            orm.RetrievalChunkModel.objects.filter(document_id=document_id).delete()
            orm.RetrievalAssetModel.objects.filter(document_id=document_id).delete()
            orm.RetrievalPageModel.objects.filter(document_id=document_id).delete()
            orm.RetrievalArtifactModel.objects.filter(document_id=document_id).delete()

        for relative_path in artifact_paths:
            self.artifacts.delete(relative_path)

        return {
            "vector_store": vector_deleted,
            "artifacts": len(artifact_paths),
        }

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        rows = (
            orm.RetrievalChunkModel.objects.select_related("asset", "page")
            .filter(document_id=document_id)
            .order_by("chunk_index")
        )
        return [
            {
                "chunk_id": row.id,
                "chunk_index": row.chunk_index,
                "text": row.content,
                "metadata": {
                    **(row.metadata or {}),
                    "page_number": row.page.page_number,
                    "asset_type": row.asset.asset_type if row.asset else None,
                    "asset_label": row.asset.label if row.asset else None,
                },
            }
            for row in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        return {
            "vector_store_count": self.vector_index.count(),
            "bm25_index_count": 0,
            "reranker_type": "None",
            "backend": PDF_RETRIEVAL_BACKEND,
        }

    def _persist_pages(
        self,
        *,
        document_model: orm.DocumentModel,
        analysis: NormalizedDocumentAnalysis,
        pdf: fitz.Document,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> tuple[dict[int, orm.RetrievalPageModel], dict[int, Image.Image], int]:
        page_models: dict[int, orm.RetrievalPageModel] = {}
        page_bitmaps: dict[int, Image.Image] = {}
        chunk_index = 0

        for current_index, normalized_page in enumerate(analysis.pages, start=1):
            pdf_page = pdf[normalized_page.page_number - 1]
            pix = pdf_page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image = Image.open(BytesIO(pix.tobytes("png")))
            image.load()
            page_bitmaps[normalized_page.page_number] = image

            page_model = orm.RetrievalPageModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page_number=normalized_page.page_number,
                width=float(image.width),
                height=float(image.height),
                source_width=normalized_page.width,
                source_height=normalized_page.height,
                rotation=0,
                text=normalized_page.text,
            )
            page_models[normalized_page.page_number] = page_model

            artifact = self._save_artifact(
                document_model=document_model,
                data=pix.tobytes("png"),
                media_type="image/png",
            )
            page_asset = orm.RetrievalAssetModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=page_model,
                asset_type="page",
                label=f"Page {normalized_page.page_number}",
                bbox=[0.0, 0.0, float(image.width), float(image.height)],
                text_content=normalized_page.text[:4000],
                preview_artifact=artifact,
                metadata={"page_number": normalized_page.page_number},
            )
            page_chunk = orm.RetrievalChunkModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=page_model,
                asset=page_asset,
                chunk_index=chunk_index,
                chunk_type="page",
                content=self._truncate(normalized_page.text, max_chars=8000),
                metadata={
                    "page_number": normalized_page.page_number,
                    "asset_type": "page",
                    "asset_label": page_asset.label,
                },
            )
            orm.RetrievalCitationModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=page_model,
                chunk=page_chunk,
                asset=page_asset,
                preview_artifact=artifact,
                label=page_asset.label,
                bbox=page_asset.bbox,
                regions=[
                    {
                        "page_number": normalized_page.page_number,
                        "page_id": page_model.id,
                        "bbox": page_asset.bbox,
                        "preview_artifact_id": artifact.id,
                    }
                ],
            )
            chunk_index += 1
            if progress_callback:
                progress_callback("persisting_pages", current_index, max(len(analysis.pages), 1))

        return page_models, page_bitmaps, chunk_index

    def _prepare_tables(
        self,
        *,
        analysis: NormalizedDocumentAnalysis,
        page_models: dict[int, orm.RetrievalPageModel],
        page_bitmaps: dict[int, Image.Image],
    ) -> list[_PreparedTable]:
        fragments: list[_TableFragment] = []
        for table in analysis.tables:
            page_model = page_models.get(table.page_number)
            page_image = page_bitmaps.get(table.page_number)
            if page_model is None or page_image is None or not table.markdown.strip():
                continue
            fragments.append(
                _TableFragment(
                    page_model=page_model,
                    bbox=self._absolute_bbox(
                        table.bbox,
                        page_model.width,
                        page_model.height,
                        page_model.source_width,
                        page_model.source_height,
                    ),
                    source_bbox=table.bbox,
                    markdown=table.markdown,
                    preview_png=self._crop_preview(
                        page_image,
                        table.bbox,
                        page_model.width,
                        page_model.height,
                        page_model.source_width,
                        page_model.source_height,
                    ),
                    row_count=table.row_count,
                    column_count=table.column_count,
                )
            )

        stitched_groups: list[list[_TableFragment]] = []
        for fragment in fragments:
            if stitched_groups and self._should_stitch_table_fragments(stitched_groups[-1][-1], fragment):
                stitched_groups[-1].append(fragment)
            else:
                stitched_groups.append([fragment])

        prepared_tables: list[_PreparedTable] = []
        for index, group in enumerate(stitched_groups, start=1):
            primary = group[0]
            page_numbers = [fragment.page_model.page_number for fragment in group]
            row_count = sum(fragment.row_count for fragment in group)
            if len(group) > 1:
                row_count -= len(group) - 1
            heading_context = self._table_heading_context(
                page=next(
                    (page for page in analysis.pages if page.page_number == primary.page_model.page_number),
                    None,
                ),
                bbox=primary.source_bbox,
            )
            prepared_tables.append(
                _PreparedTable(
                    index=index,
                    page_model=primary.page_model,
                    label=self._table_label(index, page_numbers),
                    bbox=primary.bbox,
                    markdown=self._merge_table_markdown(group),
                    heading_context=heading_context,
                    fragments=group,
                    metadata={
                        "page_number": primary.page_model.page_number,
                        "page_numbers": page_numbers,
                        "row_count": row_count,
                        "column_count": primary.column_count,
                        "is_multi_page": len(group) > 1,
                        "heading_context": heading_context,
                    },
                )
            )
        return prepared_tables

    def _prepare_images(
        self,
        *,
        pdf: fitz.Document,
        page_models: dict[int, orm.RetrievalPageModel],
    ) -> list[_PreparedImage]:
        images: list[_PreparedImage] = []
        for page_number in range(1, pdf.page_count + 1):
            page_model = page_models.get(page_number)
            if page_model is None:
                continue
            pdf_page = pdf[page_number - 1]
            embedded_images = pdf_page.get_images(full=True)
            for image_index, image_info in enumerate(embedded_images, start=1):
                xref = image_info[0]
                rects = pdf_page.get_image_rects(xref)
                extracted = pdf.extract_image(xref)
                if not extracted:
                    continue
                media_type = f"image/{extracted.get('ext', 'png')}"
                preview_bytes = extracted["image"]
                for rect in rects or [pdf_page.rect]:
                    images.append(
                        _PreparedImage(
                            page_model=page_model,
                            label=f"Image {image_index} on page {page_number}",
                            bbox=[float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)],
                            preview_bytes=preview_bytes,
                            media_type=media_type,
                            surrounding_text=page_model.text[:4000],
                        )
                    )
        return images

    def _persist_tables(
        self,
        *,
        document_model: orm.DocumentModel,
        prepared_tables: list[_PreparedTable],
        summaries: list[str],
        chunks: list[orm.RetrievalChunkModel],
        starting_chunk_index: int,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> int:
        chunk_index = starting_chunk_index
        total = max(len(prepared_tables), 1)
        for current_index, (prepared_table, summary) in enumerate(
            zip(prepared_tables, summaries, strict=True),
            start=1,
        ):
            region_payloads = []
            primary_artifact: orm.RetrievalArtifactModel | None = None
            for fragment in prepared_table.fragments:
                region_artifact = self._save_artifact(
                    document_model=document_model,
                    data=fragment.preview_png,
                    media_type="image/png",
                )
                if primary_artifact is None:
                    primary_artifact = region_artifact
                region_payloads.append(
                    {
                        "page_number": fragment.page_model.page_number,
                        "page_id": fragment.page_model.id,
                        "bbox": fragment.bbox,
                        "preview_artifact_id": region_artifact.id,
                    }
                )

            asset = orm.RetrievalAssetModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_table.page_model,
                asset_type="table",
                label=prepared_table.label,
                bbox=prepared_table.bbox,
                text_content=self._combine_table_text(prepared_table),
                preview_artifact=primary_artifact,
                metadata={**prepared_table.metadata, "summary": summary},
            )
            chunk = orm.RetrievalChunkModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_table.page_model,
                asset=asset,
                chunk_index=chunk_index,
                chunk_type="table",
                content=self._table_chunk_content(prepared_table, summary),
                metadata={
                    **prepared_table.metadata,
                    "asset_type": "table",
                    "asset_label": prepared_table.label,
                },
            )
            orm.RetrievalCitationModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_table.page_model,
                chunk=chunk,
                asset=asset,
                preview_artifact=primary_artifact,
                label=prepared_table.label,
                bbox=prepared_table.bbox,
                regions=region_payloads,
            )
            chunks.append(chunk)
            chunk_index += 1
            if progress_callback:
                progress_callback("summarizing", current_index, total)
        return chunk_index

    def _persist_images(
        self,
        *,
        document_model: orm.DocumentModel,
        prepared_images: list[_PreparedImage],
        captions: list[str],
        chunks: list[orm.RetrievalChunkModel],
        starting_chunk_index: int,
        progress_callback: Callable[[str, int, int], None] | None,
    ) -> int:
        chunk_index = starting_chunk_index
        total = max(len(prepared_images), 1)
        for current_index, (prepared_image, caption) in enumerate(
            zip(prepared_images, captions, strict=True),
            start=1,
        ):
            artifact = self._save_artifact(
                document_model=document_model,
                data=prepared_image.preview_bytes,
                media_type=prepared_image.media_type,
            )
            asset = orm.RetrievalAssetModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_image.page_model,
                asset_type="image",
                label=prepared_image.label,
                bbox=prepared_image.bbox,
                text_content=prepared_image.surrounding_text[:2000],
                preview_artifact=artifact,
                metadata={"page_number": prepared_image.page_model.page_number, "summary": caption},
            )
            chunk = orm.RetrievalChunkModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_image.page_model,
                asset=asset,
                chunk_index=chunk_index,
                chunk_type="image",
                content=caption or prepared_image.label,
                metadata={
                    "page_number": prepared_image.page_model.page_number,
                    "asset_type": "image",
                    "asset_label": prepared_image.label,
                },
            )
            orm.RetrievalCitationModel.objects.create(
                id=str(uuid4()),
                document=document_model,
                page=prepared_image.page_model,
                chunk=chunk,
                asset=asset,
                preview_artifact=artifact,
                label=prepared_image.label,
                bbox=prepared_image.bbox,
                regions=[
                    {
                        "page_number": prepared_image.page_model.page_number,
                        "page_id": prepared_image.page_model.id,
                        "bbox": prepared_image.bbox,
                        "preview_artifact_id": artifact.id,
                    }
                ],
            )
            chunks.append(chunk)
            chunk_index += 1
            if progress_callback:
                progress_callback("summarizing", current_index, total)
        return chunk_index

    def _save_artifact(
        self,
        *,
        document_model: orm.DocumentModel,
        data: bytes,
        media_type: str,
    ) -> orm.RetrievalArtifactModel:
        artifact_id = str(uuid4())
        relative_path, byte_size = self.artifacts.save(
            document_id=document_model.id,
            artifact_id=artifact_id,
            data=data,
            media_type=media_type,
        )
        return orm.RetrievalArtifactModel.objects.create(
            id=artifact_id,
            document=document_model,
            media_type=media_type,
            relative_path=relative_path,
            byte_size=byte_size,
        )

    def _summarize_table(self, markdown: str, filename: str, page_number: int) -> str:
        return self._summarize_table_with_context(
            markdown=markdown,
            filename=filename,
            page_number=page_number,
            heading_context="",
        )

    def _summarize_table_with_context(
        self,
        *,
        markdown: str,
        filename: str,
        page_number: int,
        heading_context: str,
    ) -> str:
        prompt = (
            f"Summarize the following table from {filename} page {page_number} for retrieval. "
            "Describe what the table contains, any important headers, and key semantic cues "
            "in 2 concise sentences.\n\n"
            f"Nearby heading/context:\n{heading_context[:1000] or '[none]'}\n\n"
            f"{markdown[:12000]}"
        )
        try:
            return get_openai_client().complete(prompt, max_completion_tokens=512)
        except Exception as exc:
            logger.warning("Falling back to raw table markdown summary: %s", exc)
            return f"Table on page {page_number} extracted from {filename}."

    def _caption_image(self, filename: str, page_number: int, surrounding_text: str) -> str:
        prompt = (
            f"Create a concise retrieval caption for an image extracted from {filename} page "
            f"{page_number}. Use only the surrounding document text for context and avoid "
            f"hallucinating visual details.\n\nContext:\n{surrounding_text[:4000]}"
        )
        try:
            return get_openai_client().complete(prompt, max_completion_tokens=256)
        except Exception as exc:
            logger.warning("Falling back to generic image caption: %s", exc)
            return f"Image from page {page_number}."

    def _crop_preview(
        self,
        image: Image.Image,
        bbox: list[float],
        page_width: float,
        page_height: float,
        source_width: float,
        source_height: float,
    ) -> bytes:
        left, top, right, bottom = self._absolute_bbox(
            bbox,
            page_width,
            page_height,
            source_width,
            source_height,
        )
        crop = image.crop((left, top, right, bottom))
        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        return buffer.getvalue()

    def _absolute_bbox(
        self,
        bbox: list[float],
        page_width: float,
        page_height: float,
        source_width: float,
        source_height: float,
    ) -> list[float]:
        if not bbox:
            return [0.0, 0.0, page_width, page_height]
        x0, y0, x1, y1 = bbox
        return [
            x0 * page_width / max(source_width, 1.0),
            y0 * page_height / max(source_height, 1.0),
            x1 * page_width / max(source_width, 1.0),
            y1 * page_height / max(source_height, 1.0),
        ]

    def _should_stitch_table_fragments(self, previous: _TableFragment, current: _TableFragment) -> bool:
        if current.page_model.page_number != previous.page_model.page_number + 1:
            return False
        if current.column_count != previous.column_count:
            return False
        previous_header = self._header_signature(previous.markdown)
        current_header = self._header_signature(current.markdown)
        if not previous_header or previous_header != current_header:
            return False
        previous_bottom_ratio = previous.bbox[3] / max(previous.page_model.height, 1.0)
        current_top_ratio = current.bbox[1] / max(current.page_model.height, 1.0)
        return previous_bottom_ratio >= 0.7 and current_top_ratio <= 0.3

    def _merge_table_markdown(self, fragments: list[_TableFragment]) -> str:
        merged_lines = self._markdown_lines(fragments[0].markdown)
        header_signature = self._header_signature(fragments[0].markdown)
        for fragment in fragments[1:]:
            fragment_lines = self._markdown_lines(fragment.markdown)
            if self._header_signature(fragment.markdown) == header_signature and len(fragment_lines) >= 2:
                fragment_lines = fragment_lines[2:]
            merged_lines.extend(fragment_lines)
        return "\n".join(merged_lines)

    def _header_signature(self, markdown: str) -> tuple[str, ...]:
        lines = self._markdown_lines(markdown)
        if len(lines) < 2 or "|" not in lines[0]:
            return ()
        return tuple(cell.strip().lower() for cell in lines[0].strip("|").split("|"))

    def _markdown_lines(self, markdown: str) -> list[str]:
        return [line.rstrip() for line in markdown.strip().splitlines() if line.strip()]

    def _table_label(self, index: int, page_numbers: list[int]) -> str:
        if len(page_numbers) == 1:
            return f"Table {index} on page {page_numbers[0]}"
        return f"Table {index} on pages {page_numbers[0]}-{page_numbers[-1]}"

    def _truncate(self, text: str, *, max_chars: int) -> str:
        return text[:max_chars]

    def _table_heading_context(
        self,
        *,
        page: NormalizedPage | None,
        bbox: list[float] | None,
    ) -> str:
        if page is None or not bbox:
            return ""

        table_top = bbox[1]
        vertical_window_start = max(table_top - (page.height * 0.22), 0.0)
        candidate_lines: list[NormalizedLine] = []
        for line in page.lines:
            if not line.bbox:
                continue
            _, line_top, _, line_bottom = line.bbox
            if line_bottom > table_top:
                continue
            if line_top < vertical_window_start:
                continue
            candidate_lines.append(line)

        if not candidate_lines:
            fallback_lines = [line.text.strip() for line in page.lines[:8] if line.text.strip()]
            return "\n".join(fallback_lines[-4:])

        candidate_lines.sort(key=lambda line: (line.bbox[1], line.bbox[0]))
        condensed_lines = [line.text.strip() for line in candidate_lines if line.text.strip()]
        return "\n".join(condensed_lines[-5:])

    def _combine_table_text(self, prepared_table: _PreparedTable) -> str:
        context = prepared_table.heading_context.strip()
        if not context:
            return prepared_table.markdown
        return f"{context}\n\n{prepared_table.markdown}"

    def _table_chunk_content(self, prepared_table: _PreparedTable, summary: str) -> str:
        sections = []
        if prepared_table.heading_context.strip():
            sections.append(f"Table heading/context:\n{prepared_table.heading_context.strip()}")
        if summary.strip():
            sections.append(summary.strip())
        sections.append(prepared_table.markdown)
        return "\n\n".join(section for section in sections if section)


_service_instance: PDFRetrievalService | None = None


def get_pdf_retrieval_service() -> PDFRetrievalService:
    global _service_instance
    if _service_instance is None:
        _service_instance = PDFRetrievalService()
    return _service_instance
