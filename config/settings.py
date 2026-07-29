"""小說生成器設定"""
import os
from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


# 專案根目錄
BASE_DIR = Path(__file__).parent.parent


def _load_hermes_config():
    """從 Hermes 設定檔讀取 LLM 設定作為 fallback"""
    try:
        import yaml
        hermes_config = Path.home() / ".hermes" / "config.yaml"
        if hermes_config.exists():
            with open(hermes_config) as f:
                mc = yaml.safe_load(f)
            result = {
                "llm_api_base": mc["model"].get("base_url", ""),
                "llm_api_key": mc["model"].get("api_key", ""),
                "llm_model": mc["model"].get("default", ""),
                "llm_max_tokens": mc["model"].get("max_tokens", 8192),
            }
            # 也讀取 Gemini API key（從 auxiliary.vision）
            aux_vision = mc.get("auxiliary", {}).get("vision", {})
            if aux_vision.get("api_key"):
                result["gemini_api_key"] = aux_vision["api_key"]
            return result
    except Exception:
        pass
    return {}


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
    # 中文 3000 字約 4500+ tokens，4096 會截斷章節，故預設 8192
    llm_max_tokens: int = 8192

    # === Gemini 設定（伏筆萃取用） ===
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

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
    """取得設定實例（.env 優先，Hermes 設定作為 fallback）"""
    settings = Settings()
    hermes = _load_hermes_config()
    # 如果 .env 沒設定 LLM API key（空的或是範例佔位符），從 Hermes fallback
    if not settings.llm_api_key or settings.llm_api_key.startswith("your_"):
        for key, val in hermes.items():
            if val:
                object.__setattr__(settings, key, val)
    return settings
