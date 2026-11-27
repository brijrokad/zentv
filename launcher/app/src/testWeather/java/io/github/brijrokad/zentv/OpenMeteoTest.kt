package io.github.brijrokad.zentv

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class OpenMeteoTest {
    @Test fun builtUrlsAreOpenMeteoOverHttps() {
        val f = OpenMeteo.forecast(40.7128, -74.006, fahrenheit = true)
        assertEquals("https", f.protocol)
        assertEquals("api.open-meteo.com", f.host)
        assertEquals(true, f.query.contains("temperature_unit=fahrenheit"))
        val s = OpenMeteo.search("New York & co", "en")
        assertEquals("geocoding-api.open-meteo.com", s.host)
        assertEquals(true, s.query.contains("name=New+York+%26+co"))
    }

    @Test fun anythingElseIsRefused() {
        assertThrows(IllegalArgumentException::class.java) { OpenMeteo.checked("http://api.open-meteo.com/v1/forecast") }
        assertThrows(IllegalArgumentException::class.java) { OpenMeteo.checked("https://example.com/") }
        assertThrows(IllegalArgumentException::class.java) { OpenMeteo.checked("https://api.open-meteo.com.evil.example/") }
        assertThrows(IllegalArgumentException::class.java) { OpenMeteo.checked("https://api.open-meteo.com:8443/") }
        assertThrows(IllegalArgumentException::class.java) { OpenMeteo.checked("https://user:pw@api.open-meteo.com/") }
    }
}
