"""
小說生成引擎
Novel Generation Engine

核心引擎，負責：
1. 大綱解析與生成
2. 章節內容生成
3. 上下文管理
4. 章節編輯
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime

from openai import AsyncOpenAI

from config.settings import Settings, get_settings
from core.style_engine import StyleEngine, get_style_engine
from templates.anti_ai.system_prompt import (
    get_anti_ai_system_prompt,
    OUTLINE_GENERATION_PROMPT,
    CHAPTER_WRITING_PROMPT,
    CHAPTER_EDITING_PROMPT,
    POETRY_GENERATION_PROMPT,
)
from templates.anti_ai.post_processor import clean_text, get_post_processor


@dataclass
class Character:
    """角色"""
    name: str
    description: str
    role: str  # 主角、配角、反派等
    traits: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    status: str = "alive"


@dataclass
class Chapter:
    """章節"""
    number: int
    title: str
    summary: str
    content: Optional[str] = None
    key_events: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)
    version: int = 1
    versions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Novel:
    """小說"""
    id: str
    title: str
    summary: str
    style: str
    characters: List[Character] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class NovelEngine:
    """小說生成引擎"""

    def __init__(self, settings: Optional[Settings] = None):
        """
        初始化引擎
        
        Args:
            settings: 配置設定
        """
        self.settings = settings or get_settings()
        self.style_engine = get_style_engine()
        
        # 初始化LLM客戶端
        self.client = AsyncOpenAI(
            api_key=self.settings.llm_api_key,
            base_url=self.settings.llm_api_base,
        )
        
        # 後處理器
        self.post_processor = get_post_processor(style_aware=True)

    async def generate_outline(
        self,
        brief_outline: str,
        style: str = "modern",
        chapter_count: int = 10,
        words_per_chapter: int = 3000,
    ) -> Novel:
        """
        生成小說大綱
        
        Args:
            brief_outline: 簡略大綱
            style: 風格
            chapter_count: 章節數量
            words_per_chapter: 每章字數
            
        Returns:
            小說對象
        """
        # 獲取風格配置
        style_config = self.style_engine.get_style(style)
        
        # 構建系統提示詞
        system_prompt = get_anti_ai_system_prompt(style_config.system_prompt)
        
        # 構建用戶提示詞
        user_prompt = f"""
請根據以下簡略大綱，生成詳細的小說結構。

【簡略大綱】
{brief_outline}

【要求】
- 章節數量：{chapter_count}章
- 每章字數：約{words_per_chapter}字
- 風格：{style_config.name}

{OUTLINE_GENERATION_PROMPT}
"""
        
        # 調用LLM
        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            response_format={"type": "json_object"},
        )
        
        # 解析回應
        content = response.choices[0].message.content
        outline_data = json.loads(content)
        
        # 創建小說對象
        novel = Novel(
            id=f"novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=outline_data.get("title", "未命名小說"),
            summary=outline_data.get("summary", ""),
            style=style,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        
        # 添加角色
        for char_data in outline_data.get("characters", []):
            character = Character(
                name=char_data.get("name", ""),
                description=char_data.get("description", ""),
                role=char_data.get("role", "配角"),
                traits=char_data.get("traits", []),
            )
            novel.characters.append(character)
        
        # 添加章節
        for i, chap_data in enumerate(outline_data.get("chapters", []), 1):
            chapter = Chapter(
                number=i,
                title=chap_data.get("title", f"第{i}章"),
                summary=chap_data.get("summary", ""),
                key_events=chap_data.get("key_events", []),
                foreshadowing=chap_data.get("foreshadowing", []),
            )
            novel.chapters.append(chapter)
        
        return novel

    async def generate_chapter(
        self,
        novel: Novel,
        chapter_number: int,
        previous_summary: str = "",
    ) -> str:
        """
        生成章節內容
        
        Args:
            novel: 小說對象
            chapter_number: 章節編號
            previous_summary: 前文摘要
            
        Returns:
            章節內容
        """
        if chapter_number < 1 or chapter_number > len(novel.chapters):
            raise ValueError(f"無效的章節編號: {chapter_number}")
        
        chapter = novel.chapters[chapter_number - 1]
        style_config = self.style_engine.get_style(novel.style)
        
        # 構建上下文
        context = self._build_context(novel, chapter_number, previous_summary)
        
        # 構建系統提示詞
        system_prompt = get_anti_ai_system_prompt(style_config.system_prompt)
        
        # 構建用戶提示詞
        user_prompt = f"""
{CHAPTER_WRITING_PROMPT}

【章節資訊】
- 章節編號：第{chapter_number}章
- 章節標題：{chapter.title}
- 章節大綱：{chapter.summary}
- 關鍵事件：{', '.join(chapter.key_events) if chapter.key_events else '無'}
- 伏筆：{', '.join(chapter.foreshadowing) if chapter.foreshadowing else '無'}

【前文摘要】
{context.get('previous_summary', '這是第一章')}

【角色狀態】
{context.get('characters_status', '無')}

【字數要求】
約{self.settings.default_words_per_chapter}字
"""
        
        # 調用LLM
        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        
        content = response.choices[0].message.content
        
        # 後處理
        if self.settings.anti_ai_enabled:
            content = clean_text(
                content,
                strength=self.settings.anti_ai_strength,
                style=novel.style,
            )
        
        # 保存到章節
        chapter.content = content
        chapter.version += 1
        chapter.versions.append({
            "version": chapter.version,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        
        return content

    async def edit_chapter(
        self,
        novel: Novel,
        chapter_number: int,
        instruction: str,
        paragraph_id: Optional[int] = None,
    ) -> str:
        """
        編輯章節
        
        Args:
            novel: 小說對象
            chapter_number: 章節編號
            instruction: 修改指示
            paragraph_id: 段落ID（可選，不指定則整章修改）
            
        Returns:
            修改後的內容
        """
        if chapter_number < 1 or chapter_number > len(novel.chapters):
            raise ValueError(f"無效的章節編號: {chapter_number}")
        
        chapter = novel.chapters[chapter_number - 1]
        
        if not chapter.content:
            raise ValueError(f"第{chapter_number}章尚未生成")
        
        style_config = self.style_engine.get_style(novel.style)
        
        # 構建系統提示詞
        system_prompt = get_anti_ai_system_prompt(style_config.system_prompt)
        
        # 構建用戶提示詞
        if paragraph_id is not None:
            # 修改特定段落
            paragraphs = chapter.content.split('\n\n')
            if paragraph_id < 0 or paragraph_id >= len(paragraphs):
                raise ValueError(f"無效的段落ID: {paragraph_id}")
            
            original_text = paragraphs[paragraph_id]
            context_before = '\n\n'.join(paragraphs[:paragraph_id])[-500:] if paragraph_id > 0 else ""
            context_after = '\n\n'.join(paragraphs[paragraph_id+1:])[:500] if paragraph_id < len(paragraphs) - 1 else ""
            
            user_prompt = f"""
{CHAPTER_EDITING_PROMPT}

【原文】
{original_text}

【修改要求】
{instruction}

【上下文】
前文：{context_before}
後文：{context_after}

【章節大綱】
{chapter.summary}
"""
        else:
            # 整章修改
            user_prompt = f"""
{CHAPTER_EDITING_PROMPT}

【原文】
{chapter.content}

【修改要求】
{instruction}

【章節大綱】
{chapter.summary}
"""
        
        # 調用LLM
        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        
        content = response.choices[0].message.content
        
        # 後處理
        if self.settings.anti_ai_enabled:
            content = clean_text(
                content,
                strength=self.settings.anti_ai_strength,
                style=novel.style,
            )
        
        # 更新章節
        if paragraph_id is not None:
            paragraphs = chapter.content.split('\n\n')
            paragraphs[paragraph_id] = content
            chapter.content = '\n\n'.join(paragraphs)
        else:
            chapter.content = content
        
        # 保存版本
        chapter.version += 1
        chapter.versions.append({
            "version": chapter.version,
            "content": chapter.content,
            "timestamp": datetime.now().isoformat(),
            "instruction": instruction,
        })
        
        return chapter.content

    async def generate_poetry(
        self,
        scene: str,
        emotion: str,
        poetry_type: str = "五言絕句",
    ) -> str:
        """
        生成詩詞
        
        Args:
            scene: 場景描述
            emotion: 情感
            poetry_type: 詩詞類型
            
        Returns:
            詩詞內容
        """
        user_prompt = f"""
{POETRY_GENERATION_PROMPT}

【場景】
{scene}

【情感】
{emotion}

【詩詞類型】
{poetry_type}
"""
        
        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.poetry_temperature,
            max_tokens=500,
        )
        
        return response.choices[0].message.content

    def _build_context(
        self,
        novel: Novel,
        chapter_number: int,
        previous_summary: str = "",
    ) -> Dict[str, str]:
        """構建上下文"""
        context = {}
        
        # 前文摘要
        if previous_summary:
            context["previous_summary"] = previous_summary
        elif chapter_number > 1:
            # 自動生成前文摘要
            summaries = []
            for i in range(max(0, chapter_number - 3), chapter_number - 1):
                chap = novel.chapters[i]
                if chap.content:
                    # 取前200字作為摘要
                    summaries.append(f"第{i+1}章 {chap.title}: {chap.content[:200]}...")
                else:
                    summaries.append(f"第{i+1}章 {chap.title}: {chap.summary}")
            context["previous_summary"] = "\n".join(summaries)
        else:
            context["previous_summary"] = "這是第一章"
        
        # 角色狀態
        characters_status = []
        for char in novel.characters:
            characters_status.append(f"- {char.name}（{char.role}）：{char.description}")
        context["characters_status"] = "\n".join(characters_status)
        
        return context

    def rollback_chapter(self, novel: Novel, chapter_number: int, version: int) -> str:
        """
        回滾章節到指定版本
        
        Args:
            novel: 小說對象
            chapter_number: 章節編號
            version: 版本號
            
        Returns:
            回滾後的內容
        """
        if chapter_number < 1 or chapter_number > len(novel.chapters):
            raise ValueError(f"無效的章節編號: {chapter_number}")
        
        chapter = novel.chapters[chapter_number - 1]
        
        # 查找指定版本
        for v in chapter.versions:
            if v["version"] == version:
                chapter.content = v["content"]
                chapter.version = version
                return chapter.content
        
        raise ValueError(f"找不到版本 {version}")
