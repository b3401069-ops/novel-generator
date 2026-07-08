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
        outline_data = self._parse_json_response(content)
        
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

    async def generate_bridge(
        self,
        prev_title: str,
        prev_tail: str,
        next_title: str,
        next_head: str,
        style: str = "modern",
    ) -> Dict[str, Any]:
        """
        生成兩部短篇之間的「銜接章節」大綱（合併成長篇時用）

        Args:
            prev_title: 前一部標題
            prev_tail: 前一部的結尾內容或摘要
            next_title: 下一部標題
            next_head: 下一部的開頭內容或摘要
            style: 風格

        Returns:
            {"title": ..., "summary": ..., "key_events": [...]}
        """
        style_config = self.style_engine.get_style(style)
        system_prompt = get_anti_ai_system_prompt(style_config.system_prompt)

        user_prompt = f"""
你正在把多部短篇小說合併成一部長篇小說。現在需要設計一段「銜接情節」，
讓前一部的結尾自然過渡到下一部的開頭，補足中間缺少的劇情，使長篇讀起來連貫。

【前一部：{prev_title}】結尾：
{prev_tail or '（無內容，僅有大綱）'}

【下一部：{next_title}】開頭：
{next_head or '（無內容，僅有大綱）'}

請設計「一個」銜接章節的大綱，只用 JSON 回覆，格式如下：
{{"title": "銜接章節的標題", "summary": "這一章的情節摘要，說明角色如何從前一部的結局走到下一部的開端、補足了哪些中間劇情", "key_events": ["關鍵事件1", "關鍵事件2", "關鍵事件3"]}}
"""

        response = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )

        data = self._parse_json_response(response.choices[0].message.content)
        return {
            "title": data.get("title", "銜接章節"),
            "summary": data.get("summary", ""),
            "key_events": data.get("key_events", []),
        }

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
        system_prompt, user_prompt = self._build_chapter_prompts(
            novel, chapter_number, previous_summary
        )
        chapter = novel.chapters[chapter_number - 1]

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

        # 保存到章節（版本記錄由 API 層的 _save_version 負責）
        chapter.content = content

        return content

    async def generate_chapter_stream(
        self,
        novel: Novel,
        chapter_number: int,
        previous_summary: str = "",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        串流生成章節內容

        逐塊 yield {"type": "delta", "text": ...}，
        全部生成後 yield {"type": "done", "content": 後處理過的全文}。
        """
        system_prompt, user_prompt = self._build_chapter_prompts(
            novel, chapter_number, previous_summary
        )

        stream = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            stream=True,
        )

        parts: List[str] = []
        async for chunk in stream:
            if not chunk.choices:
                continue  # 部分供應商會送出不含 choices 的 usage chunk
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                yield {"type": "delta", "text": delta}

        content = "".join(parts)
        if self.settings.anti_ai_enabled:
            content = clean_text(
                content,
                strength=self.settings.anti_ai_strength,
                style=novel.style,
            )

        novel.chapters[chapter_number - 1].content = content
        yield {"type": "done", "content": content}

    def _build_chapter_prompts(
        self,
        novel: Novel,
        chapter_number: int,
        previous_summary: str = "",
    ) -> tuple:
        """組裝章節生成的 system / user 提示詞"""
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
        return system_prompt, user_prompt

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
        system_prompt, user_prompt = self._build_edit_prompts(
            novel, chapter_number, instruction, paragraph_id
        )
        chapter = novel.chapters[chapter_number - 1]

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
        
        # 更新章節（版本記錄由 API 層的 _save_version 負責）
        chapter.content = self._apply_edit(chapter.content, content, paragraph_id)

        return chapter.content

    async def edit_chapter_stream(
        self,
        novel: Novel,
        chapter_number: int,
        instruction: str,
        paragraph_id: Optional[int] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        串流編輯章節

        逐塊 yield {"type": "delta", "text": ...}（段落編輯時是新段落內容），
        完成後 yield {"type": "done", "content": 更新後的整章內容}。
        """
        system_prompt, user_prompt = self._build_edit_prompts(
            novel, chapter_number, instruction, paragraph_id
        )
        chapter = novel.chapters[chapter_number - 1]

        stream = await self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
            stream=True,
        )

        parts: List[str] = []
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                parts.append(delta)
                yield {"type": "delta", "text": delta}

        content = "".join(parts)
        if self.settings.anti_ai_enabled:
            content = clean_text(
                content,
                strength=self.settings.anti_ai_strength,
                style=novel.style,
            )

        chapter.content = self._apply_edit(chapter.content, content, paragraph_id)
        yield {"type": "done", "content": chapter.content}

    @staticmethod
    def _apply_edit(
        original: str,
        new_text: str,
        paragraph_id: Optional[int] = None,
    ) -> str:
        """將編輯結果套用回章節：段落編輯只替換該段，否則整章替換"""
        if paragraph_id is None:
            return new_text
        paragraphs = original.split('\n\n')
        paragraphs[paragraph_id] = new_text
        return '\n\n'.join(paragraphs)

    def _build_edit_prompts(
        self,
        novel: Novel,
        chapter_number: int,
        instruction: str,
        paragraph_id: Optional[int] = None,
    ) -> tuple:
        """組裝章節編輯的 system / user 提示詞"""
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
        return system_prompt, user_prompt

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

    @staticmethod
    def _parse_json_response(content: str) -> Dict[str, Any]:
        """
        解析 LLM 回傳的 JSON。

        部分 OpenAI 相容 API（DeepSeek / Ollama / LM Studio 等）會忽略
        response_format，回傳 ```json 圍欄或夾帶說明文字，這裡做容錯處理。
        """
        text = content.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise ValueError(f"LLM 回應不是有效的 JSON，無法解析大綱：{text[:200]}")

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
