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
import httpx
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
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
class PlotThread:
    """P4: 劇情線"""
    id: str                          # 線 ID，如 "A"、"B"、"C"
    name: str                        # 線名稱，如 "主角復仇線"、"政治陰謀線"
    summary: str                     # 線的摘要
    main_characters: List[str] = field(default_factory=list)  # 該線的主要角色名列表
    progress: str = ""               # 該線的進度描述，每章更新


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
    thread_id: Optional[str] = None  # P4: 所屬劇情線


@dataclass
class Novel:
    """小說"""
    id: str
    title: str
    summary: str
    style: str
    characters: List[Character] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    plot_threads: List[PlotThread] = field(default_factory=list)  # P4: 多線劇情
    created_at: str = ""
    updated_at: str = ""
    running_summary: str = ""  # P0: 全書累進摘要
    unresolved_foreshadowing: List[str] = field(default_factory=list)  # P1: 未回收伏筆


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

        # 添加劇情線（P4）
        for thread_data in outline_data.get("plot_threads", []) or []:
            thread = PlotThread(
                id=thread_data.get("id", ""),
                name=thread_data.get("name", ""),
                summary=thread_data.get("summary", ""),
                main_characters=thread_data.get("main_characters", []),
            )
            novel.plot_threads.append(thread)

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
                thread_id=chap_data.get("thread_id"),  # P4: 所屬劇情線
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
        on_complete: Optional[Callable] = None,
    ) -> str:
        """
        生成章節內容

        Args:
            novel: 小說對象
            chapter_number: 章節編號
            previous_summary: 前文摘要
            on_complete: 可選的 async callback，在 P0+P1+P2 更新後呼叫。
                         簽名: async def callback(novel, chapter_number) -> None
                         用於持久化引擎更新的狀態到外部儲存（如 DB）。

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

        # P1→P0→P2: 完成後自動更新狀態（P1 先抓伏筆→P0 摘要同步引用）
        await self._update_foreshadowing(novel, chapter_number)
        await self._update_running_summary(novel, chapter_number)
        await self._update_characters(novel, chapter_number)

        # 持久化回調（供 API routes 寫入 DB）
        if on_complete:
            await on_complete(novel, chapter_number)

        return content

    async def generate_chapter_stream(
        self,
        novel: Novel,
        chapter_number: int,
        previous_summary: str = "",
        on_complete: Optional[Callable] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        串流生成章節內容

        逐塊 yield {"type": "delta", "text": ...}，
        全部生成後 yield {"type": "done", "content": 後處理過的全文}，
        然後自動執行 P0+P1+P2 三層狀態更新。
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

        # P1→P0→P2: 完成後自動更新狀態（失敗不影響已產出的章節內容）
        await self._update_foreshadowing(novel, chapter_number)
        await self._update_running_summary(novel, chapter_number)
        await self._update_characters(novel, chapter_number)

        # 持久化回調（供 API routes 寫入 DB）
        if on_complete:
            await on_complete(novel, chapter_number)

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
- 所屬劇情線：{chapter.thread_id or '主線'}
- 關鍵事件：{', '.join(chapter.key_events) if chapter.key_events else '無'}
- 本章需埋設的伏筆：{', '.join(chapter.foreshadowing) if chapter.foreshadowing else '無'}

【全書前文摘要】
{context.get('previous_summary', '這是第一章')}

【跨線劇情進度】（P4：了解其他線最新進展，避免時間線矛盾）
{context.get('cross_thread_context') or '（單線故事，無跨線需求）'}

【需要回收的伏筆】（P1：來自前文的未完成伏筆，必須在本章或後續章節處理）
{chr(10).join(f'- {f}' for f in novel.unresolved_foreshadowing) if novel.unresolved_foreshadowing else '無'}

【角色狀態】（P2：根據劇情進展動態更新）
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
        """構建上下文 — P0: 優先使用累進摘要，P4: 跨線感知"""
        context = {}
        chapter = novel.chapters[chapter_number - 1]
        thread_id = chapter.thread_id

        # P0: 前文摘要 — 優先使用 running_summary
        if previous_summary:
            context["previous_summary"] = previous_summary
        elif novel.running_summary:
            context["previous_summary"] = novel.running_summary
        elif chapter_number > 1:
            # 回退：自動生成前文摘要（取前 3 章）
            summaries = []
            for i in range(max(0, chapter_number - 3), chapter_number - 1):
                chap = novel.chapters[i]
                if chap.content:
                    summaries.append(f"第{i+1}章 {chap.title}: {chap.content[:200]}...")
                else:
                    summaries.append(f"第{i+1}章 {chap.title}: {chap.summary}")
            context["previous_summary"] = "\n".join(summaries)
        else:
            context["previous_summary"] = "這是第一章"

        # P4: 跨線上下文 — 多線故事時提供其他線的最新進度
        cross_thread_context = self._build_cross_thread_context(novel, chapter_number, thread_id)
        context["cross_thread_context"] = cross_thread_context

        # 角色狀態 — 包含動態 status + 性格特質
        characters_status = []
        for char in novel.characters:
            status_tag = f"【{char.status}】" if char.status != "alive" else ""
            traits_str = f"（性格：{'、'.join(char.traits)}）" if char.traits else ""
            characters_status.append(
                f"- {char.name}{status_tag}{traits_str}（{char.role}）：{char.description}"
            )
        context["characters_status"] = "\n".join(characters_status)

        return context

    def _build_cross_thread_context(
        self,
        novel: Novel,
        chapter_number: int,
        current_thread_id: Optional[str],
    ) -> str:
        """P4: 構建跨線上下文 — 給定當前章節的 thread_id，收集其他線最近一章的摘要"""
        if not novel.plot_threads or not current_thread_id:
            return ""

        lines = []
        for thread in novel.plot_threads:
            if thread.id == current_thread_id:
                # 同線：找上一章（同 thread_id 的前一章）
                prev_same_thread = None
                for ch in novel.chapters[: chapter_number - 1]:
                    if ch.thread_id == thread.id:
                        prev_same_thread = ch
                if prev_same_thread:
                    lines.append(
                        f"【同線前章：{thread.name}】第{prev_same_thread.number}章「{prev_same_thread.title}」"
                        f"摘要：{prev_same_thread.summary}"
                    )
            else:
                # 其他線：找該線最近一章
                latest_other = None
                for ch in novel.chapters[: chapter_number - 1]:
                    if ch.thread_id == thread.id:
                        latest_other = ch
                if latest_other:
                    lines.append(
                        f"【其他線進度：{thread.name}】最近為第{latest_other.number}章「{latest_other.title}」"
                        f"摘要：{latest_other.summary}"
                    )
                else:
                    lines.append(
                        f"【其他線摘要：{thread.name}】（尚未展開）{thread.summary}"
                    )

        return "\n".join(lines) if lines else ""

    # ════════════════════════════════════════════════════════════════
    # P0+P1+P2: 長篇防矛盾三層機制
    # ════════════════════════════════════════════════════════════════

    async def _update_running_summary(
        self,
        novel: Novel,
        chapter_number: int,
    ) -> None:
        """
        P0 — 全書累進摘要

        每章完成後自動更新，將新章節內容濃縮後合併到 running_summary。
        摘要上限約 2000 字，強制包含：劇情進展、角色變化、未回收伏筆。
        """
        chapter = novel.chapters[chapter_number - 1]
        old_summary = novel.running_summary or "尚無前文"

        # 擷取章節精華（前 1500 字供 LLM 參考）
        chapter_snippet = chapter.content[:1500] if chapter.content else chapter.summary

        # 注入 P1 的伏筆結構化清單，確保摘要與 structured 欄位一致
        fs_str = "\n".join(f"- {f}" for f in novel.unresolved_foreshadowing) if novel.unresolved_foreshadowing else "（尚無未回收伏筆）"

        prompt = f"""你是小說編輯，請將以下資訊合併成一份「全書累進摘要」。
摘要需精簡（上限約 2000 字），包含三部分：
1. 劇情進展（主要事件與轉折）
2. 角色狀態變化（誰受傷、死亡、關係轉變）
3. 尚未回收的伏筆（請參考下方結構化清單，用【待回收】標記）

【已知伏筆清單（結構化追蹤）】
{fs_str}

【舊摘要】
{old_summary}

【新章節（第{chapter_number}章「{chapter.title}」）內容精華】
{chapter_snippet}

請輸出合併後的摘要（純文字，不要 JSON）："""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200,
            )
            novel.running_summary = response.choices[0].message.content.strip()
        except Exception:
            # 摘要更新失敗不應中斷主流程，回退到手動拼接
            fallback = f"{old_summary}\n[第{chapter_number}章] {chapter.title}: {chapter.summary}"
            novel.running_summary = fallback[:2000]

    async def _update_foreshadowing(
        self,
        novel: Novel,
        chapter_number: int,
    ) -> None:
        """
        P1 — 伏筆註冊表更新（使用 Gemini 3.6 Flash）

        分析章節內容，提取新埋設的伏筆與已回收的伏筆，
        自動更新 novel.unresolved_foreshadowing。

        改用 Gemini 而非 DeepSeek：Gemini 更願意指出潛在線索，
        不會像 DeepSeek 因為保守而回傳空陣列。
        """
        print(f"[P1 Gemini] _update_foreshadowing called for novel={novel.id} ch={chapter_number}", flush=True)
        chapter = novel.chapters[chapter_number - 1]
        chapter_snippet = chapter.content[:4000] if chapter.content else chapter.summary

        prompt = f"""你是一位專業小說編輯，擅長找出故事中的伏筆。

以下是一個章節的內容，請找出其中所有「埋伏筆」與「回收伏筆」的線索。

伏筆類型包括（但不限於）：
- 人物伏筆：角色說出意味深長的話、反常行為、隱藏身份
- 物品伏筆：被特別描述的物品，暗示後續用途
- 對話伏筆：對話中透露未解資訊
- 情境伏筆：場景中的未解之謎
- 回收：本章解開了前面的某個疑問

【章節內容】
{chapter_snippet}

請以 JSON 格式回覆（只輸出 JSON，不要其他文字）：
{{
  "planted": ["角色A在對話中暗示知道兇手身份，但沒明說", "書房古董鐘午夜自動停下——暗示與案件時間有關"],
  "resolved": ["第2章的不在場證明漏洞，本章透過監視器畫面解釋"]
}}

重要：每部小說章節至少會埋 1-2 個伏筆（對話暗示、物品特寫、角色反常等），請務必找出。即使看似不明顯的暗示也請列出。"""

        try:
            print(f"[P1 Gemini] Calling Gemini API with model={self.settings.gemini_model}...", flush=True)
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.settings.gemini_model}:generateContent"
                f"?key={self.settings.gemini_api_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 2000,
                },
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                text = body["candidates"][0]["content"]["parts"][0]["text"]

            print(f"[P1 Gemini] Response ({len(text)} chars): {text[:200]}...", flush=True)

            # Gemini 有時會在 JSON 前後加 markdown code block，先清理
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            data = json.loads(text)

            # 加入新埋設的伏筆
            for planted in data.get("planted", []):
                if planted not in novel.unresolved_foreshadowing:
                    novel.unresolved_foreshadowing.append(planted)

            # 移除已回收的伏筆（模糊匹配）
            resolved_list = data.get("resolved", [])
            novel.unresolved_foreshadowing = [
                f for f in novel.unresolved_foreshadowing
                if not any(r in f or f in r for r in resolved_list)
            ]
        except Exception as e:
            import traceback
            print(f"[P1 Gemini] ERROR: {e}", flush=True)
            traceback.print_exc()

    async def _update_characters(
        self,
        novel: Novel,
        chapter_number: int,
    ) -> None:
        """
        P2 — 角色狀態機

        每章完成後，分析章節內容對各角色狀態的影響，
        自動更新 Character.description 與 Character.status。
        """
        chapter = novel.chapters[chapter_number - 1]
        chapter_snippet = chapter.content[:2000] if chapter.content else chapter.summary

        # 建立角色現狀摘要
        char_list = "\n".join(
            f"- {c.name}（{c.role}，狀態：{c.status}）\n  描述：{c.description}"
            for c in novel.characters
        )

        prompt = f"""根據以下章節內容，更新各角色的最新狀態。

【角色現狀】
{char_list}

【本章內容】
{chapter_snippet}

請輸出 JSON，只包含本章中「有變化」的角色。status 可為：alive / injured / dead / missing / transformed。
description 需整合本章變化後的簡短描述（50 字內）。
若某角色本章無變化，不要包含在輸出中。

格式：
{{
  "characters": [
    {{"name": "張三", "status": "injured", "description": "與守護獸交戰後左臂受傷，現藏身於山洞中"}}
  ]
}}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            data = self._parse_json_response(response.choices[0].message.content)

            for update in data.get("characters", []):
                name = update.get("name", "")
                for char in novel.characters:
                    if char.name == name:
                        if "status" in update:
                            char.status = update["status"]
                        if "description" in update:
                            char.description = update["description"]
                        break
        except Exception:
            pass  # 角色更新失敗不影響主流程

    # ════════════════════════════════════════════════════════════════
    # P3 — 全書最終審閱
    # ════════════════════════════════════════════════════════════════

    async def final_review(self, novel: Novel) -> Dict[str, Any]:
        """
        P3 — 全書最終審閱

        全部章節撰寫完成後，從頭到尾掃描整本小說，檢查：
        1. 角色事實一致性（死亡/存活/位置矛盾）
        2. 角色性格一致性（OOC、性格漂移、角色成長弧線）
        3. 未回收伏筆
        4. 時間線與事件順序
        5. 關鍵設定一致性

        Returns:
            {
                "overall_score": 1-10,
                "issues": [
                    {
                        "severity": "critical" | "major" | "minor",
                        "chapter": int | null,
                        "category": "character" | "foreshadowing" | "timeline" | "setting",
                        "description": "...",
                        "suggestion": "..."
                    }
                ],
                "summary": "整體評價（200 字內）"
            }
        """
        # 構建審閱上下文
        char_list = "\n".join(
            f"- {c.name}（{c.role}）\n"
            f"  性格特質：{'、'.join(c.traits) if c.traits else '未設定'}\n"
            f"  描述：{c.description}\n"
            f"  最終狀態：{c.status}"
            for c in novel.characters
        )

        # 逐章全文（每章取前 1500 字，確保 LLM 能看到實際文本而非只有摘要）
        chapter_texts = "\n\n".join(
            f"═══ 第 {ch.number} 章《{ch.title}》═══\n"
            f"摘要：{ch.summary}\n"
            f"內容(前1500字)：\n{(ch.content or ch.summary)[:1500]}"
            for ch in novel.chapters
        )

        foreshadowing_str = (
            "\n".join(f"- {f}" for f in novel.unresolved_foreshadowing)
            if novel.unresolved_foreshadowing
            else "（無未回收伏筆）"
        )

        # 限制總輸入長度：每章 1600 字 × N 章，超過 12 章時截斷為前後各 6 章
        chapter_count = len(novel.chapters)
        if chapter_count > 12:
            front = novel.chapters[:6]
            back = novel.chapters[-6:]
            chapter_texts = (
                "\n\n".join(
                    f"═══ 第 {ch.number} 章《{ch.title}》═══\n"
                    f"摘要：{ch.summary}\n"
                    f"內容(前1500字)：\n{(ch.content or ch.summary)[:1500]}"
                    for ch in front
                )
                + f"\n\n...（中間 {chapter_count - 12} 章略）...\n\n"
                + "\n\n".join(
                    f"═══ 第 {ch.number} 章《{ch.title}》═══\n"
                    f"摘要：{ch.summary}\n"
                    f"內容(前1500字)：\n{(ch.content or ch.summary)[:1500]}"
                    for ch in back
                )
            )

        prompt = f"""你是一位嚴厲的小說審稿編輯。請仔細閱讀以下小說全文，找出「真正存在的問題」。不要為了湊數而編造問題，但也「不允許」用空洞的正面評價敷衍——沒有問題必須有證據佐證。

【全書摘要】
{novel.running_summary or novel.summary}

【角色設定（含性格特質）】
{char_list}

【未回收伏筆】
{foreshadowing_str}

【各章全文（含內容）】
{chapter_texts}

🔴 你必須逐章掃描上方全文，對照以下五個維度，每項都需給出「通過」或「發現問題」的判斷：

1. **角色事實一致性** — 是否有角色死亡後又出現？位置衝突？關係矛盾？
   → 對照上方【角色設定】的「最終狀態」與各章實際內容。
2. **角色性格一致性** — 角色言行是否與其「性格特質」一致？有無 OOC？若有合理角色成長請正面標註。
   → 必須引用具體章節中的對話或行為作為證據。
3. **伏筆回收** — 未回收伏筆是否與結局吻合？是否有明顯埋了卻沒回收的？
4. **時間線** — 事件順序是否合理？有無明顯的時間跳躍矛盾？
5. **設定一致性** — 關鍵物品、地點、規則是否前後一致？

🚫 禁止事項：
- 禁止使用「完成度極高」「無懈可擊」「精彩絕倫」「令人驚豔」等空洞讚美詞
- 禁止在未提供逐項證據的情況下宣稱「沒有問題」
- 禁止給出 10/10 除非你能明確列出五個維度各自的通過證據
- 禁止忽略上方提供的章節全文內容
- summary 欄位必須用繁體中文，針對實際發現的問題給出具體評價，而非泛泛讚美

輸出 JSON 格式：
{{{{
  "dimension_results": {{{{ 
    "character_facts": "pass|issues_found",
    "personality_consistency": "pass|issues_found",
    "foreshadowing": "pass|issues_found",
    "timeline": "pass|issues_found",
    "setting": "pass|issues_found"
  }}}},
  "overall_score": 1-10,
  "issues": [
    {{{{
      "severity": "critical|major|minor",
      "chapter": 章節編號（全書性問題填 null）,
      "category": "character|personality|foreshadowing|timeline|setting",
      "description": "具體問題描述（引用章節內容為證）",
      "suggestion": "建議修復方式"
    }}}}
  ],
  "auto_fixes": [
    {{{{
      "character": "角色名稱",
      "field": "status|description",
      "from": "目前錯誤值",
      "to": "正確值"
    }}}}
  ],
  "summary": "基於實際發現的審閱總結（繁體中文，200 字內）"
}}}}

auto_fixes 只放「可直接修正的事實矛盾」（如角色狀態與實際劇情衝突）。不確定或需人為判斷的問題放 issues。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            result = self._parse_json_response(response.choices[0].message.content or "{}")

            # 自動套用 auto_fixes
            fixes_applied = []
            for fix in result.get("auto_fixes", []):
                char_name = fix.get("character", "")
                field = fix.get("field", "")
                new_val = fix.get("to", "")
                for char in novel.characters:
                    if char.name == char_name:
                        old_val = getattr(char, field, None)
                        setattr(char, field, new_val)
                        fixes_applied.append({
                            "character": char_name,
                            "field": field,
                            "from": old_val,
                            "to": new_val,
                        })
                        break
            result["fixes_applied"] = fixes_applied
            return result
        except Exception as e:
            return {
                "overall_score": 0,
                "issues": [],
                "summary": f"審閱失敗：{str(e)}",
                "error": True,
            }

    # ════════════════════════════════════════════════════════════════

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
