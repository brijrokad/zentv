package io.github.brijrokad.zentv

/** What the weather pill shows. Filled only by the weather build's WeatherProvider. */
data class WeatherNow(val temperature: String, val description: String, val icon: Int)

/** WMO weather codes (as used by Open-Meteo) to a short description and a zentv glyph. Pure, unit-tested. */
object WeatherCodes {
    fun describe(code: Int): Pair<String, Int> = when (code) {
        0 -> "Clear" to R.drawable.wx_clear
        1, 2 -> "Partly cloudy" to R.drawable.wx_partly
        3 -> "Cloudy" to R.drawable.wx_cloud
        45, 48 -> "Fog" to R.drawable.wx_fog
        in 51..57 -> "Drizzle" to R.drawable.wx_rain
        in 61..67, in 80..82 -> "Rain" to R.drawable.wx_rain
        in 71..77, 85, 86 -> "Snow" to R.drawable.wx_snow
        in 95..99 -> "Thunderstorm" to R.drawable.wx_storm
        else -> "Cloudy" to R.drawable.wx_cloud
    }
}
