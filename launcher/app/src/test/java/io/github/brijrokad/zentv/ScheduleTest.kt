package io.github.brijrokad.zentv

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ScheduleTest {
    private fun m(h: Int, min: Int = 0) = h * 60 + min

    @Test fun defaultMatchesTheBuiltInHours() {
        val s = Schedule.DEFAULT
        for (h in 0..23) assertEquals("hour $h", "scene:" + Scene.forHour(h).id, s.idFor(m(h), 0))
    }

    @Test fun slotsMixScenesAndWallpapersAndWrapPastMidnight() {
        val s = Schedule.parse("19:00 wall:city.jpg\n05:00 scene:dawn\n08:00 wall:lake.jpg\n")
        assertEquals("scene:dawn", s.idFor(m(5), 0))
        assertEquals("wall:lake.jpg", s.idFor(m(12, 30), 0))
        assertEquals("wall:city.jpg", s.idFor(m(23, 59), 0))
        assertEquals("wall:city.jpg", s.idFor(m(2), 0)) // still last night's slot
    }

    @Test fun severalEntriesTakeTurnsByDay() {
        val s = Schedule.parse("08:00 scene:fog, wall:lake.jpg, wall:sea.webp\n20:00 scene:night")
        assertEquals("scene:fog", s.idFor(m(9), 0))
        assertEquals("wall:lake.jpg", s.idFor(m(9), 1))
        assertEquals("wall:sea.webp", s.idFor(m(9), 2))
        assertEquals("scene:fog", s.idFor(m(9), 3))
    }

    @Test fun earlyMorningUsesYesterdaysTurn() {
        val s = Schedule.parse("06:00 scene:dawn\n22:00 wall:a.jpg, wall:b.jpg")
        assertEquals("wall:a.jpg", s.idFor(m(23), 10))
        assertEquals("wall:a.jpg", s.idFor(m(1), 11)) // same night, after midnight
    }

    @Test fun clockPlacesAndComments() {
        val s = Schedule.parse("# hello\nclock lake.jpg top=180 size=380 left=96 # comment\n08:00 wall:lake.jpg")
        assertEquals(ClockPlace(180f, 380f, 96f), s.clocks["lake.jpg"])
        assertTrue(s.problems.isEmpty())
    }

    @Test fun badLinesAreReportedNotFatal() {
        val s = Schedule.parse("8am scene:fog\n09:00 wall:../../etc\n10:00 scene:dawn\nclock x.jpg depth=3")
        assertEquals(1, s.slots.size)
        assertEquals(4, s.problems.size) // bad time; bad entry + nothing left to show; unknown key
    }

    @Test fun emptyScheduleHasNoAnswer() {
        assertNull(Schedule.parse("# nothing").idFor(m(9), 0))
    }
}
