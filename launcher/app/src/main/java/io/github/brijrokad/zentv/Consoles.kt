package io.github.brijrokad.zentv

/**
 * HDMI tiles (docs/ARCHITECTURE.md §6, InputTiles). The label is always the port ("HDMI 1"). The icon is
 * the owner's private logo when the HDMI-CEC device name says which console it is, or zentv's own
 * fallback (a controller glyph with the short name underneath). Pure Kotlin, unit-tested.
 */
enum class ConsoleBrand(val logoName: String) {
    PLAYSTATION("playstation"),
    XBOX("xbox"),
    NINTENDO("nintendo"),
}

data class ConsoleMatch(val brand: ConsoleBrand, val shortName: String)

object Consoles {
    private val PS_GEN = Regex("""(?:playstation|ps)\s*([2-9])""", RegexOption.IGNORE_CASE)

    /** What console a CEC device name describes, or null for anything else (a soundbar, a Chromecast). */
    fun match(cecName: String?): ConsoleMatch? {
        val n = cecName?.trim().orEmpty()
        if (n.isEmpty()) return null
        val lower = n.lowercase()
        if ("playstation" in lower || PS_GEN.containsMatchIn(n)) {
            val gen = PS_GEN.find(n)?.groupValues?.get(1)
            return ConsoleMatch(ConsoleBrand.PLAYSTATION, if (gen != null) "PS$gen" else "PS")
        }
        if ("xbox" in lower) return ConsoleMatch(ConsoleBrand.XBOX, "XBOX")
        if ("nintendo" in lower || Regex("""\bswitch\b""").containsMatchIn(lower)) {
            return ConsoleMatch(ConsoleBrand.NINTENDO, "SWITCH")
        }
        return null
    }

    private val PORT = Regex("""hdmi\s*(\d{1,2})""", RegexOption.IGNORE_CASE)

    /** The port number from a TV input's label ("HDMI 2", "HDMI2 (ARC)"), or null. */
    fun portNumber(label: String?): Int? = label?.let { PORT.find(it)?.groupValues?.get(1)?.toIntOrNull() }

    fun portLabel(port: Int) = "HDMI $port"
}
