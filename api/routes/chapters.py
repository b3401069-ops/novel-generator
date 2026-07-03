"""
章節相關API
Chapters API Routes
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from models.database import get_db
from models.novel import NovelDB, ChapterDB
from core.engine import NovelEngine
from config.settings import get_settings


router = APIRouter()
settings = get_settings()
engine = NovelEngine(settings)


# ──────────────────────────────────────────────
# Pydantic 模型
# ──────────────────────────────────────────────

class ChapterGenerateRequest(BaseModel):
    """生成章節請求"""
    novel_id: str
    chapter_number: int
    previous_summary: Optional[str] = None


class ChapterEditRequest(BaseModel):
    """編輯章節請求"""
    novel_id: str
    chapter_number: int
    instruction: str
    paragraph_id: Optional[int] = None


class ChapterRollbackRequest(BaseModel):
    """回滾章節請求"""
    novel_id: str
    chapter_number: int
    version: int


class ChapterResponse(BaseModel):
    """章節回應"""
    id: int
    novel_id: str
    number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    key_events: List[str] = []
    foreshadowing: List[str] = []
    version: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ──────────────────────────────────────────────
# API 端點
# ──────────────────────────────────────────────

@router.get("/{novel_id}", response_model=List[ChapterResponse])
async def list_chapters(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """列出小說的所有章節"""
    result = await db.execute(
        select(ChapterDB)
        .where(ChapterDB.novel_id == novel_id)
        .order_by(ChapterDB.number)
    )
    chapters = result.scalars().all()
    return [chap.to_dict() for chap in chapters]


@router.get("/{novel_id}/{chapter_number}", response_model=ChapterResponse)
async def get_chapter(
    novel_id: str,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
):
    """獲取特定章節"""
    result = await db.execute(
        select(ChapterDB).where(
            ChapterDB.novel_id == novel_id,
            ChapterDB.number == chapter_number,
        )
    )
    chapter = result.scalar_one_or_none()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="章節不存在")
    
    return chapter.to_dict()


@router.post("/generate", response_model=ChapterResponse)
async def generate_chapter(
    request: ChapterGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    生成章節內容
    
    根據章節大綱生成完整內容
    """
    # 獲取小說
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == request.novel_id)
    )
    novel_db = result.scalar_one_or_none()
    
    if not novel_db:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    # 獲取章節
    chap_result = await db.execute(
        select(ChapterDB).where(
            ChapterDB.novel_id == request.novel_id,
            ChapterDB.number == request.chapter_number,
        )
    )
    chapter_db = chap_result.scalar_one_or_none()
    
    if not chapter_db:
        raise HTTPException(status_code=404, detail="章節不存在")
    
    try:
        # 轉換為引擎對象
        from core.engine import Novel, Chapter, Character
        
        # 獲取所有章節
        all_chaps_result = await db.execute(
            select(ChapterDB)
            .where(ChapterDB.novel_id == request.novel_id)
            .order_by(ChapterDB.number)
        )
        all_chapters = all_chaps_result.scalars().all()
        
        # 獲取所有角色
        from models.novel import CharacterDB
        chars_result = await db.execute(
            select(CharacterDB).where(CharacterDB.novel_id == request.novel_id)
        )
        characters = chars_result.scalars().all()
        
        # 構建小說對象
        novel = Novel(
            id=novel_db.id,
            title=novel_db.title,
            summary=novel_db.summary,
            style=novel_db.style,
            characters=[
                Character(
                    name=char.name,
                    description=char.description,
                    role=char.role,
                    traits=char.traits or [],
                )
                for char in characters
            ],
            chapters=[
                Chapter(
                    number=chap.number,
                    title=chap.title,
                    summary=chap.summary,
                    content=chap.content,
                    key_events=chap.key_events or [],
                    foreshadowing=chap.foreshadowing or [],
                )
                for chap in all_chapters
            ],
        )
        
        # 生成章節
        content = await engine.generate_chapter(
            novel=novel,
            chapter_number=request.chapter_number,
            previous_summary=request.previous_summary,
        )
        
        # 更新資料庫
        chapter_db.content = content
        chapter_db.version += 1
        chapter_db.versions = chapter_db.versions or []
        chapter_db.versions.append({
            "version": chapter_db.version,
            "content": content,
        })
        
        await db.commit()
        
        return chapter_db.to_dict()
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit", response_model=ChapterResponse)
async def edit_chapter(
    request: ChapterEditRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    編輯章節
    
    根據修改要求更新章節內容
    """
    # 獲取小說和章節
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == request.novel_id)
    )
    novel_db = result.scalar_one_or_none()
    
    if not novel_db:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    chap_result = await db.execute(
        select(ChapterDB).where(
            ChapterDB.novel_id == request.novel_id,
            ChapterDB.number == request.chapter_number,
        )
    )
    chapter_db = chap_result.scalar_one_or_none()
    
    if not chapter_db:
        raise HTTPException(status_code=404, detail="章節不存在")
    
    if not chapter_db.content:
        raise HTTPException(status_code=400, detail="章節尚未生成，無法編輯")
    
    try:
        # 轉換為引擎對象
        from core.engine import Novel, Chapter, Character
        
        # 獲取所有章節
        all_chaps_result = await db.execute(
            select(ChapterDB)
            .where(ChapterDB.novel_id == request.novel_id)
            .order_by(ChapterDB.number)
        )
        all_chapters = all_chaps_result.scalars().all()
        
        # 獲取所有角色
        from models.novel import CharacterDB
        chars_result = await db.execute(
            select(CharacterDB).where(CharacterDB.novel_id == request.novel_id)
        )
        characters = chars_result.scalars().all()
        
        # 構建小說對象
        novel = Novel(
            id=novel_db.id,
            title=novel_db.title,
            summary=novel_db.summary,
            style=novel_db.style,
            characters=[
                Character(
                    name=char.name,
                    description=char.description,
                    role=char.role,
                    traits=char.traits or [],
                )
                for char in characters
            ],
            chapters=[
                Chapter(
                    number=chap.number,
                    title=chap.title,
                    summary=chap.summary,
                    content=chap.content,
                    key_events=chap.key_events or [],
                    foreshadowing=chap.foreshadowing or [],
                )
                for chap in all_chapters
            ],
        )
        
        # 編輯章節
        content = await engine.edit_chapter(
            novel=novel,
            chapter_number=request.chapter_number,
            instruction=request.instruction,
            paragraph_id=request.paragraph_id,
        )
        
        # 更新資料庫
        chapter_db.content = content
        chapter_db.version += 1
        chapter_db.versions = chapter_db.versions or []
        chapter_db.versions.append({
            "version": chapter_db.version,
            "content": content,
            "instruction": request.instruction,
        })
        
        await db.commit()
        
        return chapter_db.to_dict()
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback", response_model=ChapterResponse)
async def rollback_chapter(
    request: ChapterRollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    回滾章節
    
    將章節回滾到指定版本
    """
    chap_result = await db.execute(
        select(ChapterDB).where(
            ChapterDB.novel_id == request.novel_id,
            ChapterDB.number == request.chapter_number,
        )
    )
    chapter_db = chap_result.scalar_one_or_none()
    
    if not chapter_db:
        raise HTTPException(status_code=404, detail="章節不存在")
    
    # 查找指定版本
    versions = chapter_db.versions or []
    target_version = None
    
    for v in versions:
        if v.get("version") == request.version:
            target_version = v
            break
    
    if not target_version:
        raise HTTPException(status_code=404, detail=f"找不到版本 {request.version}")
    
    # 回滾
    chapter_db.content = target_version["content"]
    chapter_db.version = request.version
    
    await db.commit()
    
    return chapter_db.to_dict()
