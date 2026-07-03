#!/usr/bin/env python3
"""
小說生成器 - 自動備份腳本
Novel Generator - Auto Backup Script

功能：
- 定時備份資料庫
- 保留最近 N 天的備份
- 支援手動觸發
- 可指定備份目錄（例如雲端同步資料夾）
"""

import os
import sys
import shutil
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path


# 配置
DEFAULT_BACKUP_DIR = Path.home() / "novel-backups"
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "novels.db"
DEFAULT_KEEP_DAYS = 30


def create_backup(db_path: Path, backup_dir: Path, keep_days: int = DEFAULT_KEEP_DAYS):
    """
    建立備份
    
    Args:
        db_path: 資料庫路徑
        backup_dir: 備份目錄
        keep_days: 保留天數
    """
    # 確保備份目錄存在
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 檢查資料庫是否存在
    if not db_path.exists():
        print(f"❌ 資料庫不存在: {db_path}")
        return False
    
    # 產生備份檔名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"novels_backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename
    
    try:
        # 使用 SQLite 的備份 API（更安全）
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(str(backup_path))
        source.backup(dest)
        source.close()
        dest.close()
        
        print(f"✅ 備份成功: {backup_path}")
        print(f"   大小: {backup_path.stat().st_size / 1024:.2f} KB")
        
        # 清理舊備份
        cleanup_old_backups(backup_dir, keep_days)
        
        return True
        
    except Exception as e:
        print(f"❌ 備份失敗: {e}")
        return False


def cleanup_old_backups(backup_dir: Path, keep_days: int):
    """清理舊備份"""
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    deleted_count = 0
    for backup_file in backup_dir.glob("novels_backup_*.db"):
        # 從檔名提取日期
        try:
            date_str = backup_file.stem.split("_")[2] + "_" + backup_file.stem.split("_")[3]
            file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            
            if file_date < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
        except (ValueError, IndexError):
            continue
    
    if deleted_count > 0:
        print(f"🗑️  已清理 {deleted_count} 個舊備份（超過 {keep_days} 天）")


def list_backups(backup_dir: Path):
    """列出所有備份"""
    backups = sorted(backup_dir.glob("novels_backup_*.db"), reverse=True)
    
    if not backups:
        print("📭 沒有備份")
        return
    
    print(f"📦 共 {len(backups)} 個備份：\n")
    for backup in backups:
        size = backup.stat().st_size / 1024
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"  📄 {backup.name}")
        print(f"     大小: {size:.2f} KB")
        print(f"     時間: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()


def restore_backup(backup_path: Path, db_path: Path):
    """還原備份"""
    if not backup_path.exists():
        print(f"❌ 備份檔案不存在: {backup_path}")
        return False
    
    # 備份目前的資料庫
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_backup = db_path.parent / f"novels_pre_restore_{timestamp}.db"
        shutil.copy2(db_path, pre_restore_backup)
        print(f"📋 已備份目前資料庫: {pre_restore_backup}")
    
    try:
        # 還原
        shutil.copy2(backup_path, db_path)
        print(f"✅ 還原成功: {backup_path} → {db_path}")
        return True
    except Exception as e:
        print(f"❌ 還原失敗: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="小說生成器備份工具")
    parser.add_argument("action", choices=["backup", "list", "restore"],
                        help="操作類型")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH,
                        help="資料庫路徑")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR,
                        help="備份目錄")
    parser.add_argument("--keep-days", type=int, default=DEFAULT_KEEP_DAYS,
                        help="保留天數")
    parser.add_argument("--restore-file", type=Path,
                        help="還原的備份檔案")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        create_backup(args.db, args.backup_dir, args.keep_days)
    elif args.action == "list":
        list_backups(args.backup_dir)
    elif args.action == "restore":
        if not args.restore_file:
            print("❌ 請指定還原檔案: --restore-file <path>")
            sys.exit(1)
        restore_backup(args.restore_file, args.db)


if __name__ == "__main__":
    main()
