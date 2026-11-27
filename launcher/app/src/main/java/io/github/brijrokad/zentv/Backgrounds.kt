package io.github.brijrokad.zentv

/**
 * What the home screen is drawn on: one of the five built-in scenes, or one of the owner's wallpapers
 * from `launcher/wallpapers/` (copied into the APK's assets/wallpapers/ at build time).
 *
 * A wallpaper may come with an optional cut-out (`<name>-fg.png|webp`, drawn over the clock) and an
 * optional pre-blurred layer (`<name>-glass.jpg|webp|png`); without one, zentv blurs the wallpaper
 * itself when it loads (see Wallpapers.blur).
 */
data class Background(
    val id: String, // "scene:<id>" or "wall:<file name>"
    val label: String,
    val image: String,
    val cutout: String?,
    val glass: String?,
    val clockTop: Float = 150f,
    val clockSize: Float = 400f,
    val clockLeft: Float? = null,
    val fill: GlassFill = GlassFill(),
) {
    companion object {
        fun of(s: Scene) = Background(
            "scene:${s.id}", s.label, s.background, s.cutout, s.glass, s.clockTop, s.clockSize, s.clockLeft, s.fill,
        )
    }
}

/** Where the clock sits on a wallpaper, in design pixels on the 1920x1080 canvas. */
data class ClockPlace(val top: Float = 150f, val size: Float = 400f, val left: Float? = null)

/**
 * The time-of-day schedule, `launcher/wallpapers/schedule.txt`. One line per slot: a start time and
 * what to show until the next slot starts; the last slot runs past midnight to the first one.
 * Several entries separated by commas take turns, one per day. Lines starting with `clock` place the
 * clock on a wallpaper. `#` starts a comment.
 *
 *     05:00  scene:dawn
 *     08:00  scene:fog, wall:lake.jpg
 *     16:00  scene:golden
 *     19:00  wall:city-night.jpg
 *     clock  city-night.jpg  top=180 size=380 left=96
 *
 * Pure Kotlin (no Android), unit-tested.
 */
class Schedule(val slots: List<Slot>, val clocks: Map<String, ClockPlace>, val problems: List<String>) {
    data class Slot(val startMinute: Int, val ids: List<String>)

    /** The entry for this minute of the day; [day] (days since the epoch) picks among several. */
    fun idFor(minuteOfDay: Int, day: Long): String? {
        if (slots.isEmpty()) return null
        val slot = slots.lastOrNull { it.startMinute <= minuteOfDay } ?: slots.last()
        // Before the first slot of the day we are still in yesterday's last slot.
        val d = if (slot === slots.last() && minuteOfDay < slots.first().startMinute) day - 1 else day
        return slot.ids[Math.floorMod(d, slot.ids.size.toLong()).toInt()]
    }

    companion object {
        private val TIME = Regex("""^([01]?\d|2[0-3]):([0-5]\d)$""")
        private val ID = Regex("""^(scene:[a-z]+|wall:[A-Za-z0-9][A-Za-z0-9._-]{0,80})$""")

        /** The built-in schedule (owner's choice 2026-11-27): dawn, fog by day, golden hour, night. */
        const val DEFAULT_TEXT = "05:00 scene:dawn\n08:00 scene:fog\n16:00 scene:golden\n19:00 scene:night\n"
        val DEFAULT: Schedule = parse(DEFAULT_TEXT)

        fun parse(text: String): Schedule {
            val slots = mutableListOf<Slot>()
            val clocks = HashMap<String, ClockPlace>()
            val problems = mutableListOf<String>()
            text.lineSequence().forEachIndexed { i, raw ->
                val line = raw.substringBefore('#').trim()
                if (line.isEmpty()) return@forEachIndexed
                val parts = line.split(Regex("\\s+"), limit = 2)
                if (parts[0] == "clock") {
                    val bits = parts.getOrNull(1)?.split(Regex("\\s+")).orEmpty()
                    val file = bits.firstOrNull()
                    if (file == null) { problems += "line ${i + 1}: clock needs a file name"; return@forEachIndexed }
                    var place = ClockPlace()
                    for (kv in bits.drop(1)) {
                        val (k, v) = kv.split('=', limit = 2).let { it[0] to it.getOrNull(1)?.toFloatOrNull() }
                        when {
                            v == null -> problems += "line ${i + 1}: bad value in '$kv'"
                            k == "top" -> place = place.copy(top = v)
                            k == "size" -> place = place.copy(size = v)
                            k == "left" -> place = place.copy(left = v)
                            else -> problems += "line ${i + 1}: unknown '$k'"
                        }
                    }
                    clocks[file] = place
                    return@forEachIndexed
                }
                val m = TIME.find(parts[0])
                if (m == null) { problems += "line ${i + 1}: '${parts[0]}' is not a time like 08:00"; return@forEachIndexed }
                val ids = parts.getOrNull(1)?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }.orEmpty()
                val good = ids.filter { ID.matches(it) }
                (ids - good.toSet()).forEach { problems += "line ${i + 1}: '$it' should be scene:<name> or wall:<file>" }
                if (good.isEmpty()) { problems += "line ${i + 1}: nothing to show"; return@forEachIndexed }
                slots += Slot(m.groupValues[1].toInt() * 60 + m.groupValues[2].toInt(), good)
            }
            return Schedule(slots.sortedBy { it.startMinute }.distinctBy { it.startMinute }, clocks, problems)
        }
    }
}
