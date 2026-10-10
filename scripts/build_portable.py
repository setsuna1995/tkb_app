"""Đóng gói bản Portable (giải nén là chạy, không cần cài Python).

    python scripts/build_portable.py

Kết quả trong dist/:
    TKB_App_Portable/        thư mục chạy được ngay (python/ app/ data_truong/ backups/ + file .bat)
    TKB_App_Portable.zip     bản phát hành đầy đủ cho máy mới
    TKB_App_Update.zip       chỉ thư mục app/ -> đưa lên GitHub Releases cho Cap_Nhat_Phan_Mem.bat

Python embeddable cùng phiên bản với Python đang chạy script (để wheel tương thích).
Chạy lại script KHÔNG ghi đè data_truong/ đã có trong dist (giữ dữ liệu thử nghiệm).
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zipfile
from importlib.metadata import version
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
OUT = DIST / "TKB_App_Portable"
CACHE = REPO / "build" / "cache"
PY_VER = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
PY_TAG = f"python{sys.version_info.major}{sys.version_info.minor}"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip"
UPDATE_URL = "https://github.com/setsuna1995/tkb_app/releases/latest/download/TKB_App_Update.zip"

APP_FILES = ["app.py", "desktop_app.py", "ui_common.py", "ui_theme.py", "requirements.txt"]
APP_DIRS = ["pages", "core", "data", "io_excel"]
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "*.bak", "*.db-wal", "*.db-shm", "*.db-journal")

CHAY_BAT = r"""@echo off
chcp 65001 >nul
set "TKB_HOME=%~dp0"
set "PYTHONNOUSERSITE=1"
set "TKB_DATA_DIR=%~dp0data_truong"
cd /d "%~dp0app"
"%~dp0python\python.exe" desktop_app.py
if errorlevel 1 if not defined TKB_HIDDEN pause
"""

CHAY_VBS = r'''Set sh = CreateObject("WScript.Shell")
sh.Environment("Process")("TKB_HIDDEN") = "1"
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c """ & root & "\Chay_TKB.bat""", 0, False
'''

CAP_NHAT_BAT = r"""@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0"
set "UPDATE_URL=__UPDATE_URL__"
echo === CAP NHAT PHAN MEM XEP TKB ===
echo.
echo Hay DONG cua so phan mem truoc khi cap nhat.
pause

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
echo [1/4] Sao luu du lieu -^> backups\backup_%TS%
robocopy "%ROOT%data_truong" "%ROOT%backups\backup_%TS%" /E /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :fail

set "ZIP=%TEMP%\TKB_App_Update.zip"
set "NEW=%TEMP%\TKB_App_Update"
if exist "%~dp0TKB_App_Update.zip" (
    echo [2/4] Dung file TKB_App_Update.zip co san canh file nay
    copy /y "%~dp0TKB_App_Update.zip" "%ZIP%" >nul
) else (
    echo [2/4] Tai ban moi...
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing '%UPDATE_URL%' -OutFile '%ZIP%'" || goto :fail
)
if exist "%NEW%" rmdir /s /q "%NEW%"
powershell -NoProfile -Command "Expand-Archive -Force '%ZIP%' '%NEW%'" || goto :fail
if not exist "%NEW%\app\app.py" goto :fail
robocopy "%NEW%\app" "%ROOT%app" /MIR /NFL /NDL /NJH /NJS >nul
if errorlevel 8 goto :fail

echo [3/4] Cai thu vien moi (neu co)...
"%ROOT%python\python.exe" -m pip install -q --disable-pip-version-check --target "%ROOT%python\Lib\site-packages" -r "%ROOT%app\requirements.txt" >nul 2>&1

echo [4/4] Xong! Cap nhat phien ban moi thanh cong. Du lieu cua ban da duoc sao luu an toan.
pause
exit /b 0

:fail
echo.
echo LOI: Cap nhat that bai. Du lieu KHONG bi thay doi (ban sao luu: backups\backup_%TS%).
pause
exit /b 1
"""

HUONG_DAN = """PHẦN MỀM XẾP THỜI KHÓA BIỂU — BẢN PORTABLE
==========================================

MỞ PHẦN MỀM
  Nhấp đúp  Chay_TKB_An_Console.vbs   (mở cửa sổ phần mềm, không hiện màn hình đen)
  hoặc      Chay_TKB.bat              (có màn hình đen — dùng khi cần xem lỗi)
  Đóng cửa sổ phần mềm là tắt hẳn chương trình.

DỮ LIỆU
  data_truong\\   Cơ sở dữ liệu từng trường (*.db). Sao chép thư mục này để sao lưu.
  backups\\       Bản sao lưu tự động tạo trước mỗi lần cập nhật.

CẬP NHẬT
  Đóng phần mềm, nhấp đúp Cap_Nhat_Phan_Mem.bat (cần Internet).
  Không có mạng: chép file TKB_App_Update.zip vào cạnh Cap_Nhat_Phan_Mem.bat rồi chạy.
  Cập nhật chỉ thay thư mục app\\ — dữ liệu trong data_truong\\ được giữ nguyên.

YÊU CẦU
  Windows 10/11 64-bit (có sẵn trình duyệt Microsoft Edge).
  Có thể chép cả thư mục sang USB / ổ D / Desktop để dùng.
"""


def _embed_zip() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    z = CACHE / f"python-{PY_VER}-embed-amd64.zip"
    if not z.exists():
        print(f"Tải {EMBED_URL}")
        urllib.request.urlretrieve(EMBED_URL, z)
    return z


def _requirement_names() -> list[str]:
    lines = (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
    return [re.split(r"[<>=!~;\[ ]", ln.strip(), maxsplit=1)[0] for ln in lines if ln.strip() and not ln.startswith("#")]


def _install_python() -> None:
    py = OUT / "python"
    if py.exists():
        shutil.rmtree(py)
    with zipfile.ZipFile(_embed_zip()) as z:
        z.extractall(py)
    # ._pth quyết định sys.path của bản embeddable: bật site + thêm site-packages và app/.
    (py / f"{PY_TAG}._pth").write_text(
        f"{PY_TAG}.zip\n.\nLib\\site-packages\n..\\app\nimport site\n", encoding="utf-8"
    )
    site = py / "Lib" / "site-packages"
    # Ghim đúng phiên bản đang dùng/test trên máy build (requirements.txt chỉ ghi ">=").
    pins = CACHE / "pins.txt"
    pin_lines = [f"{n}=={version(n)}" for n in _requirement_names()]
    pins.write_text("\n".join(pin_lines), encoding="utf-8")
    print("Cài thư viện (pip --target):", ", ".join(pin_lines))
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "--no-compile",
         "--target", str(site), "-r", str(pins), "pip"],
        check=True,
    )
    # Thư viện không cần lúc chạy -> bớt dung lượng.
    for junk in site.glob("*/tests"):
        shutil.rmtree(junk, ignore_errors=True)
    shutil.rmtree(site / "bin", ignore_errors=True)


def _copy_app(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in APP_FILES:
        shutil.copy2(REPO / f, dest / f)
    for d in APP_DIRS:
        shutil.copytree(REPO / d, dest / d, ignore=SKIP)
    (dest / ".streamlit").mkdir()
    shutil.copy2(REPO / ".streamlit" / "config.toml", dest / ".streamlit" / "config.toml")  # KHÔNG kèm secrets.toml


def _copy_school_dbs() -> None:
    data = OUT / "data_truong"
    if data.exists():
        print("data_truong/ đã có -> giữ nguyên")
        return
    data.mkdir(parents=True)
    for src in sorted((REPO / "schools").glob("*.db")):
        # backup API: gộp cả phần còn nằm trong file -wal
        with sqlite3.connect(src) as s, sqlite3.connect(data / src.name) as d:
            s.backup(d)
        print(f"  + {src.name}")


def _zip_dir(src: Path, zip_path: Path, arc_root: str) -> None:
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in sorted(src.rglob("*")):
            if f.is_file() and ".edge_profile" not in f.parts:
                z.write(f, Path(arc_root) / f.relative_to(src))


def main() -> None:
    if sys.platform != "win32" or sys.maxsize < 2**32:
        sys.exit("Cần chạy trên Windows 64-bit (bản đóng gói dùng wheel win_amd64).")
    DIST.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    update_only = "--update-only" in sys.argv or "-u" in sys.argv
    if update_only:
        print("Đang đóng gói nhanh bản update (TKB_App_Update.zip)...")
        _copy_app(OUT / "app")
        _zip_dir(OUT / "app", DIST / "TKB_App_Update.zip", "app")
        z_update = DIST / "TKB_App_Update.zip"
        print(f"Xong bản update: {z_update} ({z_update.stat().st_size / 1e6:.1f} MB)")
        return

    _install_python()
    _copy_app(OUT / "app")
    _copy_school_dbs()
    (OUT / "backups").mkdir(exist_ok=True)
    for name, text in {
        "Chay_TKB.bat": CHAY_BAT,
        "Chay_TKB_An_Console.vbs": CHAY_VBS,
        "Cap_Nhat_Phan_Mem.bat": CAP_NHAT_BAT.replace("__UPDATE_URL__", UPDATE_URL),
    }.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\r\n")
    (OUT / "Huong_Dan_Su_Dung.txt").write_text(HUONG_DAN, encoding="utf-8-sig", newline="\r\n")

    print("Nén zip...")
    _zip_dir(OUT, DIST / "TKB_App_Portable.zip", "TKB_App_Portable")
    _zip_dir(OUT / "app", DIST / "TKB_App_Update.zip", "app")
    for z in ("TKB_App_Portable.zip", "TKB_App_Update.zip"):
        print(f"  {z}: {(DIST / z).stat().st_size / 1e6:.1f} MB")
    print(f"Xong: {OUT}")


if __name__ == "__main__":
    main()
