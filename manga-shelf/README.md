# MangaShelf

A Windows desktop app for finding, downloading and reading manga. It is written in PowerShell and WPF, so there is nothing to install.

- **Search & Download**: type a title and press Enter, pick a result, then press **Download to library**. Chapters download in the background, and partly finished downloads pick up where they left off.
- **Library**: everything you have downloaded, with covers and read marks. **Continue reading** opens your first unread chapter. **Check for new chapters** downloads chapters that came out since your last download.
- **Reader**: scroll down to read, and use the zoom slider to resize pages. Left/Right arrow = previous/next chapter, Esc = close.

Search and chapters come from the public [MangaDex](https://mangadex.org) API. Licensed series often have no chapters there, so read those on the official sites.

## Install or update

Open **Windows PowerShell** and paste:

```
[Net.ServicePointManager]::SecurityProtocol=0; irm https://raw.githubusercontent.com/uwu09644-del/Anime-/claude/fervent-lovelace-ftj9pi/manga-shelf/Install-MangaShelf.ps1 | iex
```

This puts the app in `C:\Users\<you>\MangaShelf`, adds a **MangaShelf** icon to your Desktop and Start menu, and opens it. Run the same command again any time to update. Your manga is kept.

If the app won't open, run `Debug-MangaShelf.bat` in that folder to see the error.

Manga is saved to `C:\Users\<you>\Manga\<Series>\Chapter 0001\001.jpg`. To use a different folder, run:

```
powershell -STA -ExecutionPolicy Bypass -File MangaShelf.ps1 -Library "D:\Manga"
```

Requires Windows 10/11, which already includes Windows PowerShell 5.1 and .NET Framework 4.8.
