package io.github.brijrokad.zentv

import java.net.URL
import java.net.URLEncoder
import java.util.Locale

/**
 * The only network endpoints zentv knows: Open-Meteo's forecast and geocoding APIs (free, no key, no
 * account). Every request URL is built here and checked against [HOSTS]; anything else is refused before
 * a connection is opened. No location permission: the owner types a town name once.
 */
object OpenMeteo {
    val HOSTS = setOf("api.open-meteo.com", "geocoding-api.open-meteo.com")

    fun forecast(lat: Double, lon: Double, fahrenheit: Boolean): URL = checked(
        "https://api.open-meteo.com/v1/forecast?latitude=${fmt(lat)}&longitude=${fmt(lon)}" +
            "&current=temperature_2m,weather_code&timezone=auto" +
            if (fahrenheit) "&temperature_unit=fahrenheit" else "",
    )

    fun search(name: String, language: String): URL = checked(
        "https://geocoding-api.open-meteo.com/v1/search?name=${URLEncoder.encode(name.trim(), "UTF-8")}" +
            "&count=6&format=json&language=${URLEncoder.encode(language, "UTF-8")}",
    )

    /** Refuses anything but HTTPS to an Open-Meteo host on the default port. */
    fun checked(url: String): URL {
        val u = URL(url)
        require(u.protocol == "https") { "zentv weather: HTTPS only" }
        require(u.host in HOSTS) { "zentv weather: ${u.host} is not an Open-Meteo host" }
        require(u.port == -1 || u.port == 443) { "zentv weather: unexpected port" }
        require(u.userInfo == null) { "zentv weather: no credentials in URLs" }
        return u
    }

    private fun fmt(v: Double) = String.format(Locale.US, "%.4f", v)
}
