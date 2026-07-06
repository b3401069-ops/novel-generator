"""
小說生成器 - 主程式
Novel Generator - Main Entry Point

啟動方式：
    python main.py
    
訪問地址：
    http://localhost:8012
    http://localhost:8012/docs (API文檔)
"""

import uvicorn
from config.settings import get_settings


def main():
    """主函數"""
    settings = get_settings()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📚 小說工坊 Novel Forge                                    ║
║   ────────────────────────────────────                       ║
║   AI 驅動的小說生成器                                        ║
║                                                              ║
║   🌐 訪問地址: http://localhost:{settings.port}                       ║
║   📖 API 文檔: http://localhost:{settings.port}/docs                  ║
║                                                              ║
║   ✨ 功能特色:                                               ║
║   • 16 種風格模板（古文、現代、武俠、科幻...）             ║
║   • 去AI味、去簡體中文味                                    ║
║   • 繁體中文（台灣用語）                                    ║
║   • 章節可編輯、版本控制                                    ║
║   • 多設備協作（Web介面）                                   ║
║                                                              ║
║   按 Ctrl+C 停止服務                                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
