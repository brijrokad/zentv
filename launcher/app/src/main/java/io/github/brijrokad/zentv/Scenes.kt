package io.github.brijrokad.zentv

/**
 * The five home scenes (couch-tv's AI scenes, reused under the owner's 2026-11-27 exception and
 * credited in THIRD_PARTY_NOTICES.md) and where the frosted-glass clock sits on each, in design pixels
 * on a 1920x1080 canvas. The values come from zentv's approved design preview, not from couch-tv code.
 *
 * [fill] tunes the glass texture seen through the digits: on the brightest and darkest scenes the raw
 * glass would read too flat, so it is brightened or darkened a little.
 */
enum class Scene(
    val id: String,
    val label: String,
    val hasCutout: Boolean,
    val clockTop: Float,
    val clockSize: Float,
    val clockLeft: Float?, // null = centred
    val fill: GlassFill,
) {
    NIGHT("night", "Night", true, 150f, 400f, null, GlassFill(brightness = 1.15f, saturation = 1.2f, alpha = 0.92f)),
    GOLDEN("golden", "Golden hour", true, 152f, 390f, null, GlassFill()),
    WATER("water", "Water", false, 268f, 420f, null, GlassFill()),
    FOG("fog", "Fog", true, 172f, 470f, 96f, GlassFill(brightness = 0.46f, saturation = 0.8f, contrast = 1.1f, alpha = 0.85f)),
    DAWN("dawn", "Dawn", true, 150f, 400f, null, GlassFill());

    /** 3840x2160 (couch-tv's @2x copies). Decoded at the screen's real size; see [sampleSizeFor]. */
    val background get() = "scenes/scene-$id@2x.jpg"
    val cutout get() = if (hasCutout) "scenes/scene-$id-fg@2x.webp" else null

    /** 1920x1080: couch-tv has no 4K glass layer, and a blur loses nothing when scaled up. */
    val glass get() = "scenes/scene-$id-glass.jpg"

    companion object {
        fun byId(id: String?): Scene? = entries.firstOrNull { it.id == id }

        /**
         * Power-of-two downscale for a 3840px-wide scene on a screen [screenWidthPx] wide: 1 on a TV whose
         * UI is drawn at 4K, 2 at 1080p (so a 1080p UI holds 1080p-sized bitmaps, not 4K ones).
         */
        fun sampleSizeFor(screenWidthPx: Int, imageWidthPx: Int = 3840): Int {
            var s = 1
            while (screenWidthPx > 0 && imageWidthPx / (s * 2) >= screenWidthPx) s *= 2
            return s
        }

        /**
         * "Auto": the scene follows the time of day. Dawn 05-08, fog 08-16, golden hour 16-19,
         * night otherwise (the owner's choice, 2026-11-27). Water is never picked automatically;
         * choose it in zentv settings.
         * (The idea of a time-of-day schedule comes from couch-tv; this is zentv's own mapping.)
         */
        fun forHour(hour: Int): Scene = when (hour) {
            in 5..7 -> DAWN
            in 8..15 -> FOG
            in 16..18 -> GOLDEN
            else -> NIGHT
        }
    }
}

data class GlassFill(
    val brightness: Float = 1f,
    val saturation: Float = 1f,
    val contrast: Float = 1f,
    val alpha: Float = 1f,
) {
    val isIdentity get() = brightness == 1f && saturation == 1f && contrast == 1f

    /**
     * A 4x5 colour matrix equal to CSS `saturate(s) brightness(b) contrast(c)` applied in that order.
     * Pure arithmetic (no android.graphics) so it can be unit-tested.
     */
    fun matrix(): FloatArray {
        val s = saturation
        val lr = 0.2126f
        val lg = 0.7152f
        val lb = 0.0722f
        val sat = floatArrayOf(
            lr + (1 - lr) * s, lg - lg * s, lb - lb * s, 0f, 0f,
            lr - lr * s, lg + (1 - lg) * s, lb - lb * s, 0f, 0f,
            lr - lr * s, lg - lg * s, lb + (1 - lb) * s, 0f, 0f,
            0f, 0f, 0f, 1f, 0f,
        )
        val bc = brightness * contrast
        val offset = (-0.5f * contrast + 0.5f) * 255f
        val out = FloatArray(20)
        for (row in 0 until 3) {
            for (col in 0 until 3) out[row * 5 + col] = sat[row * 5 + col] * bc
            out[row * 5 + 4] = offset
        }
        out[18] = 1f
        return out
    }
}

enum class ClockFace(val id: String, val label: String) {
    FROSTED("frosted", "Frosted glass"),
    TALL("tall", "Tall"),
    FLIP("flip", "Flip"),
    ANALOG("analog", "Analog");

    companion object {
        fun byId(id: String?): ClockFace = entries.firstOrNull { it.id == id } ?: FROSTED
    }
}

/** "7:42" (12-hour, no am/pm, as in the design) or "19:42". */
fun formatClock(hour: Int, minute: Int, h24: Boolean): String {
    val h = if (h24) hour else ((hour + 11) % 12) + 1
    val hh = if (h24) h.toString().padStart(2, '0') else h.toString()
    return "$hh:${minute.toString().padStart(2, '0')}"
}
