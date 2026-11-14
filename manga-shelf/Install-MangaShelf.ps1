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
$tmp = $env:TEMP
if ($tmp -notmatch '^[\x00-\x7F]+$') { $tmp = $env:PUBLIC }    # need a folder name with only English letters
$tmpLnk = Join-Path $tmp 'MangaShelf-new.lnk'
foreach ($dir in @([Environment]::GetFolderPath('Desktop'), (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs'))) {
    try {
        # The shortcut tool cannot save into folders with non-English names, so build it in a plain
        # temp folder first and then move it into place.
        $lnk = $ws.CreateShortcut($tmpLnk)
        $lnk.TargetPath       = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $lnk.Arguments        = "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
        $lnk.WorkingDirectory = $d
        $lnk.IconLocation     = (Join-Path $env:WINDIR 'System32\imageres.dll') + ',187'
        $lnk.Description      = 'MangaShelf manga reader'
        $lnk.Save()
        $dest = Join-Path $dir 'MangaShelf.lnk'
        [IO.File]::Copy($tmpLnk, $dest, $true)
        [IO.File]::Delete($tmpLnk)
        Write-Host "Icon created: $dest"
    } catch {
        Write-Host "Could not create an icon in $dir ($($_.Exception.Message)). You can still start the app with Start-MangaShelf.bat in $d" -ForegroundColor Yellow
    }
}

Write-Host ''
Write-Host 'MangaShelf installed. Use the MangaShelf icon on your Desktop or in the Start menu.' -ForegroundColor Green
Start-Process -FilePath (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') `
    -ArgumentList "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ps1`""
