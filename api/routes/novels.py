"""
小說相關API
Novels API Routes
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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


class NovelMergeRequest(BaseModel):
    """合併小說請求"""
    novel_ids: List[str]        # 依合併順序排列
    new_title: str
    bridge: bool = True         # 是否用 AI 補足銜接情節
    new_summary: Optional[str] = None


# ──────────────────────────────────────────────
# API 端點
# ──────────────────────────────────────────────

@router.get("/", response_model=List[NovelResponse])
async def list_novels(db: AsyncSession = Depends(get_db)):
    """列出所有小說"""
    result = await db.execute(select(NovelDB).order_by(NovelDB.updated_at.desc()))
    novels = result.scalars().all()

    # 用聚合查詢統計章節/角色數（避免逐本 lazy load）
    chap_counts = dict(
        (await db.execute(
            select(ChapterDB.novel_id, func.count()).group_by(ChapterDB.novel_id)
        )).all()
    )
    char_counts = dict(
        (await db.execute(
            select(CharacterDB.novel_id, func.count()).group_by(CharacterDB.novel_id)
        )).all()
    )

    return [
        novel.to_dict(
            chapter_count=chap_counts.get(novel.id, 0),
            character_count=char_counts.get(novel.id, 0),
        )
        for novel in novels
    ]


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

        return novel_db.to_dict(
            chapter_count=len(novel.chapters),
            character_count=len(novel.characters),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge", response_model=NovelResponse)
async def merge_novels(
    request: NovelMergeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    合併多部短篇成一部新的長篇小說

    依 novel_ids 順序串接章節（重新編號），角色去重（依名字），
    可選用 AI 在各短篇之間補足「銜接章節」大綱。原本的小說保持不變。
    """
    if len(request.novel_ids) < 2:
        raise HTTPException(status_code=400, detail="至少選擇兩部小說")

    # 依合併順序載入各來源小說 + 章節 + 角色
    sources = []
    for nid in request.novel_ids:
        novel_db = (await db.execute(
            select(NovelDB).where(NovelDB.id == nid)
        )).scalar_one_or_none()
        if not novel_db:
            raise HTTPException(status_code=404, detail=f"小說不存在: {nid}")

        chaps = (await db.execute(
            select(ChapterDB).where(ChapterDB.novel_id == nid).order_by(ChapterDB.number)
        )).scalars().all()
        chars = (await db.execute(
            select(CharacterDB).where(CharacterDB.novel_id == nid)
        )).scalars().all()
        sources.append((novel_db, chaps, chars))

    try:
        # 建立新長篇
        new_id = f"novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        style = sources[0][0].style
        summary = request.new_summary or (
            "由以下短篇合併而成：" + "、".join(s[0].title for s in sources)
        )
        new_novel = NovelDB(id=new_id, title=request.new_title, summary=summary, style=style)
        db.add(new_novel)

        # 角色去重（依名字）
        seen_names = set()
        for _, _, chars in sources:
            for c in chars:
                if c.name in seen_names:
                    continue
                seen_names.add(c.name)
                db.add(CharacterDB(
                    novel_id=new_id,
                    name=c.name,
                    description=c.description,
                    role=c.role,
                    traits=c.traits or [],
                    relationships=c.relationships or {},
                    status=c.status,
                ))

        # 章節串接（重新編號），並在短篇之間插入銜接章節
        num = 0
        for i, (novel_db, chaps, _) in enumerate(sources):
            # 除第一部外，前面插入一個 AI 銜接章節
            if i > 0 and request.bridge:
                prev_novel, prev_chaps, _ = sources[i - 1]
                prev_tail_chap = prev_chaps[-1] if prev_chaps else None
                next_head_chap = chaps[0] if chaps else None
                prev_tail = ""
                if prev_tail_chap:
                    prev_tail = (prev_tail_chap.content or prev_tail_chap.summary or "")[:800]
                next_head = ""
                if next_head_chap:
                    next_head = (next_head_chap.content or next_head_chap.summary or "")[:800]

                bridge = await engine.generate_bridge(
                    prev_title=prev_novel.title,
                    prev_tail=prev_tail,
                    next_title=novel_db.title,
                    next_head=next_head,
                    style=style,
                )
                num += 1
                db.add(ChapterDB(
                    novel_id=new_id,
                    number=num,
                    title=f"【銜接】{bridge['title']}",
                    summary=bridge["summary"],
                    key_events=bridge.get("key_events", []),
                ))

            # 串接這一部的章節
            for chap in chaps:
                num += 1
                db.add(ChapterDB(
                    novel_id=new_id,
                    number=num,
                    title=chap.title,
                    summary=chap.summary,
                    content=chap.content,
                    key_events=chap.key_events or [],
                    foreshadowing=chap.foreshadowing or [],
                ))

        await db.commit()

        return new_novel.to_dict(
            chapter_count=num,
            character_count=len(seen_names),
        )

    except HTTPException:
        raise
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
        **novel.to_dict(
            chapter_count=len(chapters),
            character_count=len(characters),
        ),
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
