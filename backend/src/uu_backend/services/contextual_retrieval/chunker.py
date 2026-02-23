"""Document chunking using LangChain text splitters."""

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Chunk


class PageAwareChunker:
    """
    One chunk per page, using '## Page N' markers embedded in document content.

    Pages that exceed max_page_size are sub-split with RecursiveCharacterTextSplitter
    so the vector store never receives an oversized chunk. Pages that are within
    the limit are kept intact, which is ideal for structured single-page documents
    like ACORD 25 certificates where every table row must stay together.
    """

    PAGE_PATTERN = re.compile(r"(?=## Page \d+)", re.MULTILINE)
    PAGE_NUM_PATTERN = re.compile(r"## Page (\d+)")

    def __init__(
        self,
        max_page_size: int = 8000,
        fallback_chunk_size: int = 2000,
        fallback_chunk_overlap: int = 200,
    ):
        self.max_page_size = max_page_size
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=fallback_chunk_size,
            chunk_overlap=fallback_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def chunk_with_metadata(
        self,
        document_id: str,
        content: str,
        metadata: dict,
    ) -> list["Chunk"]:
        if not content or not content.strip():
            return []

        raw_pages = [p.strip() for p in self.PAGE_PATTERN.split(content) if p.strip()]

        # If no page markers found fall back to treating the whole content as page 1
        if not raw_pages:
            raw_pages = [content]

        chunks = []
        idx = 0
        for raw_page in raw_pages:
            # Extract the page number from the marker if present
            m = self.PAGE_NUM_PATTERN.match(raw_page)
            page_num = int(m.group(1)) if m else (idx + 1)

            if len(raw_page) <= self.max_page_size:
                chunks.append(
                    Chunk(
                        doc_id=document_id,
                        index=idx,
                        text=raw_page,
                        metadata={
                            **metadata,
                            "page_number": page_num,
                            "chunk_size": len(raw_page),
                        },
                    )
                )
                idx += 1
            else:
                sub_texts = self._splitter.split_text(raw_page)
                for sub_text in sub_texts:
                    chunks.append(
                        Chunk(
                            doc_id=document_id,
                            index=idx,
                            text=sub_text,
                            metadata={
                                **metadata,
                                "page_number": page_num,
                                "chunk_size": len(sub_text),
                            },
                        )
                    )
                    idx += 1

        for chunk in chunks:
            chunk.metadata["total_chunks"] = len(chunks)

        return chunks

    def chunk(self, document_id: str, content: str) -> list["Chunk"]:
        return self.chunk_with_metadata(document_id, content, {})


class DocumentChunker:
    """
    Split documents into overlapping chunks.
    
    Uses RecursiveCharacterTextSplitter which tries to split on natural
    boundaries (paragraphs, sentences) before falling back to character splits.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.separators,
            length_function=len,
        )

    def chunk(self, document_id: str, content: str) -> list[Chunk]:
        """
        Split document content into chunks.
        
        Args:
            document_id: Unique identifier for the document
            content: Full text content of the document
            
        Returns:
            List of Chunk objects
        """
        if not content or not content.strip():
            return []

        texts = self.splitter.split_text(content)
        
        return [
            Chunk(
                doc_id=document_id,
                index=i,
                text=text,
                metadata={
                    "chunk_size": len(text),
                    "total_chunks": len(texts),
                },
            )
            for i, text in enumerate(texts)
        ]

    def chunk_with_metadata(
        self,
        document_id: str,
        content: str,
        metadata: dict,
    ) -> list[Chunk]:
        """
        Split document and attach metadata to each chunk.
        
        Args:
            document_id: Unique identifier for the document
            content: Full text content
            metadata: Metadata to attach to each chunk
            
        Returns:
            List of Chunk objects with metadata
        """
        chunks = self.chunk(document_id, content)
        
        for chunk in chunks:
            chunk.metadata.update(metadata)
        
        return chunks
