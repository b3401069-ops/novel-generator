"""
FastAPI 應用程式
FastAPI Application
"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from models.database import init_db
from api.routes import novels, chapters, styles, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期"""
    # 啟動時初始化資料庫
    await init_db()
    yield
    # 關閉時清理資源


# 建立FastAPI應用
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI 驅動的小說生成器，支持多種風格、去AI味、繁體中文",
    lifespan=lifespan,
)

# CORS設定
# 注意：allow_origins=["*"] 不能與 allow_credentials=True 併用（瀏覽器會拒絕）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(novels.router, prefix="/api/v1/novels", tags=["小說"])
app.include_router(chapters.router, prefix="/api/v1/chapters", tags=["章節"])
app.include_router(styles.router, prefix="/api/v1/styles", tags=["風格"])
app.include_router(export.router, prefix="/api/v1/export", tags=["匯出/匯入"])

# 靜態文件
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """首頁"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """健康檢查"""
    return {"status": "ok"}


@app.get("/api/v1/info")
async def info():
    """系統資訊"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "default_style": settings.default_style,
        "anti_ai_enabled": settings.anti_ai_enabled,
        "anti_ai_strength": settings.anti_ai_strength,
    }
