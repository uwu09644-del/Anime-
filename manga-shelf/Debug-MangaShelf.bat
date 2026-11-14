@echo off
rem Runs MangaShelf with a visible console so you can see any errors.
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0MangaShelf.ps1"
echo.
echo MangaShelf closed. Copy any red text above and send it.
pause
