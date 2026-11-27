package io.github.brijrokad.zentv

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ScenesTest {
    @Test fun scheduleCoversEveryHour() {
        assertEquals(Scene.NIGHT, Scene.forHour(4))
        assertEquals(Scene.DAWN, Scene.forHour(5))
        assertEquals(Scene.DAWN, Scene.forHour(7))
        assertEquals(Scene.FOG, Scene.forHour(8))
        assertEquals(Scene.FOG, Scene.forHour(15))
        assertEquals(Scene.GOLDEN, Scene.forHour(16))
        assertEquals(Scene.GOLDEN, Scene.forHour(18))
        assertEquals(Scene.NIGHT, Scene.forHour(19))
        assertEquals(Scene.NIGHT, Scene.forHour(0))
        for (h in 0..23) assert(Scene.forHour(h) != Scene.WATER) // water is chosen by hand only
    }

    @Test fun assetPaths() {
        assertEquals("scenes/scene-night@2x.jpg", Scene.NIGHT.background)
        assertEquals("scenes/scene-night-fg@2x.webp", Scene.NIGHT.cutout)
        assertNull(Scene.WATER.cutout)
        assertEquals("scenes/scene-water-glass.jpg", Scene.WATER.glass)
    }

    @Test fun fourKScenesDecodeAtScreenSize() {
        assertEquals(1, Scene.sampleSizeFor(3840))
        assertEquals(2, Scene.sampleSizeFor(1920))
        assertEquals(1, Scene.sampleSizeFor(2560)) // never below the screen size
        assertEquals(4, Scene.sampleSizeFor(960))
        assertEquals(1, Scene.sampleSizeFor(0))
    }

    @Test fun clockFormats() {
        assertEquals("7:42", formatClock(19, 42, false))
        assertEquals("19:42", formatClock(19, 42, true))
        assertEquals("12:05", formatClock(0, 5, false))
        assertEquals("00:05", formatClock(0, 5, true))
        assertEquals("12:00", formatClock(12, 0, false))
    }

    @Test fun identityFillIsIdentityMatrix() {
        val m = GlassFill().matrix()
        val id = floatArrayOf(1f, 0f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 0f, 0f, 1f, 0f)
        assertArrayEquals(id, m, 1e-5f)
    }

    @Test fun brightnessScalesAndContrastOffsets() {
        val m = GlassFill(brightness = 0.5f, contrast = 2f).matrix()
        assertEquals(1f, m[0], 1e-5f) // 0.5 * 2
        assertEquals(-127.5f, m[4], 1e-3f)
    }
}
