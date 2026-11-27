package io.github.brijrokad.zentv

import android.content.Context
import android.content.SharedPreferences
import android.text.format.DateFormat

/**
 * zentv's own settings and the owner's favourites/hidden lists, in app-private SharedPreferences
 * (UI process only). Keys of entries are stable strings: "app:<package>/<activity>" or "hdmi:<port>".
 */
class Prefs(context: Context) {
    private val sp: SharedPreferences = context.getSharedPreferences("zentv", Context.MODE_PRIVATE)
    private val is24System = DateFormat.is24HourFormat(context)

    /** "auto" (by time of day) or a scene id. */
    var scene: String
        get() = sp.getString("scene", "auto") ?: "auto"
        set(v) = sp.edit().putString("scene", v).apply()

    var clockFace: ClockFace
        get() = ClockFace.byId(sp.getString("clock_face", null))
        set(v) = sp.edit().putString("clock_face", v.id).apply()

    var clock24: Boolean
        get() = sp.getBoolean("clock_24", is24System)
        set(v) = sp.edit().putBoolean("clock_24", v).apply()

    /** All apps background tint, 20..80 (%). */
    var tint: Int
        get() = sp.getInt("tint", 45).coerceIn(20, 80)
        set(v) = sp.edit().putInt("tint", v.coerceIn(20, 80)).apply()

    var favourites: List<String>
        get() = sp.getString("favourites", null)?.split('\n')?.filter { it.isNotBlank() } ?: emptyList()
        set(v) = sp.edit().putString("favourites", v.distinct().joinToString("\n")).putBoolean("favourites_set", true).apply()

    val favouritesChosen get() = sp.getBoolean("favourites_set", false)

    var hidden: Set<String>
        get() = sp.getStringSet("hidden", emptySet())?.toSet() ?: emptySet()
        set(v) = sp.edit().putStringSet("hidden", v).apply()

    fun sceneNow(hour: Int): Scene = Scene.byId(scene) ?: Scene.forHour(hour)

    companion object {
        const val MAX_FAVOURITES = 8
    }
}

/** Favourite-list edits, kept pure for tests. */
object FavouriteOps {
    fun toggle(list: List<String>, key: String, max: Int = Prefs.MAX_FAVOURITES): List<String> =
        if (key in list) list - key else (list + key).take(max)

    fun move(list: List<String>, key: String, by: Int): List<String> {
        val i = list.indexOf(key)
        if (i < 0) return list
        val j = (i + by).coerceIn(0, list.lastIndex)
        if (i == j) return list
        val out = list.toMutableList()
        out.removeAt(i)
        out.add(j, key)
        return out
    }

    /** First run: well-known streaming apps that are installed, then Live TV, then consoles on HDMI. */
    fun defaults(available: List<Entry>, max: Int = 8): List<String> {
        val byPackage = available.filterIsInstance<Entry.App>().groupBy { it.packageName }
        val out = mutableListOf<String>()
        for (pkg in WELL_KNOWN) byPackage[pkg]?.firstOrNull()?.let { out += it.key }
        available.filterIsInstance<Entry.App>().firstOrNull { it.isLiveTv }?.let { out += it.key }
        available.filterIsInstance<Entry.Input>().filter { it.console != null }.forEach { out += it.key }
        return out.distinct().take(max)
    }

    val WELL_KNOWN = listOf(
        "com.google.android.youtube.tv",
        "com.netflix.ninja",
        "com.amazon.amazonvideo.livingroom",
        "com.hulu.livingroomplus",
        "com.disney.disneyplus",
        "com.wbd.stream",
        "com.hbo.hbonow",
    )
}
