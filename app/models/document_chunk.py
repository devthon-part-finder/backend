# ==============================================================================
# Document Chunk Model - PDF Chunk Embeddings for RAG
# ==============================================================================
# This model stores vectorized chunks of uploaded PDF documents.
# Used by the Reverse Catalog Search feature for RAG-based part identification.
#
# Flow:
#   1. User uploads PDF → stored in Supabase file storage
#   2. PDF is parsed into text chunks
#   3. Each chunk is embedded using Gemini → stored here with vector
#   4. User's description is also embedded
#   5. Cosine similarity between description and chunks → find relevant parts
#
# pgvector is used for efficient vector similarity search.
# ==============================================================================

from sqlmodel import SQLModel, Field, Column as SMColumn
from sqlalchemy import Column, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from pgvector.sqlalchemy import Vector
from typing import Optional
from datetime import datetime, timezone
import uuid

from app.core.config import settings


class DocumentChunk(SQLModel, table=True):
    """
    Stores a single chunk of a PDF document with its vector embedding.
    
    Each chunk is a segment of the PDF text, vectorized for similarity search.
    Linked to a Chat to associate chunks with the search session.
    
    Table name: 'document_chunks'
    """
    
    __tablename__ = "document_chunks"
    
    # Primary key (UUID)
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(
            PgUUID(as_uuid=False),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        ),
        description="Unique identifier for the chunk"
    )
    
    # Foreign key to chats table (UUID)
    chat_id: str = Field(
        sa_column=Column(
            PgUUID(as_uuid=False),
            ForeignKey("chats.id"),
            nullable=False,
            index=True,
        ),
        description="ID of the chat/search session this chunk belongs to"
    )
    
    # Chunk content
    chunk_text: str = Field(
        ...,
        sa_column=Column(Text),
        description="The text content of this chunk"
    )
    
    # Chunk metadata
    chunk_index: int = Field(
        default=0,
        description="Index/position of this chunk in the document"
    )
    
    page_number: Optional[int] = Field(
        default=None,
        description="Page number this chunk came from"
    )
    
    # Vector embedding (using pgvector)
    # Gemini gemini-embedding-001 produces 768-dimensional vectors
    embedding: Optional[list[float]] = Field(
        default=None,
        sa_column=Column(Vector(768)),
        description="Vector embedding of the chunk text (768 dimensions)"
    )
    
    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the chunk was created"
    )
