"""
匯出/匯入 API
Export/Import API Routes
"""

import json
from typing import Optional
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.database import get_db
from models.novel import NovelDB, ChapterDB, CharacterDB


router = APIRouter()


@router.get("/{novel_id}/json")
async def export_novel_json(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    匯出小說為 JSON 格式
    
    可用於備份或遷移
    """
    # 獲取小說
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
    
    # 構建匯出資料
    export_data = {
        "format": "novel-forge-v1",
        "exported_at": datetime.now().isoformat(),
        "novel": {
            "id": novel.id,
            "title": novel.title,
            "summary": novel.summary,
            "style": novel.style,
            "created_at": novel.created_at.isoformat() if novel.created_at else None,
            "updated_at": novel.updated_at.isoformat() if novel.updated_at else None,
        },
        "characters": [
            {
                "name": char.name,
                "description": char.description,
                "role": char.role,
                "traits": char.traits or [],
                "relationships": char.relationships or {},
                "status": char.status,
            }
            for char in characters
        ],
        "chapters": [
            {
                "number": chap.number,
                "title": chap.title,
                "summary": chap.summary,
                "content": chap.content,
                "key_events": chap.key_events or [],
                "foreshadowing": chap.foreshadowing or [],
                "version": chap.version,
            }
            for chap in chapters
        ],
    }
    
    return export_data


@router.get("/{novel_id}/txt")
async def export_novel_txt(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    匯出小說為純文字格式
    
    方便閱讀
    """
    # 獲取小說
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == novel_id)
    )
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    # 獲取章節
    chaps_result = await db.execute(
        select(ChapterDB)
        .where(ChapterDB.novel_id == novel_id)
        .order_by(ChapterDB.number)
    )
    chapters = chaps_result.scalars().all()
    
    # 構建文字內容
    lines = []
    lines.append(f"{'='*50}")
    lines.append(f"  {novel.title}")
    lines.append(f"{'='*50}")
    lines.append("")
    lines.append(f"摘要：{novel.summary}")
    lines.append("")
    lines.append(f"{'─'*50}")
    lines.append("")
    
    for chap in chapters:
        if chap.content:
            lines.append(f"第{chap.number}章 {chap.title or ''}")
            lines.append("")
            lines.append(chap.content)
            lines.append("")
            lines.append(f"{'─'*50}")
            lines.append("")
    
    content = "\n".join(lines)
    
    # 建立臨時檔案
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{novel.title}_{timestamp}.txt"
    temp_path = Path("/tmp") / filename
    
    temp_path.write_text(content, encoding="utf-8")
    
    return FileResponse(
        path=str(temp_path),
        filename=filename,
        media_type="text/plain; charset=utf-8",
    )


@router.get("/{novel_id}/markdown")
async def export_novel_markdown(
    novel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    匯出小說為 Markdown 格式
    """
    # 獲取小說
    result = await db.execute(
        select(NovelDB).where(NovelDB.id == novel_id)
    )
    novel = result.scalar_one_or_none()
    
    if not novel:
        raise HTTPException(status_code=404, detail="小說不存在")
    
    # 獲取章節
    chaps_result = await db.execute(
        select(ChapterDB)
        .where(ChapterDB.novel_id == novel_id)
        .order_by(ChapterDB.number)
    )
    chapters = chaps_result.scalars().all()
    
    # 構建 Markdown
    lines = []
    lines.append(f"# {novel.title}")
    lines.append("")
    lines.append(f"> {novel.summary}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    for chap in chapters:
        if chap.content:
            lines.append(f"## 第{chap.number}章 {chap.title or ''}")
            lines.append("")
            lines.append(chap.content)
            lines.append("")
            lines.append("---")
            lines.append("")
    
    content = "\n".join(lines)
    
    # 建立臨時檔案
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{novel.title}_{timestamp}.md"
    temp_path = Path("/tmp") / filename
    
    temp_path.write_text(content, encoding="utf-8")
    
    return FileResponse(
        path=str(temp_path),
        filename=filename,
        media_type="text/markdown; charset=utf-8",
    )


@router.post("/import")
async def import_novel(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    匯入小說
    
    從 JSON 格式匯入
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="只支援 JSON 格式")
    
    try:
        content = await file.read()
        data = json.loads(content)
        
        # 驗證格式
        if data.get("format") != "novel-forge-v1":
            raise HTTPException(status_code=400, detail="不支援的格式")
        
        novel_data = data.get("novel", {})
        
        # 建立小說
        novel_db = NovelDB(
            id=f"novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=novel_data.get("title", "匯入的小說"),
            summary=novel_data.get("summary", ""),
            style=novel_data.get("style", "modern"),
        )
        db.add(novel_db)
        
        # 建立角色
        for char_data in data.get("characters", []):
            char_db = CharacterDB(
                novel_id=novel_db.id,
                name=char_data.get("name", ""),
                description=char_data.get("description", ""),
                role=char_data.get("role", "配角"),
                traits=char_data.get("traits", []),
                relationships=char_data.get("relationships", {}),
                status=char_data.get("status", "alive"),
            )
            db.add(char_db)
        
        # 建立章節
        for chap_data in data.get("chapters", []):
            chap_db = ChapterDB(
                novel_id=novel_db.id,
                number=chap_data.get("number", 0),
                title=chap_data.get("title", ""),
                summary=chap_data.get("summary", ""),
                content=chap_data.get("content"),
                key_events=chap_data.get("key_events", []),
                foreshadowing=chap_data.get("foreshadowing", []),
                version=chap_data.get("version", 1),
            )
            db.add(chap_db)
        
        await db.commit()
        
        return {
            "message": "匯入成功",
            "novel_id": novel_db.id,
            "title": novel_db.title,
        }
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="無效的 JSON 格式")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
