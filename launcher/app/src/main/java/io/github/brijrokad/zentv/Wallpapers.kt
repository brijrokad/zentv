package io.github.brijrokad.zentv

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.util.Calendar
import java.util.TimeZone
import java.util.concurrent.TimeUnit

/**
 * The owner's wallpapers (assets/wallpapers/, from launcher/wallpapers/ in the repo) and the
 * schedule that mixes them with the built-in scenes. Read once per process; the files only change
 * with a new APK.
 */
object Wallpapers {
    private const val DIR = "wallpapers"
    private val IMAGE = Regex("""\.(jpe?g|png|webp)$""", RegexOption.IGNORE_CASE)

    @Volatile private var cache: Pair<Schedule, Map<String, Background>>? = null

    fun load(context: Context): Pair<Schedule, Map<String, Background>> = cache ?: synchronized(this) {
        cache ?: read(context).also { cache = it }
    }

    private fun read(context: Context): Pair<Schedule, Map<String, Background>> {
        val names = runCatching { context.assets.list(DIR)?.toList() }.getOrNull().orEmpty()
        val text = runCatching { context.assets.open("$DIR/schedule.txt").bufferedReader().use { it.readText() } }.getOrNull()
        val schedule = text?.let { Schedule.parse(it) }?.takeIf { it.slots.isNotEmpty() } ?: Schedule.DEFAULT
        val images = names.filter { IMAGE.containsMatchIn(it) }
        fun companion(stem: String, suffix: String) = images.firstOrNull { it.substringBeforeLast('.') == "$stem-$suffix" }
        val walls = images
            .filterNot { val s = it.substringBeforeLast('.'); s.endsWith("-fg") || s.endsWith("-glass") }
            .associate { file ->
                val stem = file.substringBeforeLast('.')
                val clock = schedule.clocks[file] ?: ClockPlace()
                "wall:$file" to Background(
                    id = "wall:$file",
                    label = stem.replace('-', ' ').replace('_', ' ').replaceFirstChar { it.uppercase() },
                    image = "$DIR/$file",
                    cutout = companion(stem, "fg")?.let { "$DIR/$it" },
                    glass = companion(stem, "glass")?.let { "$DIR/$it" },
                    clockTop = clock.top,
                    clockSize = clock.size,
                    clockLeft = clock.left,
                )
            }
        return schedule to walls
    }

    /** Every background the owner can pick as a fixed one: the five scenes, then the wallpapers. */
    fun all(context: Context): List<Background> = Scene.entries.map { Background.of(it) } + load(context).second.values.sortedBy { it.label }

    /** "scene:fog", a bare scene id (older settings), or "wall:<file>". */
    fun byId(context: Context, id: String): Background? = when {
        id.startsWith("wall:") -> load(context).second[id]
        else -> Scene.byId(id.removePrefix("scene:"))?.let { Background.of(it) }
    }

    /** What to show now: the owner's fixed choice, or the schedule ("auto"). */
    fun now(context: Context, prefs: Prefs, cal: Calendar = Calendar.getInstance()): Background {
        if (prefs.scene != "auto") byId(context, prefs.scene)?.let { return it }
        val minute = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)
        val offset = TimeZone.getDefault().getOffset(cal.timeInMillis)
        val day = TimeUnit.MILLISECONDS.toDays(cal.timeInMillis + offset)
        val id = load(context).first.idFor(minute, day)
        return id?.let { byId(context, it) } ?: Background.of(Scene.forHour(cal.get(Calendar.HOUR_OF_DAY)))
    }

    /** Decodes an asset no larger than needed for a screen [screenWidth] pixels wide. */
    fun decode(context: Context, path: String, config: Bitmap.Config, screenWidth: Int): Bitmap? = runCatching {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.assets.open(path).use { BitmapFactory.decodeStream(it, null, bounds) }
        val sample = Scene.sampleSizeFor(screenWidth, maxOf(bounds.outWidth, bounds.outHeight))
        context.assets.open(path).use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply {
                inPreferredConfig = config
                inSampleSize = sample
            })
        }
    }.getOrNull()

    /**
     * A soft blur for wallpapers that have no -glass layer (Android 11 has no RenderEffect): shrink to
     * 1/24 in steps with bilinear filtering, then scale back up to 1920x1080. Cheap, and smooth enough
     * for the frosted clock and the All apps backdrop.
     */
    fun blur(src: Bitmap): Bitmap {
        var b = src
        var w = src.width
        var h = src.height
        val steps = mutableListOf<Bitmap>()
        while (w > 80) {
            w = maxOf(1, w / 2)
            h = maxOf(1, h / 2)
            b = Bitmap.createScaledBitmap(b, w, h, true)
            steps += b
        }
        var up = b
        var uw = w
        var uh = h
        while (uw < 1920) {
            uw = minOf(1920, uw * 2)
            uh = minOf(1080, uh * 2)
            up = Bitmap.createScaledBitmap(up, uw, uh, true)
            steps += up
        }
        steps.filter { it !== up }.forEach { it.recycle() }
        return up
    }
}
