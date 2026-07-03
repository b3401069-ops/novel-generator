"""小說生成器設定"""
import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


# 專案根目錄
BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """應用設定"""

    # === 服務設定 ===
    app_name: str = "小說工坊 Novel Forge"
    app_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8012  # 使用可用端口
    debug: bool = False

    # === 資料庫 ===
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'novels.db'}"

    # === LLM 設定 ===
    # 支援 OpenAI 相容 API（OpenAI / DeepSeek / Ollama / LM Studio 等）
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.8
    llm_max_tokens: int = 4096

    # 詩詞生成用（需要較高創意）
    poetry_temperature: float = 1.0

    # === 預設風格 ===
    default_style: str = "modern"
    default_language: str = "zh-TW"  # 繁體中文

    # === 生成設定 ===
    default_chapter_count: int = 10
    default_words_per_chapter: int = 3000
    max_context_length: int = 8000  # 上下文最大長度

    # === 去AI味設定 ===
    anti_ai_enabled: bool = True
    anti_ai_strength: float = 1.0  # 0.0-1.0，1.0為完全去除

    # === 路徑 ===
    templates_dir: Path = BASE_DIR / "templates"
    styles_dir: Path = BASE_DIR / "templates" / "styles"
    data_dir: Path = BASE_DIR / "data"
    export_dir: Path = BASE_DIR / "data" / "exports"

    class Config:
        env_file = BASE_DIR / ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """取得設定實例"""
    return Settings()
