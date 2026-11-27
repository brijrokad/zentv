package io.github.brijrokad.zentv

import org.junit.Assert.assertEquals
import org.junit.Test

class FavouritesTest {
    private fun app(pkg: String, live: Boolean = false) = Entry.App("app:$pkg/Main", pkg, pkg, "Main", live)

    @Test fun toggleAddsAtEndAndCaps() {
        assertEquals(listOf("a", "b"), FavouriteOps.toggle(listOf("a"), "b"))
        assertEquals(listOf("a"), FavouriteOps.toggle(listOf("a", "b"), "b"))
        assertEquals(listOf("a", "b"), FavouriteOps.toggle(listOf("a", "b"), "c", max = 2))
    }

    @Test fun moveStaysInBounds() {
        assertEquals(listOf("b", "a", "c"), FavouriteOps.move(listOf("a", "b", "c"), "b", -1))
        assertEquals(listOf("a", "b", "c"), FavouriteOps.move(listOf("a", "b", "c"), "a", -1))
        assertEquals(listOf("a", "c", "b"), FavouriteOps.move(listOf("a", "b", "c"), "b", +1))
        assertEquals(listOf("a", "b"), FavouriteOps.move(listOf("a", "b"), "zz", +1))
    }

    @Test fun defaultsPreferKnownAppsThenLiveTvThenConsoles() {
        val ps = Entry.Input("hdmi:1", "HDMI 1", 1, "in1", ConsoleMatch(ConsoleBrand.PLAYSTATION, "PS5"), "PlayStation 5")
        val bar = Entry.Input("hdmi:2", "HDMI 2", 2, "in2", null, "Soundbar")
        val all = listOf(app("com.example.other"), app("com.netflix.ninja"), app("com.tcl.tv", live = true), app("com.google.android.youtube.tv"), ps, bar)
        assertEquals(
            listOf("app:com.google.android.youtube.tv/Main", "app:com.netflix.ninja/Main", "app:com.tcl.tv/Main", "hdmi:1"),
            FavouriteOps.defaults(all),
        )
    }
}
