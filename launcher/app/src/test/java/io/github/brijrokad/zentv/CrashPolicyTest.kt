package io.github.brijrokad.zentv

import io.github.brijrokad.zentv.CrashPolicy.Event
import io.github.brijrokad.zentv.CrashPolicy.Kind.CRASH
import io.github.brijrokad.zentv.CrashPolicy.Kind.SETTLED
import io.github.brijrokad.zentv.CrashPolicy.Kind.START
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CrashPolicyTest {
    private val p = CrashPolicy()
    private val s = 1000L

    @Test fun twoUnsettledCrashesInThreeMinutesStepAside() {
        val ev = listOf(Event(START, 0), Event(CRASH, 2 * s), Event(START, 10 * s), Event(CRASH, 12 * s), Event(START, 20 * s))
        assertEquals(12 * s + 5 * 60 * s, p.stepAsideUntil(ev, 21 * s))
    }

    @Test fun oneCrashIsNotEnough() {
        val ev = listOf(Event(START, 0), Event(CRASH, 2 * s), Event(START, 10 * s))
        assertNull(p.stepAsideUntil(ev, 11 * s))
    }

    @Test fun trimKillWithoutCrashRecordIsNotAFailure() {
        // Started, never settled, no crash written: the vendor trim or the low-memory killer.
        val ev = listOf(Event(START, 0), Event(START, 5 * s), Event(START, 10 * s), Event(START, 15 * s))
        assertEquals(emptyList<Long>(), p.failures(ev))
        assertNull(p.stepAsideUntil(ev, 16 * s))
    }

    @Test fun crashAfterSettlingIsNotCounted() {
        val ev = listOf(Event(START, 0), Event(SETTLED, 3 * s), Event(CRASH, 60 * s), Event(START, 61 * s), Event(SETTLED, 64 * s), Event(CRASH, 90 * s))
        assertNull(p.stepAsideUntil(ev, 91 * s))
    }

    @Test fun crashesFarApartDoNotStepAside() {
        val ev = listOf(Event(START, 0), Event(CRASH, 1 * s), Event(START, 240 * s), Event(CRASH, 241 * s))
        assertNull(p.stepAsideUntil(ev, 242 * s))
    }

    @Test fun stepAsideEndsAfterFiveMinutes() {
        val ev = listOf(Event(START, 0), Event(CRASH, 1 * s), Event(START, 5 * s), Event(CRASH, 6 * s))
        assertNull(p.stepAsideUntil(ev, 6 * s + 5 * 60 * s + 1))
    }

    @Test fun logRoundTripsAndIgnoresJunk() {
        val ev = listOf(Event(START, 1), Event(CRASH, 2))
        assertEquals(ev, p.parse(p.format(ev) + "garbage line\nSTART notanumber\n"))
    }
}
