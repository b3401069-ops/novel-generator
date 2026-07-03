"""
小說相關API
Novels API Routes
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from models.database import get_db
from models.novel import NovelDB, ChapterDB, CharacterDB
from core.engine import NovelEngine
from config.settings import get_settings


router = APIRouter()
settings = get_settings()
engine = NovelEngine(settings)


# ──────────────────────────────────────────────
# Pydantic 模型
# ──────────────────────────────────────────────

class NovelCreate(BaseModel):
    """創建小說請求"""
    brief_outline: str
    style: str = "modern"
    chapter_count: int = 10
    words_per_chapter: int = 3000


class NovelResponse(BaseModel):
    """小說回應"""
    id: str
    title: str
    summary: str
    style: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    chapter_count: int = 0
    character_count: int = 0


class NovelDetailResponse(BaseModel):
    """小說詳細回應"""
    id: str
    title: str
    summary: str
    style: str
    characters: List[dict]
    chapters: List[dict]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ──────────────────────────────────────────────
# API 端點
# ──────────────────────────────────────────────

@router.get("/", response_model=List[NovelResponse])
async def list_novels(db: AsyncSession = Depends(get_db)):
    """列出所有小說"""
    result = await db.execute(select(NovelDB).order_by(NovelDB.updated_at.desc()))
    novels = result.scalars().all()
    return [novel.to_dict() for novel in novels]


@router.post("/", response_model=NovelResponse)
async def create_novel(
    request: NovelCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    創建新小說
    
    根據簡略大綱生成小說結構
    """
    try:
        # 生成小說大綱
        novel = await engine.generate_outline(
            brief_outline=request.brief_outline,
            style=request.style,
            chapter_count=request.chapter_count,
            words_per_chapter=request.words_per_chapter,
        )
        
        # 保存到資料庫
        novel_db = NovelDB(
            id=novel.id,
            title=novel.title,
            summary=novel.summary,
            style=novel.style,
        )
        db.add(novel_db)
        
        # 保存角色
        for char in novel.characters:
            char_db = CharacterDB(
                novel_id=novel.id,
                name=char.name,
                description=char.description,
                role=char.role,
                traits=char.traits,
            )
            db.add(char_db)
        
        # 保存章節
        for chap in novel.chapters:
            chap_db = ChapterDB(
                novel_id=novel.id,
                number=chap.number,
                title=chap.title,
                summary=chap.summary,
                key_events=chap.key_events,
                foreshadowing=chap.foreshadowing,
            )
            db.add(chap_db)
        
        await db.commit()
        
        return novel_db.to_dict()
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{novel_id}", response_model=NovelDetailResponse)
async def get_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """獲取小說詳情"""
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == novel_id)
    )
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    # 獲取角色
    chars_result = await db.execute(
        select(CharacterDB).where(CharacterDB.novel_id == novel_id)
    )
    characters = chars_result.scalars().all()
    
    # 獲取章節
    chaps_result = await db.execute(
        select(ChapterDB)
        .where(ChapterDB.novel_id == novel_id)
        .order_by(ChapterDB.number)
    )
    chapters = chaps_result.scalars().all()
    
    return {
        **novel.to_dict(),
        "characters": [char.to_dict() for char in characters],
        "chapters": [chap.to_dict() for chap in chapters],
    }


@router.delete("/{novel_id}")
async def delete_novel(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """刪除小說"""
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == novel_id)
    )
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    await db.delete(novel)
    await db.commit()
    
    return {"message": "已刪除"}
