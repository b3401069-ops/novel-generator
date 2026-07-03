@echo off
REM 小說生成器 - 自動備份腳本 (Windows)
REM Novel Generator - Auto Backup Script (Windows)
REM
REM 使用方式：
REM 1. 設定備份目錄（例如 Google Drive 同步資料夾）
REM 2. 加入 Windows 工作排程器定時執行
REM
REM 範例排程：
REM - 觸發器：每天凌晨 3:00
REM - 動作：執行此腳本

setlocal enabledelayedexpansion

REM 設定
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "BACKUP_DIR=%USERPROFILE%\novel-backups"
set "DB_PATH=%PROJECT_DIR%\data\novels.db"
set "KEEP_DAYS=30"

REM 建立備份目錄
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM 產生備份檔名
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set "TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%"
set "BACKUP_FILE=%BACKUP_DIR%\novels_backup_%TIMESTAMP%.db"

REM 備份
if exist "%DB_PATH%" (
    copy "%DB_PATH%" "%BACKUP_FILE%" >nul
    echo [%date% %time%] ✅ 備份成功: %BACKUP_FILE%
) else (
    echo [%date% %time%] ❌ 資料庫不存在: %DB_PATH%
    exit /b 1
)

REM 清理舊備份
forfiles /p "%BACKUP_DIR%" /m novels_backup_*.db /d -%KEEP_DAYS% /c "cmd /c del @path" 2>nul
echo [%date% %time%] 🗑️  已清理超過 %KEEP_DAYS% 天的舊備份

REM 計算備份數量
set count=0
for %%f in ("%BACKUP_DIR%\novels_backup_*.db") do set /a count+=1
echo [%date% %time%] 📦 目前共有 %count% 個備份

endlocal
