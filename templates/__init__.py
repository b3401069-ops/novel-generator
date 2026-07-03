"""小說生成器模板系統"""
from .anti_ai.system_prompt import get_anti_ai_system_prompt, CORE_ANTI_AI_RULES
from .anti_ai.post_processor import PostProcessor, clean_text, get_post_processor

__all__ = [
    "get_anti_ai_system_prompt",
    "CORE_ANTI_AI_RULES",
    "PostProcessor",
    "clean_text",
    "get_post_processor",
]
