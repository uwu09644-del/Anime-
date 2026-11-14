@echo off
rem Starts MangaShelf without a console window.
start "" powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0MangaShelf.ps1"
