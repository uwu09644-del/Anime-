package com.mangashelf.app

import android.app.Application
import android.content.Context
import android.content.SharedPreferences
import coil.ImageLoader
import coil.ImageLoaderFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.URLEncoder
import java.util.Collections
import java.util.Locale
import java.util.concurrent.TimeUnit

const val USER_AGENT = "MangaShelf-Android/1.0 (personal reader)"

class App : Application(), ImageLoaderFactory {
    override fun onCreate() {
        super.onCreate()
        Library.init(this)
        ReadState.init(this)
    }

    // Cover pictures go through the same client, so they carry our User-Agent
    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this).okHttpClient(Net.client).crossfade(true).build()
}

// ------------------------------------------------------------------ network
object Net {
    val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            chain.proceed(chain.request().newBuilder().header("User-Agent", USER_AGENT).build())
        }
        .build()

    fun getJson(url: String): JSONObject {
        var last: Exception? = null
        for (attempt in 1..4) {
            try {
                client.newCall(Request.Builder().url(url).build()).execute().use { r ->
                    if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
                    val body = r.body?.string() ?: throw IOException("empty response")
                    return JSONObject(body)
                }
            } catch (e: Exception) {
                last = e
                Thread.sleep(1500L * attempt)
            }
        }
        throw last ?: IOException("request failed")
    }

    fun download(url: String, out: File): Boolean {
        val part = File(out.path + ".part")
        for (attempt in 1..3) {
            try {
                client.newCall(Request.Builder().url(url).build()).execute().use { r ->
                    if (!r.isSuccessful) throw IOException("HTTP ${r.code}")
                    val body = r.body ?: throw IOException("empty response")
                    part.outputStream().use { o -> body.byteStream().copyTo(o) }
                }
                if (out.exists()) out.delete()
                if (part.renameTo(out)) return true
            } catch (e: Exception) {
                part.delete()
                Thread.sleep(2000L * attempt)
            }
        }
        return false
    }
}

// ------------------------------------------------------------------ MangaDex API
data class Manga(
    val id: String,
    val title: String,
    val coverUrl: String?,
    val coverBig: String?,
    val info: String,
    val description: String,
    val officialUrl: String?,
)

data class RemoteChapter(val id: String, val number: String?, val title: String?, val group: String?)

data class AtHome(val baseUrl: String, val hash: String, val files: List<String>)

object MangaDex {
    private const val API = "https://api.mangadex.org"
    private const val RATINGS = "contentRating[]=safe&contentRating[]=suggestive&contentRating[]=erotica"

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8")

    private fun str(o: JSONObject?, key: String): String? {
        if (o == null || !o.has(key) || o.isNull(key)) return null
        return o.optString(key).takeIf { it.isNotBlank() }
    }

    fun search(query: String, lang: String): List<Manga> {
        val url = "$API/manga?title=${enc(query)}&limit=30&includes[]=cover_art" +
            "&availableTranslatedLanguage[]=$lang&contentRating[]=safe&contentRating[]=suggestive&order[relevance]=desc"
        val data = Net.getJson(url).getJSONArray("data")
        return (0 until data.length()).map { parseManga(data.getJSONObject(it)) }
    }

    private fun pickTitle(a: JSONObject): String {
        val t = a.optJSONObject("title")
        str(t, "en")?.let { return it }
        val alts = a.optJSONArray("altTitles")
        if (alts != null) {
            for (i in 0 until alts.length()) str(alts.optJSONObject(i), "en")?.let { return it }
        }
        if (t != null) {
            val keys = t.keys()
            if (keys.hasNext()) str(t, keys.next())?.let { return it }
        }
        return "Untitled"
    }

    private fun parseManga(m: JSONObject): Manga {
        val id = m.getString("id")
        val a = m.getJSONObject("attributes")
        var coverFile: String? = null
        val rels = m.optJSONArray("relationships")
        if (rels != null) {
            for (i in 0 until rels.length()) {
                val r = rels.getJSONObject(i)
                if (r.optString("type") == "cover_art") coverFile = str(r.optJSONObject("attributes"), "fileName")
            }
        }
        val desc = (str(a.optJSONObject("description"), "en") ?: "").replace(Regex("\\s+"), " ").take(300)
        val info = listOfNotNull(
            str(a, "status"),
            str(a, "year"),
            str(a, "lastChapter")?.let { "last ch. $it" },
        ).joinToString("  |  ")
        val links = a.optJSONObject("links")
        val official = listOf("engtl", "amz", "raw", "cdj", "ebj")
            .mapNotNull { str(links, it) }
            .firstOrNull { it.startsWith("http") }
        val cf = coverFile
        return Manga(
            id = id,
            title = pickTitle(a),
            coverUrl = cf?.let { "https://uploads.mangadex.org/covers/$id/$it.256.jpg" },
            coverBig = cf?.let { "https://uploads.mangadex.org/covers/$id/$it.512.jpg" },
            info = info,
            description = desc,
            officialUrl = official,
        )
    }

    /** How many chapter uploads can actually be downloaded (0 = licensed / external only). */
    fun chapterCount(id: String, lang: String): Int =
        Net.getJson("$API/manga/$id/feed?translatedLanguage[]=$lang&includeExternalUrl=0&limit=1&$RATINGS")
            .optInt("total", 0)

    fun chapters(id: String, lang: String): List<RemoteChapter> {
        val out = mutableListOf<RemoteChapter>()
        val seen = HashSet<String>()
        var offset = 0
        while (true) {
            val j = Net.getJson(
                "$API/manga/$id/feed?translatedLanguage[]=$lang&order[volume]=asc&order[chapter]=asc" +
                    "&limit=500&offset=$offset&includes[]=scanlation_group&includeExternalUrl=0&$RATINGS"
            )
            val data = j.getJSONArray("data")
            for (i in 0 until data.length()) {
                val c = data.getJSONObject(i)
                val a = c.getJSONObject("attributes")
                if (a.optInt("pages", 0) < 1) continue
                val num = str(a, "chapter")
                val key = num ?: ("x" + c.getString("id"))
                if (!seen.add(key)) continue          // one upload per chapter number
                var group: String? = null
                val rels = c.optJSONArray("relationships")
                if (rels != null) {
                    for (k in 0 until rels.length()) {
                        val r = rels.getJSONObject(k)
                        if (r.optString("type") == "scanlation_group") group = str(r.optJSONObject("attributes"), "name")
                    }
                }
                out += RemoteChapter(c.getString("id"), num, str(a, "title"), group)
            }
            offset += 500
            if (offset >= j.optInt("total", 0)) break
            Thread.sleep(300)
        }
        return out
    }

    fun atHome(chapterId: String): AtHome {
        val j = Net.getJson("$API/at-home/server/$chapterId")
        val ch = j.getJSONObject("chapter")
        val d = ch.getJSONArray("data")
        return AtHome(j.getString("baseUrl"), ch.getString("hash"), (0 until d.length()).map { d.getString(it) })
    }
}

// ------------------------------------------------------------------ library on the phone
object Library {
    lateinit var root: File
        private set

    val imgExt = setOf("jpg", "jpeg", "png", "webp", "gif")
    private val numRe = Regex("\\d+")

    fun init(ctx: Context) {
        root = File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, "Manga").apply { mkdirs() }
    }

    fun natKey(s: String): String = numRe.replace(s) { it.value.padStart(10, '0') }.lowercase(Locale.ROOT)

    fun cleanName(s: String): String {
        var n = s.replace(Regex("[\\\\/:*?\"<>|\\x00-\\x1f]"), "_").trim().trimEnd('.')
        if (n.length > 120) n = n.take(120).trim()
        return n.ifBlank { "Untitled" }
    }

    fun chapterFolder(c: RemoteChapter): String {
        val n = c.number
        val m = n?.let { Regex("^(\\d+)(\\.\\d+)?$").find(it) }
        return when {
            m != null -> "Chapter " + m.groupValues[1].padStart(4, '0') + m.groupValues[2]
            n != null -> "Chapter " + cleanName(n)
            else -> "Extra - " + cleanName(c.title ?: c.id.take(8))
        }
    }

    fun series(): List<File> =
        (root.listFiles()?.filter { it.isDirectory } ?: emptyList()).sortedBy { natKey(it.name) }

    fun chapters(series: File): List<File> =
        (series.listFiles()?.filter { it.isDirectory } ?: emptyList()).sortedBy { natKey(it.name) }

    fun pages(ch: File): List<File> =
        (ch.listFiles()?.filter { it.isFile && it.extension.lowercase(Locale.ROOT) in imgExt } ?: emptyList())
            .sortedBy { natKey(it.name) }

    fun isDone(ch: File) = File(ch, ".done").exists()

    fun cover(series: File): File? = File(series, "cover.jpg").takeIf { it.exists() }

    fun info(series: File): JSONObject? =
        File(series, "info.json").takeIf { it.exists() }?.let { runCatching { JSONObject(it.readText()) }.getOrNull() }
}

object ReadState {
    private lateinit var prefs: SharedPreferences

    fun init(ctx: Context) {
        prefs = ctx.getSharedPreferences("read_chapters", Context.MODE_PRIVATE)
    }

    fun isRead(series: String, chapter: String) = prefs.getBoolean("$series|$chapter", false)

    fun markRead(series: String, chapter: String) {
        prefs.edit().putBoolean("$series|$chapter", true).apply()
    }
}

// ------------------------------------------------------------------ background downloader
data class DownloadJob(
    val mangaId: String,
    val title: String,
    val lang: String,
    val coverUrl: String?,
    val gen: Int = 0,
)

object Downloader {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val queue = Channel<DownloadJob>(Channel.UNLIMITED)
    private val queued: MutableSet<String> = Collections.synchronizedSet(mutableSetOf())

    @Volatile
    private var gen = 0

    val status = MutableStateFlow("Ready")
    val progress = MutableStateFlow(0f)
    val busy = MutableStateFlow(false)
    val changes = MutableStateFlow(0)      // bumps whenever the library on disk changes

    init {
        scope.launch { for (job in queue) run(job) }
    }

    fun bump() {
        changes.value = changes.value + 1
    }

    /** Returns false if this manga is already queued or downloading. */
    fun enqueue(job: DownloadJob): Boolean {
        if (!queued.add(job.mangaId)) return false
        queue.trySend(job.copy(gen = gen))
        status.value = "Queued: ${job.title}"
        return true
    }

    fun cancel() {
        gen++
        queued.clear()
        status.value = "Cancelling..."
    }

    private fun run(job: DownloadJob) {
        if (job.gen != gen) return
        busy.value = true
        progress.value = 0f
        try {
            status.value = "Getting chapters for ${job.title}..."
            val dir = File(Library.root, Library.cleanName(job.title)).apply { mkdirs() }
            File(dir, "info.json").writeText(
                JSONObject().put("id", job.mangaId).put("lang", job.lang).put("title", job.title).toString()
            )
            val cover = File(dir, "cover.jpg")
            if (job.coverUrl != null && !cover.exists()) Net.download(job.coverUrl, cover)
            bump()

            val list = MangaDex.chapters(job.mangaId, job.lang)
            if (list.isEmpty()) {
                status.value = "${job.title}: no downloadable chapters in '${job.lang}' (it is licensed)."
                return
            }
            var added = 0
            var failed = 0
            for ((i, c) in list.withIndex()) {
                if (job.gen != gen) {
                    status.value = "Downloads cancelled."
                    return
                }
                progress.value = i.toFloat() / list.size
                val cdir = File(dir, Library.chapterFolder(c))
                if (File(cdir, ".done").exists()) continue
                status.value = "${job.title}: chapter ${c.number ?: "extra"} (${i + 1}/${list.size})"

                val ah = MangaDex.atHome(c.id)
                cdir.mkdirs()
                c.group?.let { File(cdir, ".group").writeText(it) }
                var ok = true
                for ((p, f) in ah.files.withIndex()) {
                    if (job.gen != gen) { ok = false; break }
                    val ext = f.substringAfterLast('.', "jpg")
                    val out = File(cdir, String.format(Locale.US, "%03d.%s", p + 1, ext))
                    if (!out.exists() && !Net.download("${ah.baseUrl}/data/${ah.hash}/$f", out)) ok = false
                }
                if (ok) {
                    File(cdir, ".done").writeText("")
                    added++
                } else {
                    failed++
                }
                bump()
                Thread.sleep(1500)                 // MangaDex allows ~40 chapter lookups per minute
            }
            progress.value = 1f
            status.value = if (failed > 0) {
                "${job.title}: $added new, $failed failed. Tap 'Check new' to retry."
            } else {
                "${job.title}: done, $added new chapters."
            }
        } catch (e: Exception) {
            status.value = "Error downloading ${job.title}: ${e.message}"
        } finally {
            busy.value = false
            queued.remove(job.mangaId)
            bump()
        }
    }
}
