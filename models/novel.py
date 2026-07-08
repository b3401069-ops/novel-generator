"""
小說資料庫模型
Novel Database Models
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from .database import Base


class NovelDB(Base):
    """小說資料表"""
    __tablename__ = "novels"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    summary = Column(Text)
    style = Column(String(50), default="modern")
    
    # 時間戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 關聯
    chapters = relationship("ChapterDB", back_populates="novel", cascade="all, delete-orphan")
    characters = relationship("CharacterDB", back_populates="novel", cascade="all, delete-orphan")

    def to_dict(self, chapter_count: int = 0, character_count: int = 0):
        """
        轉換為字典

        注意：chapter_count / character_count 由呼叫端明確傳入。
        不能在這裡取 len(self.chapters) — async SQLAlchemy 下 lazy 關聯
        未載入時會回傳空集合或報錯，導致列表顯示 0 章。
        """
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "style": self.style,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "chapter_count": chapter_count,
            "character_count": character_count,
        }


class ChapterDB(Base):
    """章節資料表"""
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(String(50), ForeignKey("novels.id"), nullable=False)
    number = Column(Integer, nullable=False)
    title = Column(String(200))
    summary = Column(Text)
    content = Column(Text)
    key_events = Column(JSON, default=list)
    foreshadowing = Column(JSON, default=list)
    version = Column(Integer, default=1)
    versions = Column(JSON, default=list)
    
    # 時間戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 關聯
    novel = relationship("NovelDB", back_populates="chapters")

    def to_dict(self):
        """轉換為字典"""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "number": self.number,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "key_events": self.key_events,
            "foreshadowing": self.foreshadowing,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CharacterDB(Base):
    """角色資料表"""
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    novel_id = Column(String(50), ForeignKey("novels.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    role = Column(String(50))  # 主角、配角、反派等
    traits = Column(JSON, default=list)
    relationships = Column(JSON, default=dict)
    status = Column(String(20), default="alive")
    
    # 時間戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 關聯
    novel = relationship("NovelDB", back_populates="characters")

    def to_dict(self):
        """轉換為字典"""
        return {
            "id": self.id,
            "novel_id": self.novel_id,
            "name": self.name,
            "description": self.description,
            "role": self.role,
            "traits": self.traits,
            "relationships": self.relationships,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
