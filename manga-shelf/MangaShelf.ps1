<#
  MangaShelf - a desktop manga app for Windows (PowerShell + WPF).

  * Search tab : search MangaDex, pick a result, press Download.
                 Chapters download in the background into your library folder.
  * Library tab: everything you have downloaded. Double-click a chapter to read.
  * Reader     : vertical scrolling, zoom slider, Left/Right = prev/next chapter, Esc = close.

  Run with Start-MangaShelf.bat (or Create-DesktopShortcut.ps1 once for a desktop icon).
#>
param(
    [string]$Library = (Join-Path $HOME 'Manga')
)

# WPF needs a single-threaded apartment. Relaunch if we are not in one.
if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    Start-Process powershell.exe -ArgumentList @('-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass',
        '-File', "`"$PSCommandPath`"", '-Library', "`"$Library`"")
    return
}

Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

# If anything crashes, show the error and save it instead of closing silently.
trap {
    $msg = "MangaShelf crashed:`n`n$($_.Exception.Message)`n`nLine $($_.InvocationInfo.ScriptLineNumber): $($_.InvocationInfo.Line.Trim())"
    $log = Join-Path $env:TEMP 'MangaShelf-error.txt'
    try { [IO.File]::WriteAllText($log, "$msg`n`n$($_.ScriptStackTrace)") } catch { }
    [void][System.Windows.MessageBox]::Show("$msg`n`n(Saved to $log)", 'MangaShelf error')
    exit 1
}

# Secure connection settings. Let Windows pick (TLS 1.3 on Windows 11); fall back if that fails.
$TlsModes = @(
    [Net.SecurityProtocolType]0,                    # Windows default (TLS 1.2 / 1.3)
    [Net.SecurityProtocolType](3072 -bor 12288),    # TLS 1.2 + TLS 1.3
    [Net.SecurityProtocolType]3072                  # TLS 1.2 only
)
try { [Net.ServicePointManager]::SecurityProtocol = $TlsModes[0] } catch { }

# Web request that retries with other TLS settings on "Could not create SSL/TLS secure channel"
function Invoke-MD([string]$url, [int]$timeout = 20) {
    $lastErr = $null
    foreach ($mode in (@($null) + $TlsModes)) {
        if ($null -ne $mode) { try { [Net.ServicePointManager]::SecurityProtocol = $mode } catch { continue } }
        try { return Invoke-RestMethod -Uri $url -UserAgent $UA -TimeoutSec $timeout }
        catch {
            $lastErr = $_
            if ("$($_.Exception.Message)" -notmatch 'SSL|TLS|secure channel|underlying connection') { throw }
        }
    }
    throw $lastErr
}

$Api      = 'https://api.mangadex.org'
$UA       = 'MangaShelf/1.0 (personal desktop reader)'
$ImgExt   = @('.jpg', '.jpeg', '.png', '.webp', '.gif')
[void][IO.Directory]::CreateDirectory($Library)
$ReadFile = Join-Path $Library '.mangashelf-read.json'

# ---------------------------------------------------------------- helpers
function NatSort {
    $input | Sort-Object { [regex]::Replace($_.Name, '\d+', { param($m) $m.Value.PadLeft(10, '0') }) }
}

function Load-Xaml([string]$text) {
    $xml = [xml]$text
    [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xml))
}

function Show-Msg([string]$text) { [void][System.Windows.MessageBox]::Show($text, 'MangaShelf') }

function Load-Read {
    $script:Read = @{}
    if ([IO.File]::Exists($ReadFile)) {
        try { foreach ($k in (Get-Content -LiteralPath $ReadFile -Raw | ConvertFrom-Json)) { $script:Read["$k"] = $true } } catch { }
    }
}
function Save-Read {
    try { [IO.File]::WriteAllText($ReadFile, (ConvertTo-Json -InputObject @($script:Read.Keys))) } catch { }
}

function Get-MangaTitle($attrs) {
    $t = $attrs.title
    if ($t.en) { return $t.en }
    foreach ($alt in @($attrs.altTitles)) { if ($alt.en) { return $alt.en } }
    $first = $t.PSObject.Properties | Select-Object -First 1
    if ($first) { return "$($first.Value)" }
    return 'Untitled'
}

# ---------------------------------------------------------------- background downloader
# Runs in its own runspace so the window never freezes. Talks to the UI through $sync.
$sync  = [hashtable]::Synchronized(@{ Status = 'Ready'; Progress = 0; LibraryChanged = $false; Gen = 0; CurrentId = $null; Quit = $false })
$queue = New-Object 'System.Collections.Concurrent.ConcurrentQueue[object]'

$worker = {
    param($sync, $queue, $Library, $UA, $Api, $TlsModes)

    function Call-Api([string]$path) {
        for ($try = 1; $try -le 5; $try++) {
            try {
                $r = $null
                foreach ($mode in (@($null) + $TlsModes)) {
                    if ($null -ne $mode) { try { [Net.ServicePointManager]::SecurityProtocol = $mode } catch { continue } }
                    try { $r = Invoke-RestMethod -Uri ($Api + $path) -UserAgent $UA -TimeoutSec 30; break }
                    catch { if ("$($_.Exception.Message)" -notmatch 'SSL|TLS|secure channel|underlying connection') { throw } }
                }
                if ($null -eq $r) { throw 'TLS connection failed' }
                Start-Sleep -Milliseconds 250          # stay well under MangaDex rate limits
                return $r
            } catch { Start-Sleep -Seconds (3 * $try) }
        }
        throw "MangaDex API request failed: $path"
    }

    function Get-File([string]$url, [string]$out) {
        for ($try = 1; $try -le 3; $try++) {
            $wc = New-Object Net.WebClient
            try {
                $wc.Headers.Add('User-Agent', $UA)
                $wc.DownloadFile($url, "$out.part")
                [IO.File]::Delete($out)
                [IO.File]::Move("$out.part", $out)
                return $true
            } catch { Start-Sleep -Seconds (2 * $try) } finally { $wc.Dispose() }
        }
        return $false
    }

    function Clean-Name([string]$s) {
        $s = ($s -replace '[\\/:*?"<>|\x00-\x1f]', '_').Trim().TrimEnd('.')
        if ($s.Length -gt 120) { $s = $s.Substring(0, 120).Trim() }
        if (-not $s) { $s = 'Untitled' }
        return $s
    }

    function Chapter-Folder($c) {
        $n = $c.attributes.chapter
        if ($n -match '^(\d+)(\.\d+)?$') { return ('Chapter {0}{1}' -f $matches[1].PadLeft(4, '0'), $matches[2]) }
        if ($n) { return 'Chapter ' + (Clean-Name $n) }
        $t = $c.attributes.title
        if (-not $t) { $t = $c.id.Substring(0, 8) }
        return 'Extra - ' + (Clean-Name $t)
    }

    while (-not $sync.Quit) {
        $job = $null
        if (-not $queue.TryDequeue([ref]$job)) { Start-Sleep -Milliseconds 300; continue }
        if ($job.Gen -ne $sync.Gen) { continue }       # cancelled before it started

        $sync.CurrentId = $job.Id
        $sync.Progress = 0
        $failed = 0; $new = 0
        try {
            $sync.Status = "Getting chapter list for $($job.Title)..."
            $dir = Join-Path $Library (Clean-Name $job.Title)
            [void][IO.Directory]::CreateDirectory($dir)
            $info = @{ id = $job.Id; lang = $job.Lang; title = $job.Title } | ConvertTo-Json
            [IO.File]::WriteAllText((Join-Path $dir 'info.json'), $info)

            $cover = Join-Path $dir 'cover.jpg'
            if ($job.CoverUrl -and -not [IO.File]::Exists($cover)) { [void](Get-File $job.CoverUrl $cover) }
            $sync.LibraryChanged = $true

            # Full chapter list (paged, 500 at a time)
            $all = @(); $offset = 0
            do {
                $feed = Call-Api ("/manga/$($job.Id)/feed?translatedLanguage[]=$($job.Lang)&order[volume]=asc&order[chapter]=asc" +
                                  "&limit=500&offset=$offset&includes[]=scanlation_group&includeExternalUrl=0" +
                                  "&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=erotica")
                $all += @($feed.data)
                $offset += 500
            } while ($offset -lt $feed.total -and $job.Gen -eq $sync.Gen)

            # One upload per chapter number (several groups often translate the same chapter)
            $seen = @{}; $list = @()
            foreach ($c in $all) {
                if ($c.attributes.pages -lt 1) { continue }
                $key = if ($c.attributes.chapter) { "$($c.attributes.chapter)" } else { "x$($c.id)" }
                if ($seen.ContainsKey($key)) { continue }
                $seen[$key] = $true; $list += $c
            }

            if ($list.Count -eq 0) {
                $sync.Status = "$($job.Title): no readable chapters on MangaDex in '$($job.Lang)' (it may be licensed - check the official site)."
                continue
            }

            for ($i = 0; $i -lt $list.Count; $i++) {
                if ($job.Gen -ne $sync.Gen -or $sync.Quit) { break }
                $c    = $list[$i]
                $cdir = Join-Path $dir (Chapter-Folder $c)
                $sync.Progress = [int](100 * $i / $list.Count)
                if ([IO.File]::Exists((Join-Path $cdir '.done'))) { continue }

                $sync.Status = "$($job.Title): chapter $($c.attributes.chapter) ($($i + 1)/$($list.Count))  +$($queue.Count) queued"
                $ah = Call-Api "/at-home/server/$($c.id)"
                [void][IO.Directory]::CreateDirectory($cdir)
                $grp = $c.relationships | Where-Object { $_.type -eq 'scanlation_group' } | Select-Object -First 1
                if ($grp -and $grp.attributes) { [IO.File]::WriteAllText((Join-Path $cdir '.group'), $grp.attributes.name) }

                $ok = $true; $p = 0
                foreach ($f in @($ah.chapter.data)) {
                    if ($job.Gen -ne $sync.Gen -or $sync.Quit) { $ok = $false; break }
                    $p++
                    $out = Join-Path $cdir ('{0:D3}{1}' -f $p, [IO.Path]::GetExtension($f))
                    if ([IO.File]::Exists($out)) { continue }
                    if (-not (Get-File "$($ah.baseUrl)/data/$($ah.chapter.hash)/$f" $out)) { $ok = $false }
                }
                if ($ok) { [IO.File]::WriteAllText((Join-Path $cdir '.done'), ''); $new++ } else { $failed++ }
                $sync.LibraryChanged = $true
                Start-Sleep -Milliseconds 1500                 # at-home endpoint allows ~40 calls/minute
            }

            $sync.Progress = 100
            if ($job.Gen -ne $sync.Gen) { $sync.Status = 'Downloads cancelled.' }
            elseif ($failed) { $sync.Status = "$($job.Title): $new new chapters, $failed failed (press 'Check for new chapters' to retry)." }
            else { $sync.Status = "$($job.Title): done, $new new chapters." }
        } catch {
            $sync.Status = "Error downloading $($job.Title): $($_.Exception.Message)"
        } finally {
            $sync.CurrentId = $null
            $sync.LibraryChanged = $true
        }
    }
}

$rs = [runspacefactory]::CreateRunspace()
$rs.Open()
$ps = [powershell]::Create()
$ps.Runspace = $rs
[void]$ps.AddScript($worker.ToString()).AddArgument($sync).AddArgument($queue).AddArgument($Library).AddArgument($UA).AddArgument($Api).AddArgument($TlsModes)
[void]$ps.BeginInvoke()

function Queue-Download($id, $title, $lang, $coverUrl) {
    if ($sync.CurrentId -eq $id -or ($queue.ToArray() | Where-Object { $_.Id -eq $id })) {
        Show-Msg "'$title' is already downloading."
        return
    }
    $queue.Enqueue([pscustomobject]@{ Id = $id; Title = $title; Lang = $lang; CoverUrl = $coverUrl; Gen = $sync.Gen })
    $Status.Text = "Queued: $title"
}

# ---------------------------------------------------------------- main window
$MainXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="MangaShelf" Width="1150" Height="780" Background="#1E1E1E" WindowStartupLocation="CenterScreen">
  <Window.Resources>
    <Style TargetType="Button">
      <Setter Property="Padding" Value="14,6"/>
      <Setter Property="Margin" Value="4"/>
    </Style>
  </Window.Resources>
  <DockPanel>
    <Border DockPanel.Dock="Bottom" Background="#111111" Padding="8,6">
      <DockPanel>
        <Button x:Name="CancelBtn" DockPanel.Dock="Right" Content="Cancel downloads"/>
        <ProgressBar x:Name="Progress" DockPanel.Dock="Right" Width="220" Height="14" Margin="8,0" Maximum="100"/>
        <TextBlock x:Name="Status" Text="Ready" Foreground="#DDDDDD" VerticalAlignment="Center" TextTrimming="CharacterEllipsis"/>
      </DockPanel>
    </Border>
    <TabControl x:Name="Tabs" Background="#1E1E1E" BorderThickness="0" Padding="0">

      <TabItem Header="  Library  ">
        <Grid Margin="8">
          <Grid.ColumnDefinitions>
            <ColumnDefinition Width="2*"/>
            <ColumnDefinition Width="3*"/>
          </Grid.ColumnDefinitions>
          <DockPanel Grid.Column="0" Margin="0,0,8,0">
            <StackPanel DockPanel.Dock="Top" Orientation="Horizontal">
              <TextBlock Text="My manga" Foreground="#EEEEEE" FontSize="20" FontWeight="Bold" VerticalAlignment="Center" Margin="4,0,12,0"/>
              <Button x:Name="RefreshBtn" Content="Refresh"/>
              <Button x:Name="FolderBtn" Content="Open folder"/>
            </StackPanel>
            <ListBox x:Name="SeriesList" Background="#252526" BorderThickness="0" HorizontalContentAlignment="Stretch"
                     ScrollViewer.HorizontalScrollBarVisibility="Disabled">
              <ListBox.ItemTemplate>
                <DataTemplate>
                  <Grid Margin="2">
                    <Grid.ColumnDefinitions>
                      <ColumnDefinition Width="Auto"/>
                      <ColumnDefinition Width="*"/>
                    </Grid.ColumnDefinitions>
                    <Border Width="56" Height="80" Background="#333333" Margin="0,0,10,0">
                      <Image Source="{Binding Cover}" Stretch="UniformToFill"/>
                    </Border>
                    <StackPanel Grid.Column="1" VerticalAlignment="Center">
                      <TextBlock Text="{Binding Name}" Foreground="#FFFFFF" FontSize="15" FontWeight="SemiBold" TextWrapping="Wrap"/>
                      <TextBlock Text="{Binding Info}" Foreground="#999999"/>
                    </StackPanel>
                  </Grid>
                </DataTemplate>
              </ListBox.ItemTemplate>
            </ListBox>
          </DockPanel>
          <DockPanel Grid.Column="1">
            <TextBlock x:Name="SeriesTitle" DockPanel.Dock="Top" Text="Pick a manga on the left" Foreground="#EEEEEE"
                       FontSize="20" FontWeight="Bold" TextWrapping="Wrap" Margin="4"/>
            <StackPanel DockPanel.Dock="Top" Orientation="Horizontal">
              <Button x:Name="ContinueBtn" Content="Continue reading"/>
              <Button x:Name="ReadBtn" Content="Read selected"/>
              <Button x:Name="UpdateBtn" Content="Check for new chapters"/>
            </StackPanel>
            <ListBox x:Name="ChapterList" Background="#252526" Foreground="#EEEEEE" BorderThickness="0" FontSize="14">
              <ListBox.ItemTemplate>
                <DataTemplate>
                  <TextBlock Text="{Binding Label}" Foreground="#EEEEEE" Margin="4,3"/>
                </DataTemplate>
              </ListBox.ItemTemplate>
            </ListBox>
          </DockPanel>
        </Grid>
      </TabItem>

      <TabItem Header="  Search &amp; Download  ">
        <DockPanel Margin="8">
          <DockPanel DockPanel.Dock="Top">
            <Button x:Name="SearchBtn" DockPanel.Dock="Right" Content="Search"/>
            <ComboBox x:Name="LangBox" DockPanel.Dock="Right" Width="80" Margin="4" SelectedIndex="0" VerticalContentAlignment="Center">
              <ComboBoxItem Content="en"/>
              <ComboBoxItem Content="es-la"/>
              <ComboBoxItem Content="es"/>
              <ComboBoxItem Content="pt-br"/>
              <ComboBoxItem Content="fr"/>
              <ComboBoxItem Content="de"/>
              <ComboBoxItem Content="it"/>
              <ComboBoxItem Content="ru"/>
              <ComboBoxItem Content="id"/>
              <ComboBoxItem Content="vi"/>
              <ComboBoxItem Content="tr"/>
              <ComboBoxItem Content="pl"/>
            </ComboBox>
            <TextBlock DockPanel.Dock="Right" Text="Language" Foreground="#AAAAAA" VerticalAlignment="Center" Margin="8,0,0,0"/>
            <TextBox x:Name="SearchBox" FontSize="16" Padding="6" Margin="4"/>
          </DockPanel>
          <DockPanel DockPanel.Dock="Bottom">
            <Button x:Name="DownloadBtn" DockPanel.Dock="Right" Content="Download to library" FontSize="14" FontWeight="Bold"/>
            <TextBlock Text="Search and chapters provided by MangaDex and its scanlation groups. Please support official releases."
                       Foreground="#777777" VerticalAlignment="Center" TextWrapping="Wrap"/>
          </DockPanel>
          <ListBox x:Name="Results" Background="#252526" BorderThickness="0" HorizontalContentAlignment="Stretch"
                   ScrollViewer.HorizontalScrollBarVisibility="Disabled">
            <ListBox.ItemTemplate>
              <DataTemplate>
                <Grid Margin="4">
                  <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="Auto"/>
                    <ColumnDefinition Width="*"/>
                  </Grid.ColumnDefinitions>
                  <Border Width="84" Height="120" Background="#333333" Margin="0,0,12,0">
                    <Image Source="{Binding Cover}" Stretch="UniformToFill"/>
                  </Border>
                  <StackPanel Grid.Column="1">
                    <TextBlock Text="{Binding Title}" Foreground="#FFFFFF" FontSize="17" FontWeight="Bold" TextWrapping="Wrap"/>
                    <TextBlock Text="{Binding Info}" Foreground="#88CCFF" Margin="0,2,0,4"/>
                    <TextBlock Text="{Binding Desc}" Foreground="#BBBBBB" TextWrapping="Wrap" MaxHeight="66" TextTrimming="WordEllipsis"/>
                  </StackPanel>
                </Grid>
              </DataTemplate>
            </ListBox.ItemTemplate>
          </ListBox>
        </DockPanel>
      </TabItem>

    </TabControl>
  </DockPanel>
</Window>
'@

$ReaderXaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Reader" Width="1000" Height="900" Background="Black" WindowStartupLocation="CenterOwner">
  <DockPanel>
    <Border DockPanel.Dock="Top" Background="#1A1A1A" Padding="6">
      <DockPanel>
        <StackPanel DockPanel.Dock="Right" Orientation="Horizontal">
          <TextBlock Text="Zoom" Foreground="#CCCCCC" VerticalAlignment="Center" Margin="8,0"/>
          <Slider x:Name="Zoom" Minimum="300" Maximum="2200" Value="800" Width="180" VerticalAlignment="Center"/>
        </StackPanel>
        <Button x:Name="PrevBtn" Content="&lt; Prev" Padding="12,4" Margin="2"/>
        <Button x:Name="NextBtn" Content="Next &gt;" Padding="12,4" Margin="2"/>
        <TextBlock x:Name="ChTitle" Foreground="#EEEEEE" FontSize="15" VerticalAlignment="Center" Margin="12,0" TextTrimming="CharacterEllipsis"/>
      </DockPanel>
    </Border>
    <Border DockPanel.Dock="Bottom" Background="#1A1A1A" Padding="6">
      <Button x:Name="NextBtn2" Content="Next chapter &gt;" HorizontalAlignment="Center" Padding="16,6"/>
    </Border>
    <ListBox x:Name="Pages" Background="Black" BorderThickness="0"
             VirtualizingPanel.IsVirtualizing="True" VirtualizingPanel.VirtualizationMode="Recycling"
             VirtualizingPanel.ScrollUnit="Pixel" ScrollViewer.HorizontalScrollBarVisibility="Auto">
      <ListBox.ItemContainerStyle>
        <Style TargetType="ListBoxItem">
          <Setter Property="Focusable" Value="False"/>
          <Setter Property="Template">
            <Setter.Value>
              <ControlTemplate TargetType="ListBoxItem">
                <ContentPresenter HorizontalAlignment="Center" Margin="0,0,0,4"/>
              </ControlTemplate>
            </Setter.Value>
          </Setter>
        </Style>
      </ListBox.ItemContainerStyle>
      <ListBox.ItemTemplate>
        <DataTemplate>
          <Image Source="{Binding File}" Width="{Binding Value, ElementName=Zoom}" Stretch="Uniform"/>
        </DataTemplate>
      </ListBox.ItemTemplate>
    </ListBox>
  </DockPanel>
</Window>
'@

$win = Load-Xaml $MainXaml
foreach ($n in 'CancelBtn', 'Progress', 'Status', 'Tabs', 'RefreshBtn', 'FolderBtn', 'SeriesList', 'SeriesTitle',
               'ContinueBtn', 'ReadBtn', 'UpdateBtn', 'ChapterList', 'SearchBtn', 'LangBox', 'SearchBox', 'DownloadBtn', 'Results') {
    Set-Variable -Name $n -Value $win.FindName($n) -Scope Script
}

# ---------------------------------------------------------------- library
function Get-ChapterDirs($seriesDir) { @(Get-ChildItem -LiteralPath $seriesDir -Directory | NatSort) }

function Refresh-Library {
    $selName = if ($SeriesList.SelectedItem) { $SeriesList.SelectedItem.Name } else { $null }
    $items = @(foreach ($d in (Get-ChildItem -LiteralPath $Library -Directory | NatSort)) {
        $cover = Join-Path $d.FullName 'cover.jpg'
        $chs = Get-ChapterDirs $d.FullName
        $read = @($chs | Where-Object { $script:Read.ContainsKey("$($d.Name)|$($_.Name)") }).Count
        [pscustomobject]@{
            Name  = $d.Name
            Dir   = $d.FullName
            Cover = $(if ([IO.File]::Exists($cover)) { $cover } else { $null })
            Info  = "$($chs.Count) chapters, $read read"
        }
    })
    $script:SeriesItems = $items
    $SeriesList.ItemsSource = $items
    for ($i = 0; $i -lt $items.Count; $i++) { if ($items[$i].Name -eq $selName) { $SeriesList.SelectedIndex = $i } }
    if ($items.Count -eq 0) { $SeriesTitle.Text = 'Your library is empty - go to "Search & Download".' }
}

function Refresh-Chapters {
    $s = $SeriesList.SelectedItem
    if (-not $s) { $ChapterList.ItemsSource = $null; return }
    $SeriesTitle.Text = $s.Name
    $keep = $ChapterList.SelectedIndex
    $check = [string][char]0x2713
    $ChapterList.ItemsSource = @(foreach ($c in (Get-ChapterDirs $s.Dir)) {
        $label = $c.Name
        if (-not [IO.File]::Exists((Join-Path $c.FullName '.done'))) { $label += '   (downloading...)' }
        if ($script:Read.ContainsKey("$($s.Name)|$($c.Name)")) { $label += "   $check read" }
        [pscustomobject]@{ Name = $c.Name; Label = $label }
    })
    if ($keep -ge 0) { $ChapterList.SelectedIndex = $keep }
}

# ---------------------------------------------------------------- reader
function Show-Chapter([int]$i) {
    $R = $script:R
    if ($i -lt 0 -or $i -ge $R.Chs.Count) { return }
    $R.Index = $i
    $ch = $R.Chs[$i]
    $files = @(Get-ChildItem -LiteralPath $ch.FullName -File |
               Where-Object { $ImgExt -contains $_.Extension.ToLower() } | NatSort |
               ForEach-Object { [pscustomobject]@{ File = $_.FullName } })
    $R.Pages.ItemsSource = $files
    if ($files.Count) { $R.Pages.ScrollIntoView($files[0]) }

    $grpFile = Join-Path $ch.FullName '.group'
    $by = if ([IO.File]::Exists($grpFile)) { '  - translated by ' + [IO.File]::ReadAllText($grpFile) } else { '' }
    $R.Title.Text = "$($R.Series.Name)  |  $($ch.Name)  ($($i + 1)/$($R.Chs.Count), $($files.Count) pages)$by"
    $R.Win.Title = "$($R.Series.Name) - $($ch.Name)"
    $R.Prev.IsEnabled = $i -gt 0
    $hasNext = $i -lt ($R.Chs.Count - 1)
    $R.Next.IsEnabled = $hasNext
    $R.Next2.IsEnabled = $hasNext

    $script:Read["$($R.Series.Name)|$($ch.Name)"] = $true
    Save-Read
}

function Open-Reader([int]$index) {
    $series = $SeriesList.SelectedItem
    if (-not $series) { return }
    $chs = Get-ChapterDirs $series.Dir
    if ($chs.Count -eq 0) { Show-Msg 'No chapters downloaded yet.'; return }
    if ($index -lt 0) { $index = 0 }

    $rw = Load-Xaml $ReaderXaml
    $rw.Owner = $win
    $rw.Height = [System.Windows.SystemParameters]::WorkArea.Height * 0.95
    $script:R = @{
        Win = $rw; Series = $series; Chs = $chs; Index = $index
        Pages = $rw.FindName('Pages'); Title = $rw.FindName('ChTitle')
        Prev = $rw.FindName('PrevBtn'); Next = $rw.FindName('NextBtn'); Next2 = $rw.FindName('NextBtn2')
    }
    $script:R.Prev.Add_Click({ Show-Chapter ($script:R.Index - 1) })
    $script:R.Next.Add_Click({ Show-Chapter ($script:R.Index + 1) })
    $script:R.Next2.Add_Click({ Show-Chapter ($script:R.Index + 1) })
    $rw.Add_PreviewKeyDown({
        param($s, $e)
        switch ($e.Key) {
            'Right'  { Show-Chapter ($script:R.Index + 1); $e.Handled = $true }
            'Left'   { Show-Chapter ($script:R.Index - 1); $e.Handled = $true }
            'Escape' { $script:R.Win.Close() }
        }
    })
    Show-Chapter $index
    [void]$rw.ShowDialog()
    Refresh-Library
}

# ---------------------------------------------------------------- search
function Search-Manga {
    $q = $SearchBox.Text.Trim()
    if (-not $q) { return }
    $lang = $LangBox.SelectedItem.Content
    $Status.Text = "Searching for '$q'..."
    $win.Cursor = [System.Windows.Input.Cursors]::Wait
    try {
        $url = "$Api/manga?title=$([uri]::EscapeDataString($q))&limit=40&includes[]=cover_art" +
               "&availableTranslatedLanguage[]=$lang&contentRating[]=safe&contentRating[]=suggestive&order[relevance]=desc"
        $r = Invoke-MD $url
        $items = @(foreach ($m in $r.data) {
            $a = $m.attributes
            $art = $m.relationships | Where-Object { $_.type -eq 'cover_art' } | Select-Object -First 1
            $file = if ($art -and $art.attributes) { $art.attributes.fileName } else { $null }
            $desc = "$($a.description.en)" -replace '\s+', ' '
            if ($desc.Length -gt 350) { $desc = $desc.Substring(0, 350) + '...' }
            $bits = @($a.status, $a.year, $(if ($a.lastChapter) { "last ch. $($a.lastChapter)" })) | Where-Object { $_ }
            [pscustomobject]@{
                Id       = $m.id
                Title    = Get-MangaTitle $a
                Cover    = $(if ($file) { "https://uploads.mangadex.org/covers/$($m.id)/$file.256.jpg" } else { $null })
                CoverBig = $(if ($file) { "https://uploads.mangadex.org/covers/$($m.id)/$file.512.jpg" } else { $null })
                Info     = ($bits -join '  |  ')
                Desc     = $desc
                Lang     = $lang
            }
        })
        $Results.ItemsSource = $items
        $Status.Text = if ($items.Count) { "$($r.total) results. Select one and press 'Download to library'." } else { "Nothing found for '$q' in '$lang'." }
    } catch {
        $Status.Text = 'Search failed.'
        Show-Msg "Search failed: $($_.Exception.Message)`n`nCheck that https://mangadex.org opens in your web browser. If it does not, your network or antivirus may be blocking it."
    } finally {
        $win.Cursor = $null
    }
}

function Download-Selected {
    $m = $Results.SelectedItem
    if (-not $m) { Show-Msg 'Select a manga from the results first.'; return }
    Queue-Download $m.Id $m.Title $m.Lang $m.CoverBig
}

# ---------------------------------------------------------------- wire up events
$SearchBtn.Add_Click({ Search-Manga })
$SearchBox.Add_KeyDown({ param($s, $e) if ($e.Key -eq 'Return') { Search-Manga } })
$DownloadBtn.Add_Click({ Download-Selected })
$Results.Add_MouseDoubleClick({ Download-Selected })

$RefreshBtn.Add_Click({ Refresh-Library })
$FolderBtn.Add_Click({ Start-Process explorer.exe -ArgumentList "`"$Library`"" })
$SeriesList.Add_SelectionChanged({ Refresh-Chapters })
$ChapterList.Add_MouseDoubleClick({ if ($ChapterList.SelectedIndex -ge 0) { Open-Reader $ChapterList.SelectedIndex } })
$ReadBtn.Add_Click({ Open-Reader $ChapterList.SelectedIndex })
$ContinueBtn.Add_Click({
    $s = $SeriesList.SelectedItem
    if (-not $s) { return }
    $chs = Get-ChapterDirs $s.Dir
    $idx = 0
    for ($i = 0; $i -lt $chs.Count; $i++) { if (-not $script:Read.ContainsKey("$($s.Name)|$($chs[$i].Name)")) { $idx = $i; break }; $idx = $i }
    Open-Reader $idx
})
$UpdateBtn.Add_Click({
    $s = $SeriesList.SelectedItem
    if (-not $s) { return }
    $infoFile = Join-Path $s.Dir 'info.json'
    if (-not [IO.File]::Exists($infoFile)) { Show-Msg 'This folder was not downloaded by MangaShelf, so it cannot be updated.'; return }
    $info = [IO.File]::ReadAllText($infoFile) | ConvertFrom-Json
    Queue-Download $info.id $info.title $info.lang $null
})
$CancelBtn.Add_Click({
    $sync.Gen++
    $tmp = $null
    while ($queue.TryDequeue([ref]$tmp)) { }
    $Status.Text = 'Cancelling...'
})

# Poll the background downloader twice a second
$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(500)
$timer.Add_Tick({
    if ($sync.CurrentId -or $sync.LibraryChanged -or $queue.Count) {
        $Status.Text = $sync.Status
        $Progress.Value = $sync.Progress
    }
    if ($sync.LibraryChanged) {
        $sync.LibraryChanged = $false
        Refresh-Library
    }
})

$win.Add_Closed({
    $timer.Stop()
    $sync.Quit = $true
    $sync.Gen++
})

Load-Read
Refresh-Library
if ($script:SeriesItems.Count -eq 0) { $Tabs.SelectedIndex = 1 }
$timer.Start()
[void]$win.ShowDialog()

# Window closed: stop the downloader (partially downloaded chapters resume next time)
try { [void]$ps.BeginStop($null, $null) } catch { }
