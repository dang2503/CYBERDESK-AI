@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Create the virtual environment and install requirements.txt first. See README.md.
    exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m streamlit run app.py --server.address=127.0.0.1 --server.headless=false
