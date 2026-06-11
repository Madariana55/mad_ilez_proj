"""
models.py — sqlalchemy orm-модели для хранения результатов ocr
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, Float, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()


class ProcessingStatus(enum.Enum):
    PENDING   = "pending"
    PROCESSING = "processing"
    DONE      = "done"
    ERROR     = "error"


class Document(Base):
    __tablename__ = "documents"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    filename    = Column(String(255), nullable=False)
    filepath    = Column(String(512), nullable=False)
    file_size   = Column(Integer)                       # байты
    page_count  = Column(Integer, default=0)
    language    = Column(String(50), default="rus+eng")
    status      = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_msg   = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pages = relationship("Page", back_populates="document",
                         cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":          self.id,
            "filename":    self.filename,
            "file_size":   self.file_size,
            "page_count":  self.page_count,
            "language":    self.language,
            "status":      self.status.value,
            "error_msg":   self.error_msg,
            "created_at":  self.created_at.isoformat() if self.created_at else None,
        }


class Page(Base):
    __tablename__ = "pages"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    document_id  = Column(Integer, ForeignKey("documents.id"), nullable=False)
    page_number  = Column(Integer, nullable=False)
    raw_text     = Column(Text, default="")
    char_count   = Column(Integer, default=0)
    word_count   = Column(Integer, default=0)
    confidence   = Column(Float, default=0.0)   # средняя уверенность tesseract, 0–100
    ocr_engine   = Column(String(50), default="tesseract")
    processed_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="pages")

    def to_dict(self):
        return {
            "id":           self.id,
            "document_id":  self.document_id,
            "page_number":  self.page_number,
            "raw_text":     self.raw_text,
            "char_count":   self.char_count,
            "word_count":   self.word_count,
            "confidence":   round(self.confidence, 2),
            "ocr_engine":   self.ocr_engine,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


def init_db(db_path: str = "ocr_storage.db"):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session
