package io.github.brijrokad.zentv

import org.junit.Assert.assertEquals
import org.junit.Test

class WeatherCodesTest {
    @Test fun wmoCodes() {
        assertEquals("Clear", WeatherCodes.describe(0).first)
        assertEquals("Partly cloudy", WeatherCodes.describe(2).first)
        assertEquals("Fog", WeatherCodes.describe(45).first)
        assertEquals("Rain", WeatherCodes.describe(63).first)
        assertEquals("Snow", WeatherCodes.describe(75).first)
        assertEquals("Thunderstorm", WeatherCodes.describe(95).first)
        assertEquals("Cloudy", WeatherCodes.describe(1234).first)
    }
}
