r"""개발용: .venv\Scripts\python.exe build_exe.py"""
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent


if __name__ == "__main__":
    scratch = ROOT / "build" / "temp"
    scratch.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(TEMP=str(scratch), TMP=str(scratch))
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", "교직원연수실",
        "--icon", str(ROOT / "assets" / "app.ico"),
        "--distpath", str(ROOT), "--workpath", str(ROOT / "build" / "work"),
        "--specpath", str(ROOT / "build"),
        "--add-data", f"{ROOT / 'web'};web",
        "--add-data", f"{ROOT / 'assets'};assets",
        "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.txt'};.",
        "--collect-data", "docx", "--collect-data", "tzdata",
        "--collect-data", "customtkinter",
        "--collect-data", "hwpx",
        "--collect-submodules", "hwpx",
        str(ROOT / "desktop.py"),
    ], check=True, cwd=ROOT, env=env)
    print(f"EXE: {ROOT / '교직원연수실.exe'}")
    package = ROOT / "교직원연수실_배포용.zip"
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT / "교직원연수실.exe", "교직원연수실/교직원연수실.exe")
        archive.write(ROOT / "사용안내.txt", "교직원연수실/사용안내.txt")
        archive.write(ROOT / "THIRD_PARTY_NOTICES.txt", "교직원연수실/THIRD_PARTY_NOTICES.txt")
        archive.writestr("교직원연수실/연수자료/", "")
    print(f"Distribution ZIP: {package}")
