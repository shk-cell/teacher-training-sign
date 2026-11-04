@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 교직원 연수 서버
if exist ".venv\Scripts\python.exe" goto ready
py -3 --version >nul 2>&1
if errorlevel 1 goto nopython
py -3 -m venv .venv
if errorlevel 1 goto failed
:ready
".venv\Scripts\python.exe" -c "import flask, pymupdf, openpyxl, docx, waitress, PIL, tzdata" >nul 2>&1
if not errorlevel 1 goto start
".venv\Scripts\python.exe" -m pip --version >nul 2>&1
if not errorlevel 1 goto install
".venv\Scripts\python.exe" -m ensurepip --upgrade
if errorlevel 1 goto failed
:install
echo 처음 실행에 필요한 구성요소를 설치합니다. 인터넷 연결이 필요합니다.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:start
".venv\Scripts\python.exe" server.py
if errorlevel 1 goto failed
pause
exit /b
:nopython
echo Python 3.11 이상을 먼저 설치해 주세요: https://www.python.org/downloads/
echo 설치할 때 Python Launcher도 함께 설치해 주세요.
pause
exit /b 1
:failed
echo 실행하지 못했습니다. 위 오류 내용을 확인해 주세요.
pause
exit /b 1
