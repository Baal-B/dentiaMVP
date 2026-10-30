@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe scrape.py >> scrape.log 2>&1