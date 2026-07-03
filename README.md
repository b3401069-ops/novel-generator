# 📚 小說工坊 Novel Forge

AI 驅動的小說生成器，支持多種風格、去AI味、繁體中文、多設備協作。

## ✨ 功能特色

### 🎨 16 種風格模板
- 📜 **古文風** - 文言與白話交融，自動生成詩詞
- 🏙️ **現代風** - 當代白話，生活化敘事
- 🌀 **抽象風** - 意識流、實驗性、詩意散文
- ⚔️ **武俠風** - 金庸風格，俠義江湖
- 🚀 **科幻風** - 硬科幻與軟科幻
- 🔍 **懸疑風** - 推理小說，層層解謎
- 🐉 **東方奇幻** - 仙俠、修真、東方神話
- 🧙 **西方奇幻** - 魔法、劍與魔法、史詩奇幻
- 🧒 **兒童文學風** - 溫暖、想像力、成長
- 💕 **言情風** - 浪漫愛情，細膩情感
- 👻 **恐怖風** - 懸疑驚悚，毛骨悚然
- 📜 **歷史風** - 以史為鏡，借古喻今
- 🏙️ **都市風** - 現代都市，職場人生
- 🎬 **黑色電影風** - 陰鬱、宿命、道德灰色
- 😂 **幽默風** - 諷刺、黑色幽默、荒誕
- ⚔️ **戰爭風** - 烽火連天，人性掙扎

### 🛡️ 去AI味 + 繁體中文
- **雙層過濾架構**：提示詞工程 + 後處理過濾
- **台灣用語規範**：視頻→影片、網絡→網路、信息→資訊
- **AI套話過濾**：自動移除「值得注意的是」「眾所周知」等
- **完全去除模式**：最大程度消除AI痕跡

### ✏️ 章節可編輯
- **段落級修改**：選中特定段落進行修改
- **整章重寫**：保留大綱，重新生成
- **版本控制**：每次修改都保存版本，可回滾
- **修改歷史**：查看所有修改記錄

### 🌐 多設備協作
- **Web介面**：任何設備的瀏覽器都能訪問
- **即時同步**：所有設備看到相同的內容
- **零配置**：不需要雲端帳號

## 🚀 快速開始

### 1. 安裝依賴

```bash
cd novel-generator
pip install -r requirements.txt
```

### 2. 配置環境變數

```bash
cp .env.example .env
# 編輯 .env，設定你的 LLM API
```

### 3. 啟動服務

```bash
python main.py
```

### 4. 訪問

- **Web介面**：http://localhost:9527
- **API文檔**：http://localhost:9527/docs

## 📖 使用方式

### 創建小說

1. 點擊「✨ 創建小說」
2. 輸入簡略大綱
3. 選擇風格
4. 點擊「🚀 開始生成」

### 編輯章節

1. 在「我的小說」中選擇小說
2. 點擊章節查看內容
3. 點擊「✏️ 編輯」
4. 輸入修改要求
5. 點擊「🔄 重新生成」

### 風格選擇

- **古文風**：適合歷史、仙俠、古典題材
- **現代風**：適合都市、職場、日常題材
- **武俠風**：適合武俠、江湖題材
- **科幻風**：適合未來、太空、科技題材
- **懸疑風**：適合推理、偵探題材
- **奇幻風**：適合魔法、冒險題材

## 🔧 API 端點

### 小說
- `GET /api/v1/novels/` - 列出所有小說
- `POST /api/v1/novels/` - 創建新小說
- `GET /api/v1/novels/{id}` - 獲取小說詳情
- `DELETE /api/v1/novels/{id}` - 刪除小說

### 章節
- `GET /api/v1/chapters/{novel_id}` - 列出章節
- `GET /api/v1/chapters/{novel_id}/{number}` - 獲取章節
- `POST /api/v1/chapters/generate` - 生成章節
- `POST /api/v1/chapters/edit` - 編輯章節
- `POST /api/v1/chapters/rollback` - 回滾章節

### 風格
- `GET /api/v1/styles/` - 列出所有風格
- `GET /api/v1/styles/{id}` - 獲取風格詳情
- `GET /api/v1/styles/{id}/prompt` - 獲取風格提示詞
- `GET /api/v1/styles/{id}/vocabulary` - 獲取詞彙表

## 📁 專案結構

```
novel-generator/
├── main.py                    # 主程式入口
├── requirements.txt           # 依賴
├── .env.example               # 環境變數範例
├── config/
│   └── settings.py            # 配置
├── templates/
│   ├── styles/                # 16種風格模板
│   │   ├── ancient_chinese.yaml
│   │   ├── modern.yaml
│   │   ├── abstract.yaml
│   │   ├── wuxia.yaml
│   │   ├── scifi.yaml
│   │   ├── mystery.yaml
│   │   ├── fantasy_eastern.yaml
│   │   ├── fantasy_western.yaml
│   │   ├── children.yaml
│   │   ├── romance.yaml
│   │   ├── horror.yaml
│   │   ├── historical.yaml
│   │   ├── urban.yaml
│   │   ├── noir.yaml
│   │   ├── humor.yaml
│   │   └── war.yaml
│   └── anti_ai/
│       ├── system_prompt.py   # 反AI系統提示詞
│       └── post_processor.py  # 後處理過濾器
├── core/
│   ├── engine.py              # 核心引擎
│   └── style_engine.py        # 風格引擎
├── models/
│   ├── database.py            # 資料庫配置
│   └── novel.py               # 資料模型
├── api/
│   ├── app.py                 # FastAPI應用
│   └── routes/
│       ├── novels.py          # 小說API
│       ├── chapters.py        # 章節API
│       └── styles.py          # 風格API
├── static/
│   └── index.html             # Web前端
└── data/                      # 資料目錄
    └── novels.db              # SQLite資料庫
```

## 🎯 設計理念

### 1. 簡單易用
用戶只需提供簡略大綱，系統自動生成詳細結構和內容。

### 2. 風格多樣
16種精心設計的風格模板，滿足不同類型的創作需求。

### 3. 品質保證
雙層過濾架構，從源頭和後處理兩個層面確保輸出品質。

### 4. 靈活編輯
支持段落級和整章級的修改，每次修改都有版本記錄。

### 5. 隨時隨地
Web介面設計，任何設備的瀏覽器都能訪問和編輯。

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License
