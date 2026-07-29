"""
章節相關API
Chapters API Routes
"""

import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from models.database import get_db, async_session
from models.novel import NovelDB, ChapterDB, CharacterDB
from core.engine import NovelEngine, Novel, Chapter, Character, PlotThread
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


def _save_version(chapter_db: ChapterDB, content: str, instruction: Optional[str] = None) -> None:
    """
    寫入新版本。

    注意：versions 是 JSON 欄位，必須整個重新賦值（而非原地 append），
    否則 SQLAlchemy 偵測不到變更、歷史不會存進資料庫。
    版本號取歷史最大值 +1，避免回滾後再編輯產生重複版本號。
    """
    versions = list(chapter_db.versions or [])
    new_version = max((v.get("version", 0) for v in versions), default=0) + 1
    entry = {
        "version": new_version,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if instruction:
        entry["instruction"] = instruction
    versions.append(entry)

    chapter_db.content = content
    chapter_db.version = new_version
    chapter_db.versions = versions


async def _load_engine_novel(
    db: AsyncSession,
    novel_id: str,
) -> Tuple[Novel, Dict[int, ChapterDB], NovelDB]:
    """
    從資料庫載入小說並轉換為引擎物件。

    Returns:
        (引擎 Novel 物件, {章節編號: ChapterDB}, NovelDB 物件)
    """
    result = await db.execute(select(NovelDB).where(NovelDB.id == novel_id))
    novel_db = result.scalar_one_or_none()
    if not novel_db:
        raise HTTPException(status_code=404, detail="小說不存在")

    chaps_result = await db.execute(
        select(ChapterDB)
        .where(ChapterDB.novel_id == novel_id)
        .order_by(ChapterDB.number)
    )
    all_chapters = chaps_result.scalars().all()

    chars_result = await db.execute(
        select(CharacterDB).where(CharacterDB.novel_id == novel_id)
    )
    characters = chars_result.scalars().all()

    # 解析 plot_threads（SQLite JSON 欄位可能返回字串或已解析物件）
    raw_threads = novel_db.plot_threads or []
    if isinstance(raw_threads, str):
        import json
        raw_threads = json.loads(raw_threads)
    plot_threads = [
        PlotThread(id=t.get("id", ""), name=t.get("name", ""), summary=t.get("summary", ""))
        for t in raw_threads
    ]

    novel = Novel(
        id=novel_db.id,
        title=novel_db.title,
        summary=novel_db.summary,
        style=novel_db.style,
        running_summary=novel_db.running_summary or "",
        unresolved_foreshadowing=novel_db.unresolved_foreshadowing or [],
        plot_threads=plot_threads,
        characters=[
            Character(
                name=char.name,
                description=char.description,
                role=char.role,
                traits=char.traits or [],
                status=char.status or "alive",
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
                thread_id=chap.thread_id,
            )
            for chap in all_chapters
        ],
    )
    return novel, {chap.number: chap for chap in all_chapters}, novel_db


def _sse(data: dict) -> str:
    """編碼單一 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _persist_novel_state(
    novel_db: NovelDB,
    novel: Novel,
    db: AsyncSession,
) -> None:
    """
    持久化 P0+P1+P2 更新的小說狀態到資料庫。

    每章生成完成後，引擎會更新 running_summary、unresolved_foreshadowing
    與角色狀態。此函數將這些記憶體變更寫回資料庫。
    """
    novel_db.running_summary = novel.running_summary
    novel_db.unresolved_foreshadowing = novel.unresolved_foreshadowing

    # 持久化角色狀態更新
    try:
        chars_result = await db.execute(
            select(CharacterDB).where(CharacterDB.novel_id == novel.id)
        )
        char_dbs = {c.name: c for c in chars_result.scalars().all()}
        for char in novel.characters:
            db_char = char_dbs.get(char.name)
            if db_char:
                db_char.description = char.description
                db_char.status = char.status
    except Exception:
        pass  # 角色同步失敗不阻塞章節存檔


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",  # 避免反向代理緩衝，讓串流即時送達
}


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
    thread_id: Optional[str] = None  # P4
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
    novel, chapters_by_number, novel_db = await _load_engine_novel(db, request.novel_id)
    chapter_db = chapters_by_number.get(request.chapter_number)

    if not chapter_db:
        raise HTTPException(status_code=404, detail="章節不存在")

    try:
        # 持久化包裝函式（閉包捕捉 novel_db, db）
        async def persist(novel: Novel, chapter_number: int) -> None:
            await _persist_novel_state(novel_db, novel, db)

        # 生成章節（含 P0+P1+P2 狀態更新 + 自動持久化回調）
        content = await engine.generate_chapter(
            novel=novel,
            chapter_number=request.chapter_number,
            previous_summary=request.previous_summary,
            on_complete=persist,
        )
        
        # 更新資料庫（章節內容版本）
        _save_version(chapter_db, content)
        
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
    novel, chapters_by_number, _ = await _load_engine_novel(db, request.novel_id)
    chapter_db = chapters_by_number.get(request.chapter_number)

    if not chapter_db:
        raise HTTPException(status_code=404, detail="章節不存在")

    if not chapter_db.content:
        raise HTTPException(status_code=400, detail="章節尚未生成，無法編輯")

    try:
        # 編輯章節
        content = await engine.edit_chapter(
            novel=novel,
            chapter_number=request.chapter_number,
            instruction=request.instruction,
            paragraph_id=request.paragraph_id,
        )
        
        # 更新資料庫
        _save_version(chapter_db, content, instruction=request.instruction)

        await db.commit()
        
        return chapter_db.to_dict()
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/stream")
async def generate_chapter_stream(request: ChapterGenerateRequest):
    """
    串流生成章節內容（SSE）

    事件格式（每行 data: JSON）：
    - {"type": "delta", "text": "..."}      生成中的文字片段
    - {"type": "done", "chapter": {...}}    完成，含已存檔的章節資料
    - {"type": "error", "detail": "..."}    發生錯誤
    """
    async def event_stream():
        # 串流回應期間需要自行管理 session，不能用 Depends(get_db)
        try:
            async with async_session() as db:
                novel, chapters_by_number, novel_db = await _load_engine_novel(db, request.novel_id)
                chapter_db = chapters_by_number.get(request.chapter_number)
                if not chapter_db:
                    yield _sse({"type": "error", "detail": "章節不存在"})
                    return

                # 持久化包裝函式
                async def persist(novel, ch_num):
                    await _persist_novel_state(novel_db, novel, db)

                async for event in engine.generate_chapter_stream(
                    novel=novel,
                    chapter_number=request.chapter_number,
                    previous_summary=request.previous_summary,
                    on_complete=persist,
                ):
                    if event["type"] == "done":
                        _save_version(chapter_db, event["content"])
                        await db.commit()
                        yield _sse({"type": "done", "chapter": chapter_db.to_dict()})
                    else:
                        yield _sse(event)

                # P0+P1+P2 已由 engine 內部 + on_complete 回調完成持久化
                await db.commit()
        except HTTPException as e:
            yield _sse({"type": "error", "detail": e.detail})
        except Exception as e:
            yield _sse({"type": "error", "detail": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/edit/stream")
async def edit_chapter_stream(request: ChapterEditRequest):
    """
    串流編輯章節（SSE）

    事件格式同 /generate/stream。
    """
    async def event_stream():
        try:
            async with async_session() as db:
                novel, chapters_by_number, _ = await _load_engine_novel(db, request.novel_id)
                chapter_db = chapters_by_number.get(request.chapter_number)
                if not chapter_db:
                    yield _sse({"type": "error", "detail": "章節不存在"})
                    return
                if not chapter_db.content:
                    yield _sse({"type": "error", "detail": "章節尚未生成，無法編輯"})
                    return

                async for event in engine.edit_chapter_stream(
                    novel=novel,
                    chapter_number=request.chapter_number,
                    instruction=request.instruction,
                    paragraph_id=request.paragraph_id,
                ):
                    if event["type"] == "done":
                        _save_version(
                            chapter_db, event["content"],
                            instruction=request.instruction,
                        )
                        await db.commit()
                        yield _sse({"type": "done", "chapter": chapter_db.to_dict()})
                    else:
                        yield _sse(event)
        except HTTPException as e:
            yield _sse({"type": "error", "detail": e.detail})
        except Exception as e:
            yield _sse({"type": "error", "detail": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


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


# ──────────────────────────────────────────────
# P3 — 全書最終審閱
# ──────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """審閱請求"""
    novel_id: str


@router.post("/review")
async def review_novel(
    request: ReviewRequest,
):
    """
    P3 — 全書最終審閱

    載入已完成的小說，執行全面審閱：
    - 角色狀態一致性
    - 伏筆回收
    - 時間線
    - 設定一致性

    返回審閱報告 JSON。
    """
    async with async_session() as db:
        novel, _, _ = await _load_engine_novel(db, request.novel_id)

    result = await engine.final_review(novel)
    return result
