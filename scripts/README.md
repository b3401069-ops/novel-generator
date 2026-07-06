# 📦 備份系統使用說明

> 💡 要把整套服務搬到另一台電腦？用一鍵搬家工具 `migrate_export.py`，
> 它會打包資料庫 + `.env` + Cloudflare Tunnel 憑證。詳見主 README 的
> 「🚚 搬家 / 災難復原」章節。

## 快速開始

### 方法一：使用備份腳本（推薦）

**Linux/Mac:**
```bash
# 建立備份
python scripts/backup.py backup

# 查看備份列表
python scripts/backup.py list

# 還原備份
python scripts/backup.py restore --restore-file ~/novel-backups/novels_backup_20240101_120000.db
```

**Windows:**
```powershell
# 建立備份
python scripts\backup.py backup

# 查看備份列表
python scripts\backup.py list

# 還原備份
python scripts\backup.py restore --restore-file %USERPROFILE%\novel-backups\novels_backup_20240101_120000.db
```

### 方法二：自動定時備份

**Linux/Mac (使用 crontab):**
```bash
# 編輯 crontab
crontab -e

# 加入以下內容（每天凌晨 3 點備份）
0 3 * * * /path/to/novel-generator/scripts/auto_backup.sh >> /var/log/novel-backup.log 2>&1
```

**Windows (使用工作排程器):**
1. 開啟「工作排程器」
2. 建立基本工作
3. 觸發器：每天凌晨 3:00
4. 動作：啟動程式 → `scripts\auto_backup.bat`

### 方法三：備份到雲端同步資料夾

將備份目錄設為雲端同步資料夾：

**Google Drive:**
```bash
# Linux/Mac
export BACKUP_DIR=~/Google\ Drive/novel-backups
python scripts/backup.py backup

# Windows
set BACKUP_DIR=%USERPROFILE%\Google Drive\novel-backups
python scripts\backup.py backup
```

**Dropbox:**
```bash
# Linux/Mac
export BACKUP_DIR=~/Dropbox/novel-backups
python scripts/backup.py backup

# Windows
set BACKUP_DIR=%USERPROFILE%\Dropbox\novel-backups
python scripts\backup.py backup
```

**OneDrive:**
```bash
# Linux/Mac
export BACKUP_DIR=~/OneDrive/novel-backups
python scripts/backup.py backup

# Windows
set BACKUP_DIR=%USERPROFILE%\OneDrive\novel-backups
python scripts\backup.py backup
```

---

## 匯出功能

### 匯出為 JSON（完整備份）

```bash
# 使用 API
curl -o novel_backup.json http://localhost:8012/api/v1/export/{novel_id}/json
```

### 匯出為 TXT（純文字）

```bash
# 使用 API
curl -o novel.txt http://localhost:8012/api/v1/export/{novel_id}/txt
```

### 匯出為 Markdown

```bash
# 使用 API
curl -o novel.md http://localhost:8012/api/v1/export/{novel_id}/markdown
```

---

## 匯入功能

### 從 JSON 匯入

```bash
# 使用 API
curl -X POST -F "file=@novel_backup.json" http://localhost:8012/api/v1/export/import
```

---

## 備份策略建議

### 3-2-1 備份原則

- **3** 份備份
- **2** 種不同儲存媒體
- **1** 份異地備份

### 建議配置

```
本地備份（每天）:
├── ~/novel-backups/          # 本地備份目錄
└── 保留最近 30 天

雲端備份（每天）:
├── Google Drive/novel-backups/
├── Dropbox/novel-backups/
└── OneDrive/novel-backups/

匯出備份（每週）:
├── 導出 JSON 格式
└── 存放在雲端硬碟
```

---

## 常見問題

### Q: 備份檔案在哪裡？

預設位置：
- Linux/Mac: `~/novel-backups/`
- Windows: `%USERPROFILE%\novel-backups\`

### Q: 如何修改備份保留天數？

```bash
# 保留 60 天
python scripts/backup.py backup --keep-days 60

# 或修改腳本中的 DEFAULT_KEEP_DAYS
```

### Q: 如何備份到自訂目錄？

```bash
# 指定備份目錄
python scripts/backup.py backup --backup-dir /path/to/backup

# 或設定環境變數
export BACKUP_DIR=/path/to/backup
```

### Q: 電腦掛掉後如何還原？

1. **從雲端同步資料夾還原**：
   - 備份檔案會自動同步到雲端
   - 在新電腦安裝雲端同步客戶端
   - 備份檔案會自動下載

2. **從備份還原**：
   ```bash
   # 找到最新的備份
   python scripts/backup.py list
   
   # 還原
   python scripts/backup.py restore --restore-file ~/novel-backups/novels_backup_20240101_120000.db
   ```

3. **從 JSON 匯入**：
   - 如果有導出的 JSON 檔案
   - 使用匯入 API 還原

---

## 備份驗證

定期驗證備份是否可用：

```bash
# 1. 建立備份
python scripts/backup.py backup

# 2. 還原到測試資料庫
python scripts/backup.py restore --restore-file ~/novel-backups/novels_backup_XXX.db --db data/test.db

# 3. 啟動服務測試
python main.py --db data/test.db
```
