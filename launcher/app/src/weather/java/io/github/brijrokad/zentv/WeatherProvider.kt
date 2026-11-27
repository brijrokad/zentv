package io.github.brijrokad.zentv

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.text.InputType
import android.widget.EditText
import android.widget.Toast
import org.json.JSONObject
import java.net.URL
import java.util.Locale
import javax.net.ssl.HttpsURLConnection
import kotlin.math.roundToInt

/**
 * Weather build only. Fetches the current temperature and conditions for the owner's town from
 * Open-Meteo at most every 30 minutes while the home screen is shown. Sends only the town's
 * coordinates (or, once, the typed town name); no identifiers, no cookies, no analytics.
 */
object WeatherProvider {
    const val AVAILABLE = true
    private const val MAX_AGE_MS = 30 * 60_000L

    private fun prefs(c: Context) = c.getSharedPreferences("zentv_weather", Context.MODE_PRIVATE)

    private fun fahrenheit(c: Context) =
        prefs(c).getBoolean("fahrenheit", Locale.getDefault().country in setOf("US", "LR", "MM"))

    fun current(activity: Activity, onResult: (WeatherNow?) -> Unit) {
        val p = prefs(activity)
        if (!p.contains("lat")) return onResult(null)
        cached(activity)?.let(onResult)
        if (System.currentTimeMillis() - p.getLong("at", 0) < MAX_AGE_MS) return
        val lat = p.getFloat("lat", 0f).toDouble()
        val lon = p.getFloat("lon", 0f).toDouble()
        val f = fahrenheit(activity)
        (activity.application as ZentvApp).worker.execute {
            val now = runCatching {
                val cur = JSONObject(get(OpenMeteo.forecast(lat, lon, f))).getJSONObject("current")
                cur.getDouble("temperature_2m") to cur.getInt("weather_code")
            }.getOrNull()
            if (now != null) {
                p.edit().putFloat("temp", now.first.toFloat()).putInt("code", now.second)
                    .putLong("at", System.currentTimeMillis()).apply()
            }
            activity.runOnUiThread { if (!activity.isDestroyed) onResult(cached(activity)) }
        }
    }

    private fun cached(c: Context): WeatherNow? {
        val p = prefs(c)
        if (!p.contains("temp")) return null
        val (desc, icon) = WeatherCodes.describe(p.getInt("code", 3))
        return WeatherNow("${p.getFloat("temp", 0f).roundToInt()}°", desc, icon)
    }

    private fun get(url: URL): String {
        val conn = OpenMeteo.checked(url.toString()).openConnection() as HttpsURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 8000
        conn.useCaches = false
        conn.instanceFollowRedirects = false
        conn.setRequestProperty("User-Agent", "zentv")
        try {
            require(conn.responseCode == 200) { "HTTP ${conn.responseCode}" }
            return conn.inputStream.bufferedReader().use { it.readText().take(64_000) }
        } finally {
            conn.disconnect()
        }
    }

    fun settingsLabel(activity: Activity): String {
        val place = prefs(activity).getString("place", null)
        return if (place == null) "Weather: off (set your town)" else "Weather: $place"
    }

    /** Town search, °C/°F, or turn weather off. */
    fun openSettings(activity: Activity, done: () -> Unit) {
        val p = prefs(activity)
        val items = arrayOf(
            "Set town…",
            if (fahrenheit(activity)) "Units: °F (switch to °C)" else "Units: °C (switch to °F)",
            "Turn weather off",
        )
        AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle("Weather (Open-Meteo)")
            .setItems(items) { _, which ->
                when (which) {
                    0 -> askTown(activity, done)
                    1 -> { p.edit().putBoolean("fahrenheit", !fahrenheit(activity)).putLong("at", 0).apply(); done() }
                    else -> { p.edit().clear().apply(); done() }
                }
            }
            .setOnCancelListener { done() }.show()
    }

    private fun askTown(activity: Activity, done: () -> Unit) {
        val input = EditText(activity).apply { inputType = InputType.TYPE_CLASS_TEXT; hint = "Town or city" }
        AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle("Your town").setView(input)
            .setPositiveButton("Search") { _, _ -> search(activity, input.text.toString(), done) }
            .setNegativeButton("Cancel") { _, _ -> done() }.show()
    }

    private fun search(activity: Activity, name: String, done: () -> Unit) {
        if (name.isBlank()) return done()
        (activity.application as ZentvApp).worker.execute {
            val results = runCatching {
                val arr = JSONObject(get(OpenMeteo.search(name, Locale.getDefault().language))).optJSONArray("results")
                (0 until (arr?.length() ?: 0)).map { i ->
                    val o = arr!!.getJSONObject(i)
                    val label = listOf(o.optString("name"), o.optString("admin1"), o.optString("country"))
                        .filter { it.isNotBlank() }.joinToString(", ")
                    Triple(label, o.getDouble("latitude"), o.getDouble("longitude"))
                }
            }.getOrNull()
            activity.runOnUiThread {
                if (activity.isDestroyed) return@runOnUiThread
                if (results.isNullOrEmpty()) {
                    Toast.makeText(activity, "No town found (or no network)", Toast.LENGTH_LONG).show()
                    return@runOnUiThread done()
                }
                AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle("Choose your town")
                    .setItems(results.map { it.first }.toTypedArray()) { _, i ->
                        val r = results[i]
                        prefs(activity).edit().putString("place", r.first).putFloat("lat", r.second.toFloat())
                            .putFloat("lon", r.third.toFloat()).putLong("at", 0).remove("temp").apply()
                        done()
                    }
                    .setOnCancelListener { done() }.show()
            }
        }
    }
}
