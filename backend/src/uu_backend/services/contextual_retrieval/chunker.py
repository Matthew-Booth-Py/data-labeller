"""Document chunking using LangChain text splitters."""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Chunk


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
