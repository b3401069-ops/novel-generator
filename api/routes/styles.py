"""
風格相關API
Styles API Routes
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.style_engine import get_style_engine


router = APIRouter()
style_engine = get_style_engine()


# ──────────────────────────────────────────────
# Pydantic 模型
# ──────────────────────────────────────────────

class StyleResponse(BaseModel):
    """風格回應"""
    id: str
    name: str
    name_en: str
    icon: str
    description: str


class StyleDetailResponse(BaseModel):
    """風格詳細回應"""
    id: str
    name: str
    name_en: str
    icon: str
    description: str
    system_prompt: str
    vocabulary: dict
    sentence_rules: dict
    reference_materials: List[dict]
    chapter_templates: dict
    sub_styles: dict


class PoetryRequest(BaseModel):
    """詩詞生成請求"""
    scene: str
    emotion: str
    poetry_type: str = "五言絕句"


# ──────────────────────────────────────────────
# API 端點
# ──────────────────────────────────────────────

@router.get("/", response_model=List[StyleResponse])
async def list_styles():
    """列出所有可用風格"""
    styles = style_engine.list_styles()
    return styles


@router.get("/{style_id}", response_model=StyleDetailResponse)
async def get_style(style_id: str):
    """獲取風格詳情"""
    try:
        style = style_engine.get_style(style_id)
        return {
            "id": style_id,
            "name": style.name,
            "name_en": style.name_en,
            "icon": style.icon,
            "description": style.description,
            "system_prompt": style.system_prompt,
            "vocabulary": style.vocabulary,
            "sentence_rules": style.sentence_rules,
            "reference_materials": style.reference_materials,
            "chapter_templates": style.chapter_templates,
            "sub_styles": style.sub_styles,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{style_id}/prompt")
async def get_style_prompt(style_id: str):
    """獲取風格的系統提示詞"""
    try:
        prompt = style_engine.get_system_prompt(style_id)
        return {"style": style_id, "prompt": prompt}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{style_id}/vocabulary")
async def get_style_vocabulary(style_id: str):
    """獲取風格的詞彙替換表"""
    try:
        replacements = style_engine.get_vocabulary_replacements(style_id)
        banned = style_engine.get_banned_words(style_id)
        return {
            "style": style_id,
            "replacements": replacements,
            "banned": banned,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{style_id}/reference")
async def get_random_reference(style_id: str):
    """隨機獲取風格的參考素材"""
    try:
        reference = style_engine.get_random_reference(style_id)
        if reference:
            return {"style": style_id, "reference": reference}
        return {"style": style_id, "reference": None, "message": "無參考素材"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
