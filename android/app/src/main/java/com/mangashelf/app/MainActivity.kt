package com.mangashelf.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

private val Accent = Color(0xFFE94560)
private val Green = Color(0xFF66DD66)
private val Red = Color(0xFFFF7777)
private val Dim = Color(0xFF9E9E9E)
private val CardBg = Color(0xFF333333)

private val Languages = listOf("en", "es-la", "es", "pt-br", "fr", "de", "it", "ru", "id", "vi", "tr", "pl")

sealed class Screen {
    data object Home : Screen()
    data class Series(val dir: File) : Screen()
    data class Reader(val series: File, val index: Int) : Screen()
}

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = Accent, secondary = Accent)) {
                Surface(Modifier.fillMaxSize(), color = Color(0xFF121212)) { AppRoot() }
            }
        }
    }
}

private fun toast(ctx: Context, msg: String) = Toast.makeText(ctx, msg, Toast.LENGTH_SHORT).show()

private fun openUrl(ctx: Context, url: String) {
    try {
        ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (e: Exception) {
        toast(ctx, "No browser found")
    }
}

@Composable
fun AppRoot() {
    var screen by remember { mutableStateOf<Screen>(Screen.Home) }
    var tab by rememberSaveable { mutableIntStateOf(0) }

    when (val s = screen) {
        is Screen.Home -> HomeScreen(tab, { tab = it }, onOpenSeries = { screen = Screen.Series(it) })
        is Screen.Series -> {
            BackHandler { screen = Screen.Home }
            SeriesScreen(s.dir, onBack = { screen = Screen.Home }, onRead = { screen = Screen.Reader(s.dir, it) })
        }
        is Screen.Reader -> {
            BackHandler { screen = Screen.Series(s.series) }
            ReaderScreen(
                s.series, s.index,
                onBack = { screen = Screen.Series(s.series) },
                onIndex = { screen = Screen.Reader(s.series, it) },
            )
        }
    }
}

// ------------------------------------------------------------------ home (tabs)
@Composable
fun HomeScreen(tab: Int, onTab: (Int) -> Unit, onOpenSeries: (File) -> Unit) {
    Scaffold(
        bottomBar = {
            Column {
                DownloadStatusBar()
                NavigationBar {
                    NavigationBarItem(
                        selected = tab == 0, onClick = { onTab(0) },
                        icon = { Icon(Icons.Filled.Home, contentDescription = null) }, label = { Text("Library") },
                    )
                    NavigationBarItem(
                        selected = tab == 1, onClick = { onTab(1) },
                        icon = { Icon(Icons.Filled.Search, contentDescription = null) }, label = { Text("Search") },
                    )
                }
            }
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            if (tab == 0) LibraryTab(onOpenSeries, onGoSearch = { onTab(1) }) else SearchTab()
        }
    }
}

@Composable
fun DownloadStatusBar() {
    val status by Downloader.status.collectAsState()
    val busy by Downloader.busy.collectAsState()
    val prog by Downloader.progress.collectAsState()
    Surface(color = Color(0xFF0A0A0A)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
            if (busy) LinearProgressIndicator(progress = { prog }, modifier = Modifier.fillMaxWidth())
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(status, Modifier.weight(1f).padding(vertical = 6.dp), fontSize = 12.sp, color = Color(0xFFCCCCCC), maxLines = 2)
                if (busy) TextButton(onClick = { Downloader.cancel() }) { Text("Cancel") }
            }
        }
    }
}

// ------------------------------------------------------------------ library
@Composable
fun LibraryTab(onOpen: (File) -> Unit, onGoSearch: () -> Unit) {
    val changes by Downloader.changes.collectAsState()
    val series = remember(changes) { Library.series() }

    if (series.isEmpty()) {
        Column(
            Modifier.fillMaxSize().padding(32.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Your library is empty", fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text("Search for a manga and download it to read here, even offline.", textAlign = TextAlign.Center, color = Dim)
            Spacer(Modifier.height(16.dp))
            Button(onClick = onGoSearch) { Text("Search manga") }
        }
        return
    }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(8.dp)) {
        item {
            Text("My manga", fontSize = 22.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(8.dp))
        }
        items(series, key = { it.name }) { s ->
            val chs = remember(changes, s) { Library.chapters(s) }
            val read = chs.count { ReadState.isRead(s.name, it.name) }
            Row(
                Modifier.fillMaxWidth().clickable { onOpen(s) }.padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                AsyncImage(
                    model = Library.cover(s), contentDescription = null, contentScale = ContentScale.Crop,
                    modifier = Modifier.size(60.dp, 86.dp).background(CardBg),
                )
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(s.name, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                    Text("${chs.size} chapters, $read read", color = Dim, fontSize = 13.sp)
                }
            }
        }
    }
}

// ------------------------------------------------------------------ search
@Composable
fun SearchTab() {
    val ctx = LocalContext.current
    val focus = LocalFocusManager.current
    val scope = rememberCoroutineScope()
    var query by rememberSaveable { mutableStateOf("") }
    var lang by rememberSaveable { mutableStateOf("en") }
    var searchedLang by remember { mutableStateOf("en") }
    var results by remember { mutableStateOf<List<Manga>>(emptyList()) }
    val counts = remember { mutableStateMapOf<String, Int>() }
    var loading by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>("Search MangaDex for a manga to download.") }
    var langMenu by remember { mutableStateOf(false) }

    fun doSearch() {
        val q = query.trim()
        if (q.isEmpty() || loading) return
        focus.clearFocus()
        loading = true
        message = null
        val l = lang
        scope.launch {
            try {
                val r = withContext(Dispatchers.IO) { MangaDex.search(q, l) }
                results = r
                searchedLang = l
                counts.clear()
                if (r.isEmpty()) message = "Nothing found for \"$q\" in '$l'."
                loading = false
                // Check which results really have downloadable chapters
                for (m in r) {
                    if (searchedLang != l || results !== r) break
                    val n = withContext(Dispatchers.IO) { runCatching { MangaDex.chapterCount(m.id, l) }.getOrDefault(-2) }
                    counts[m.id] = n
                    delay(250)
                }
            } catch (e: Exception) {
                message = "Search failed: ${e.message}\nCheck your internet connection."
            } finally {
                loading = false
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                value = query, onValueChange = { query = it },
                modifier = Modifier.weight(1f), singleLine = true,
                placeholder = { Text("Manga name") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { doSearch() }),
            )
            Box {
                TextButton(onClick = { langMenu = true }) { Text(lang) }
                DropdownMenu(expanded = langMenu, onDismissRequest = { langMenu = false }) {
                    Languages.forEach { l ->
                        DropdownMenuItem(text = { Text(l) }, onClick = { lang = l; langMenu = false })
                    }
                }
            }
            IconButton(onClick = { doSearch() }) { Icon(Icons.Filled.Search, contentDescription = "Search") }
        }
        if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        message?.let { Text(it, color = Dim, modifier = Modifier.padding(16.dp)) }

        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 16.dp)) {
            items(results, key = { it.id }) { m ->
                ResultRow(m, counts[m.id], searchedLang, ctx)
                HorizontalDivider(color = Color(0xFF2A2A2A))
            }
            if (results.isNotEmpty()) {
                item {
                    Text(
                        "Search and chapters by MangaDex and its scanlation groups. Please support official releases.",
                        color = Color(0xFF777777), fontSize = 11.sp, modifier = Modifier.padding(16.dp),
                    )
                }
            }
        }
    }
}

@Composable
fun ResultRow(m: Manga, count: Int?, lang: String, ctx: Context) {
    Row(Modifier.fillMaxWidth().padding(10.dp)) {
        AsyncImage(
            model = m.coverUrl, contentDescription = null, contentScale = ContentScale.Crop,
            modifier = Modifier.size(84.dp, 120.dp).background(CardBg),
        )
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(m.title, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            if (m.info.isNotBlank()) Text(m.info, color = Color(0xFF88CCFF), fontSize = 12.sp)
            val (label, color) = when {
                count == null -> "Checking chapters..." to Dim
                count > 0 -> "Downloadable" to Green
                count == 0 -> "Licensed - not downloadable here" to Red
                else -> "Couldn't check chapters" to Dim
            }
            Text(label, color = color, fontWeight = FontWeight.Bold, fontSize = 13.sp)
            if (m.description.isNotBlank()) {
                Text(m.description, color = Color(0xFFBBBBBB), fontSize = 12.sp, maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (count != 0) {
                    Button(onClick = {
                        val ok = Downloader.enqueue(DownloadJob(m.id, m.title, lang, m.coverBig))
                        toast(ctx, if (ok) "Downloading ${m.title}" else "Already downloading")
                    }) { Text("Download") }
                }
                OutlinedButton(onClick = {
                    openUrl(ctx, m.officialUrl ?: "https://mangadex.org/title/${m.id}")
                }) { Text("Official site") }
            }
        }
    }
}

// ------------------------------------------------------------------ one series
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SeriesScreen(dir: File, onBack: () -> Unit, onRead: (Int) -> Unit) {
    val ctx = LocalContext.current
    val changes by Downloader.changes.collectAsState()
    val chs = remember(changes) { Library.chapters(dir) }
    var confirmDelete by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(dir.name, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") }
                },
            )
        },
        bottomBar = { DownloadStatusBar() },
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    if (chs.isEmpty()) {
                        toast(ctx, "No chapters yet")
                    } else {
                        val i = chs.indexOfFirst { !ReadState.isRead(dir.name, it.name) }
                        onRead(if (i < 0) chs.lastIndex else i)
                    }
                }) { Text("Continue") }
                OutlinedButton(onClick = {
                    val info = Library.info(dir)
                    if (info == null) {
                        toast(ctx, "Can't update this one")
                    } else {
                        val ok = Downloader.enqueue(
                            DownloadJob(info.getString("id"), info.optString("title", dir.name), info.optString("lang", "en"), null)
                        )
                        toast(ctx, if (ok) "Checking for new chapters..." else "Already downloading")
                    }
                }) { Text("Check new") }
                OutlinedButton(onClick = { confirmDelete = true }) { Text("Delete") }
            }
            LazyColumn(Modifier.fillMaxSize()) {
                itemsIndexed(chs, key = { _, c -> c.name }) { i, c ->
                    val read = ReadState.isRead(dir.name, c.name)
                    Row(
                        Modifier.fillMaxWidth().clickable { onRead(i) }.padding(horizontal = 16.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(c.name, Modifier.weight(1f), color = if (read) Dim else Color.White)
                        when {
                            !Library.isDone(c) -> Text("downloading...", color = Color(0xFFFFAA44), fontSize = 12.sp)
                            read -> Text("read", color = Dim, fontSize = 12.sp)
                        }
                    }
                    HorizontalDivider(color = Color(0xFF2A2A2A))
                }
            }
        }
    }

    if (confirmDelete) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete ${dir.name}?") },
            text = { Text("All downloaded chapters of this manga will be removed from your phone.") },
            confirmButton = {
                TextButton(onClick = {
                    dir.deleteRecursively()
                    confirmDelete = false
                    Downloader.bump()
                    onBack()
                }) { Text("Delete") }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }
}

// ------------------------------------------------------------------ reader
@Composable
fun ReaderScreen(series: File, index: Int, onBack: () -> Unit, onIndex: (Int) -> Unit) {
    val chs = remember(series) { Library.chapters(series) }
    if (index !in chs.indices) {
        LaunchedEffect(Unit) { onBack() }
        return
    }
    val ch = chs[index]
    key(ch.path) {
        val pages = remember { Library.pages(ch) }
        val group = remember { File(ch, ".group").takeIf { it.exists() }?.readText() }
        val listState = rememberLazyListState()
        var showBar by remember { mutableStateOf(true) }
        LaunchedEffect(Unit) { ReadState.markRead(series.name, ch.name) }

        Box(Modifier.fillMaxSize().background(Color.Black)) {
            LazyColumn(
                state = listState,
                modifier = Modifier.fillMaxSize().pointerInput(Unit) { detectTapGestures { showBar = !showBar } },
            ) {
                item { Spacer(Modifier.height(if (showBar) 64.dp else 0.dp)) }
                items(pages, key = { it.path }) { p -> PageImage(p) }
                item {
                    Column(
                        Modifier.fillMaxWidth().padding(vertical = 32.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        if (pages.isEmpty()) Text("This chapter has no pages yet.", color = Dim)
                        if (index < chs.lastIndex) {
                            Button(onClick = { onIndex(index + 1) }) { Text("Next chapter") }
                        } else {
                            Text("You're all caught up!", color = Dim)
                        }
                    }
                }
            }

            if (showBar) {
                Surface(color = Color(0xE6000000), modifier = Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                        }
                        Column(Modifier.weight(1f)) {
                            Text(ch.name, color = Color.White, fontWeight = FontWeight.Bold, maxLines = 1)
                            val sub = "${index + 1}/${chs.size}  |  ${pages.size} pages" + (group?.let { "  |  $it" } ?: "")
                            Text(sub, color = Dim, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        TextButton(onClick = { onIndex(index - 1) }, enabled = index > 0) { Text("Prev") }
                        TextButton(onClick = { onIndex(index + 1) }, enabled = index < chs.lastIndex) { Text("Next") }
                    }
                }
            }
        }
    }
}

@Composable
fun PageImage(file: File) {
    val ctx = LocalContext.current
    var loaded by remember { mutableStateOf(false) }
    val request = remember(file) {
        ImageRequest.Builder(ctx)
            .data(file)
            .size(1440, 12000)          // keeps very tall webtoon strips within memory limits
            .allowHardware(false)
            .build()
    }
    AsyncImage(
        model = request,
        contentDescription = null,
        contentScale = ContentScale.FillWidth,
        onSuccess = { loaded = true },
        modifier = Modifier.fillMaxWidth().heightIn(min = if (loaded) 0.dp else 400.dp),
    )
}
