#!/bin/bash
# 小說生成器 - 自動備份腳本
# Novel Generator - Auto Backup Script
#
# 使用方式：
# 1. 設定備份目錄（例如 Google Drive 同步資料夾）
# 2. 加入 crontab 定時執行
#
# 範例 crontab（每天凌晨 3 點備份）：
# 0 3 * * * /path/to/novel-generator/scripts/auto_backup.sh

# 設定
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-$HOME/novel-backups}"
DB_PATH="$PROJECT_DIR/data/novels.db"
KEEP_DAYS=30

# 建立備份目錄
mkdir -p "$BACKUP_DIR"

# 產生備份檔名
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/novels_backup_${TIMESTAMP}.db"

# 備份
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$BACKUP_FILE"
    echo "[$(date)] ✅ 備份成功: $BACKUP_FILE"
else
    echo "[$(date)] ❌ 資料庫不存在: $DB_PATH"
    exit 1
fi

# 清理舊備份
find "$BACKUP_DIR" -name "novels_backup_*.db" -mtime +$KEEP_DAYS -delete
echo "[$(date)] 🗑️  已清理超過 $KEEP_DAYS 天的舊備份"

# 計算備份數量
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/novels_backup_*.db 2>/dev/null | wc -l)
echo "[$(date)] 📦 目前共有 $BACKUP_COUNT 個備份"
