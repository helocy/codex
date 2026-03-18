from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from datetime import datetime
from app.core.database import Base
import enum


class FileType(str, enum.Enum):
    TEXT = "text"
    PDF = "pdf"
    WORD = "word"
    MARKDOWN = "markdown"
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    file_type = Column(Enum(FileType), nullable=False)
    file_path = Column(String(512))
    file_size = Column(Integer)
    # PageIndex 树形索引：层级目录结构，格式见 page_index_service.py
    tree_index = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float))
    chunk_index = Column(Integer)
    # 所属树形节点 ID（对应 tree_index 中的 node_id）
    section_id = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
