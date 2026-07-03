"""資料庫模型"""
from .database import Base, get_db, init_db
from .novel import NovelDB, ChapterDB, CharacterDB

__all__ = ["Base", "get_db", "init_db", "NovelDB", "ChapterDB", "CharacterDB"]
