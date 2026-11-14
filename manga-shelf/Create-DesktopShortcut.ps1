# Run once (right-click > Run with PowerShell) to add MangaShelf to your Desktop and Start menu.
$ws     = New-Object -ComObject WScript.Shell
$script = Join-Path $PSScriptRoot 'MangaShelf.ps1'
$places = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs')
)
foreach ($dir in $places) {
    $lnk = $ws.CreateShortcut((Join-Path $dir 'MangaShelf.lnk'))
    $lnk.TargetPath       = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $lnk.Arguments        = "-NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.IconLocation     = (Join-Path $env:WINDIR 'System32\imageres.dll') + ',187'
    $lnk.Description      = 'MangaShelf manga reader'
    $lnk.Save()
}
Write-Host 'MangaShelf shortcuts created on your Desktop and in the Start menu.'
