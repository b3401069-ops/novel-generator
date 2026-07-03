#!/bin/bash
# 小說生成器 - 一鍵復原腳本
# Novel Generator - One-Click Restore Script
#
# 使用方式：
# ./scripts/restore.sh [備份目錄]
#
# 範例：
# ./scripts/restore.sh ~/Google\ Drive/novel-backups
# ./scripts/restore.sh ~/Dropbox/novel-backups

set -e

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_BACKUP_DIR="$HOME/novel-backups"
BACKUP_DIR="${1:-$DEFAULT_BACKUP_DIR}"
DB_PATH="$PROJECT_DIR/data/novels.db"

echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           小說生成器 - 一鍵復原腳本                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 檢查備份目錄
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ 備份目錄不存在: $BACKUP_DIR${NC}"
    echo ""
    echo "請指定備份目錄，例如："
    echo "  ./scripts/restore.sh ~/Google\\ Drive/novel-backups"
    echo "  ./scripts/restore.sh ~/Dropbox/novel-backups"
    exit 1
fi

# 列出可用的備份
echo -e "${YELLOW}📦 在 $BACKUP_DIR 中找到以下備份：${NC}"
echo ""

BACKUPS=($(ls -1 "$BACKUP_DIR"/novels_backup_*.db 2>/dev/null | sort -r))

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo -e "${RED}❌ 沒有找到備份檔案${NC}"
    exit 1
fi

for i in "${!BACKUPS[@]}"; do
    BACKUP_FILE="${BACKUPS[$i]}"
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    DATE=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$BACKUP_FILE" 2>/dev/null || stat -c "%y" "$BACKUP_FILE" 2>/dev/null | cut -d'.' -f1)
    echo -e "  ${GREEN}[$i]${NC} $(basename "$BACKUP_FILE")"
    echo -e "      大小: $SIZE"
    echo -e "      時間: $DATE"
    echo ""
done

# 選擇備份
if [ ${#BACKUPS[@]} -eq 1 ]; then
    SELECTED=0
    echo -e "${YELLOW}自動選擇唯一的備份${NC}"
else
    read -p "請選擇要還原的備份 [0]: " SELECTED
    SELECTED=${SELECTED:-0}
fi

if [ "$SELECTED" -lt 0 ] || [ "$SELECTED" -ge ${#BACKUPS[@]} ]; then
    echo -e "${RED}❌ 無效的選擇${NC}"
    exit 1
fi

SELECTED_BACKUP="${BACKUPS[$SELECTED]}"
echo ""
echo -e "${YELLOW}📋 將還原: $(basename "$SELECTED_BACKUP")${NC}"
echo ""

# 確認
read -p "確定要還原嗎？(y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${YELLOW}取消還原${NC}"
    exit 0
fi

# 建立資料目錄
mkdir -p "$PROJECT_DIR/data"

# 備份目前的資料庫（如果存在）
if [ -f "$DB_PATH" ]; then
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    PRE_RESTORE_BACKUP="$PROJECT_DIR/data/novels_pre_restore_${TIMESTAMP}.db"
    cp "$DB_PATH" "$PRE_RESTORE_BACKUP"
    echo -e "${GREEN}📋 已備份目前資料庫: $PRE_RESTORE_BACKUP${NC}"
fi

# 還原
cp "$SELECTED_BACKUP" "$DB_PATH"
echo -e "${GREEN}✅ 還原成功！${NC}"
echo ""

# 驗證
if [ -f "$DB_PATH" ]; then
    SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo -e "${GREEN}📊 資料庫大小: $SIZE${NC}"
fi

echo ""
echo -e "${GREEN}🎉 復原完成！${NC}"
echo ""
echo "下一步："
echo "  1. 啟動服務: python main.py"
echo "  2. 訪問: http://localhost:8012"
echo "  3. 設定 Cloudflare Tunnel（如果需要）"
echo ""
