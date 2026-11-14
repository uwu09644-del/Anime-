# MangaShelf installer / updater.
# Downloads the newest version to C:\Users\<you>\MangaShelf, makes Desktop + Start menu icons, and starts the app.
# Your downloaded manga (C:\Users\<you>\Manga) is never touched.
[Net.ServicePointManager]::SecurityProtocol = 0
$ErrorActionPreference = 'Stop'

$d = Join-Path $HOME 'MangaShelf'
$u = 'https://raw.githubusercontent.com/uwu09644-del/Anime-/claude/fervent-lovelace-ftj9pi/manga-shelf'
New-Item -ItemType Directory -Force -Path $d | Out-Null

foreach ($f in 'MangaShelf.ps1', 'Start-MangaShelf.bat', 'Debug-MangaShelf.bat') {
    Write-Host "Downloading $f ..."
    Invoke-WebRequest -Uri "$u/$f`?nocache=$(Get-Random)" -OutFile (Join-Path $d $f) -UseBasicParsing
}
Get-ChildItem -LiteralPath $d | Unblock-File

# Desktop + Start menu icons (replaces any old ones)
$ps1 = Join-Path $d 'MangaShelf.ps1'
$ws  = New-Object -ComObject WScript.Shell
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))) {
    $path = Join-Path $dir 'MangaShelf.lnk'
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
    $lnk = $ws.CreateShortcut($path)
    $lnk.TargetPath       = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $lnk.Arguments        = "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
    $lnk.WorkingDirectory = $d
    $lnk.IconLocation     = (Join-Path $env:WINDIR 'System32\imageres.dll') + ',187'
    $lnk.Description      = 'MangaShelf manga reader'
    $lnk.Save()
}

Write-Host ''
Write-Host 'MangaShelf installed. Use the MangaShelf icon on your Desktop or in the Start menu.' -ForegroundColor Green
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') `
    -ArgumentList "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
