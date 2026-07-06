#!/usr/bin/env python3
"""
小說生成器 - 一鍵搬家工具
Novel Generator - Migration Tool

把整套服務搬到另一台電腦只需要三樣東西：
1. data/novels.db          - 所有小說、章節、版本歷史、角色
2. .env                    - LLM API key 等環境設定
3. ~/.cloudflared/         - Cloudflare Tunnel 憑證（cert.pem + tunnel JSON）

程式碼本身在 GitHub 上，Cloudflare Access / DNS 設定在雲端，都不用搬。

用法：
    # 舊機器：打包（產生 novel-forge-migration_<時間>.zip）
    python scripts/migrate_export.py pack

    # 新機器：先 git clone 專案並進入目錄，再還原
    python scripts/migrate_export.py unpack --file novel-forge-migration_XXX.zip

⚠️ 打包出來的 zip 含有 API key 與 Tunnel 憑證，請用隨身碟或加密通道傳輸，
   搬完之後記得刪除。
"""

import argparse
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


PROJECT_DIR = Path(__file__).parent.parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "novels.db"
DEFAULT_ENV_PATH = PROJECT_DIR / ".env"
DEFAULT_CLOUDFLARED_DIR = Path.home() / ".cloudflared"

# zip 內的固定路徑
ZIP_DB = "novels.db"
ZIP_ENV = ".env"
ZIP_CLOUDFLARED_PREFIX = "cloudflared/"


def pack(db_path: Path, env_path: Path, cloudflared_dir: Path, output: Path) -> bool:
    """打包搬家 zip"""
    packed_anything = False

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 資料庫：用 SQLite backup API 抓一致性快照（服務跑著也安全）
        if db_path.exists():
            with tempfile.TemporaryDirectory() as td:
                snapshot = Path(td) / "novels.db"
                source = sqlite3.connect(str(db_path))
                dest = sqlite3.connect(str(snapshot))
                source.backup(dest)
                source.close()
                dest.close()
                zf.write(snapshot, ZIP_DB)
            print(f"✅ 資料庫: {db_path}")
            packed_anything = True
        else:
            print(f"⚠️ 找不到資料庫，略過: {db_path}")

        # 2. 環境設定
        if env_path.exists():
            zf.write(env_path, ZIP_ENV)
            print(f"✅ 環境設定: {env_path}")
            packed_anything = True
        else:
            print(f"⚠️ 找不到 .env，略過: {env_path}")

        # 3. Cloudflare Tunnel 憑證（cert.pem + tunnel 的 credentials JSON）
        cf_count = 0
        if cloudflared_dir.exists():
            for f in sorted(cloudflared_dir.iterdir()):
                if f.is_file() and (f.name == "cert.pem" or f.suffix == ".json"):
                    zf.write(f, ZIP_CLOUDFLARED_PREFIX + f.name)
                    cf_count += 1
        if cf_count > 0:
            print(f"✅ Tunnel 憑證: {cloudflared_dir}（{cf_count} 個檔案）")
            packed_anything = True
        else:
            print(f"⚠️ 找不到 Tunnel 憑證，略過: {cloudflared_dir}")

    if not packed_anything:
        output.unlink(missing_ok=True)
        print("❌ 沒有任何東西可以打包")
        return False

    size_kb = output.stat().st_size / 1024
    print(f"\n📦 打包完成: {output}（{size_kb:.1f} KB）")
    print("⚠️ 這個 zip 含有 API key 與 Tunnel 憑證，傳輸完成後請刪除")
    print("\n新機器上的還原步驟：")
    print("  git clone https://github.com/b3401069-ops/novel-generator.git")
    print("  cd novel-generator")
    print(f"  python scripts/migrate_export.py unpack --file {output.name}")
    return True


def _backup_existing(path: Path, timestamp: str) -> None:
    """還原前先備份既有檔案，避免覆蓋掉唯一的資料"""
    if path.exists():
        backup = path.with_name(f"{path.name}.pre_migrate_{timestamp}")
        shutil.copy2(path, backup)
        print(f"📋 既有檔案已備份: {backup}")


def unpack(zip_path: Path, db_path: Path, env_path: Path, cloudflared_dir: Path) -> bool:
    """從搬家 zip 還原"""
    if not zip_path.exists():
        print(f"❌ 找不到搬家檔案: {zip_path}")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    restored = 0

    # 只處理已知路徑，逐一寫到指定位置（不用 extractall，避免 zip 內惡意路徑）
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        if ZIP_DB in names:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _backup_existing(db_path, timestamp)
            with zf.open(ZIP_DB) as src, open(db_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"✅ 資料庫還原: {db_path}")
            restored += 1

        if ZIP_ENV in names:
            _backup_existing(env_path, timestamp)
            with zf.open(ZIP_ENV) as src, open(env_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"✅ 環境設定還原: {env_path}")
            restored += 1

        cf_names = [
            n for n in names
            if n.startswith(ZIP_CLOUDFLARED_PREFIX) and "/" not in n[len(ZIP_CLOUDFLARED_PREFIX):]
        ]
        if cf_names:
            cloudflared_dir.mkdir(parents=True, exist_ok=True)
            for name in cf_names:
                target = cloudflared_dir / Path(name).name
                _backup_existing(target, timestamp)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            print(f"✅ Tunnel 憑證還原: {cloudflared_dir}（{len(cf_names)} 個檔案）")
            restored += 1

    if restored == 0:
        print("❌ zip 裡沒有可辨識的搬家內容（不是本工具打包的？）")
        return False

    print("\n🎉 還原完成，接下來：")
    print("  pip install -r requirements.txt   # 若尚未安裝依賴")
    print("  python main.py                    # 啟動服務")
    print("  cloudflared tunnel run novel-generator   # 啟動 tunnel")
    print("（DNS 指向 tunnel，不用改任何 Cloudflare 設定）")
    return True


def main():
    parser = argparse.ArgumentParser(description="小說生成器一鍵搬家工具")
    parser.add_argument("action", choices=["pack", "unpack"], help="pack=舊機打包 / unpack=新機還原")
    parser.add_argument("--file", type=Path, help="unpack 時指定 zip；pack 時指定輸出檔名（可省略）")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="資料庫路徑")
    parser.add_argument("--env-path", type=Path, default=DEFAULT_ENV_PATH, help=".env 路徑")
    parser.add_argument("--cloudflared-dir", type=Path, default=DEFAULT_CLOUDFLARED_DIR,
                        help="cloudflared 憑證目錄")

    args = parser.parse_args()

    if args.action == "pack":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = args.file or PROJECT_DIR / f"novel-forge-migration_{timestamp}.zip"
        ok = pack(args.db, args.env_path, args.cloudflared_dir, output)
    else:
        if not args.file:
            print("❌ 請指定搬家檔案: --file <zip>")
            sys.exit(1)
        ok = unpack(args.file, args.db, args.env_path, args.cloudflared_dir)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
