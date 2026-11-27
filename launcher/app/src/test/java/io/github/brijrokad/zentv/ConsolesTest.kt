package io.github.brijrokad.zentv

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ConsolesTest {
    @Test fun playstationNames() {
        assertEquals(ConsoleMatch(ConsoleBrand.PLAYSTATION, "PS5"), Consoles.match("PlayStation 5"))
        assertEquals(ConsoleMatch(ConsoleBrand.PLAYSTATION, "PS5"), Consoles.match("PS5"))
        assertEquals(ConsoleMatch(ConsoleBrand.PLAYSTATION, "PS4"), Consoles.match("PlayStation4"))
        assertEquals(ConsoleMatch(ConsoleBrand.PLAYSTATION, "PS"), Consoles.match("PlayStation"))
    }

    @Test fun xboxAndNintendo() {
        assertEquals(ConsoleMatch(ConsoleBrand.XBOX, "XBOX"), Consoles.match("Xbox Series X"))
        assertEquals(ConsoleMatch(ConsoleBrand.NINTENDO, "SWITCH"), Consoles.match("Nintendo Switch"))
        assertEquals(ConsoleMatch(ConsoleBrand.NINTENDO, "SWITCH"), Consoles.match("Switch"))
    }

    @Test fun otherDevicesAreNotConsoles() {
        assertNull(Consoles.match("Soundbar"))
        assertNull(Consoles.match("Chromecast"))
        assertNull(Consoles.match("HDMI Switcher Box"))
        assertNull(Consoles.match(""))
        assertNull(Consoles.match(null))
    }

    @Test fun portNumbersAndLabelsArePortOnly() {
        assertEquals(1, Consoles.portNumber("HDMI 1"))
        assertEquals(2, Consoles.portNumber("HDMI2 (ARC)"))
        assertNull(Consoles.portNumber("PS5"))
        assertEquals("HDMI 3", Consoles.portLabel(3))
    }
}
