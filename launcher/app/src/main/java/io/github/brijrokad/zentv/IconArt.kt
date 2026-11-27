package io.github.brijrokad.zentv

import android.content.ComponentName
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.BlurMaskFilter
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.drawable.AdaptiveIconDrawable
import android.graphics.drawable.Drawable
import kotlin.math.roundToInt

/**
 * Tile art, rendered once per entry on a worker thread: the icon itself (no board), its soft shadow
 * and its focus glow. Sizes are design pixels at 1.5x, as in the approved preview (a 96px icon box
 * zoomed to 144).
 */
class TileArt(val icon: Bitmap, val shadow: Bitmap, val glow: Bitmap, val pad: Float)

class IconArt(private val context: Context, private val d: Design) {
    private val pm = context.packageManager
    private val box = d.px(144f)
    private val pad = d.px(36f)
    private val consoleLogos: Map<ConsoleBrand, String> = run {
        val names = runCatching { context.assets.list("consoles")?.toList() }.getOrNull().orEmpty()
        ConsoleBrand.entries.mapNotNull { b ->
            names.firstOrNull { it.substringBeforeLast('.') == b.logoName }?.let { b to "consoles/$it" }
        }.toMap()
    }

    fun render(e: Entry): TileArt {
        val size = (box + 2 * pad).roundToInt()
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        c.translate(pad, pad)
        when (e) {
            is Entry.App -> if (e.isLiveTv) glyph(c, R.drawable.ic_antenna, 63f, 63f) else app(c, e)
            is Entry.Input -> input(c, e)
            Entry.SystemSettings -> glyph(c, R.drawable.ic_gear, 66f, 66f)
            Entry.ZentvSettings -> glyph(c, R.drawable.app_icon, 84f, 84f)
            Entry.AllApps -> glyph(c, R.drawable.ic_apps, 63f, 63f)
        }
        return TileArt(bmp, halo(bmp, Color.argb(89, 0, 0, 0), d.px(10f), d.px(4.5f)), halo(bmp, Color.argb(191, 255, 255, 255), d.px(16f), 0f), pad)
    }

    private fun halo(src: Bitmap, color: Int, radius: Float, dy: Float): Bitmap {
        val blur = Paint().apply { maskFilter = BlurMaskFilter(radius.coerceAtLeast(1f), BlurMaskFilter.Blur.NORMAL) }
        val offset = IntArray(2)
        val alpha = src.extractAlpha(blur, offset)
        val out = Bitmap.createBitmap(src.width, src.height, Bitmap.Config.ARGB_8888)
        Canvas(out).drawBitmap(alpha, offset[0].toFloat(), offset[1] + dy, Paint().apply { this.color = color })
        alpha.recycle()
        return out
    }

    private fun glyph(c: Canvas, res: Int, w: Float, h: Float) {
        val dr = context.getDrawable(res) ?: return
        drawCentered(c, dr, d.px(w), d.px(h))
    }

    private fun drawCentered(c: Canvas, dr: Drawable, w: Float, h: Float, dy: Float = 0f) {
        val l = (box - w) / 2
        val t = (box - h) / 2 + dy
        dr.setBounds(l.roundToInt(), t.roundToInt(), (l + w).roundToInt(), (t + h).roundToInt())
        dr.draw(c)
    }

    private fun app(c: Canvas, e: Entry.App) {
        val cn = ComponentName(e.packageName, e.className)
        val icon = runCatching { pm.getActivityIcon(cn) }.getOrNull()
        val hasOwnIcon = runCatching { pm.getActivityInfo(cn, 0).let { it.iconResource != 0 } }.getOrDefault(false)
        if (icon is AdaptiveIconDrawable && icon.foreground != null) {
            if (readableOnDark(icon.foreground)) {
                // The bare mark: the foreground layer, scaled so its 72dp visible area spans 85% of the box.
                val full = box * 0.85f * 1.5f
                val off = (box - full) / 2
                icon.foreground.setBounds(off.roundToInt(), off.roundToInt(), (off + full).roundToInt(), (off + full).roundToInt())
                icon.foreground.draw(c)
            } else {
                rounded(c, icon, box * 0.7f, box * 0.7f)
            }
            return
        }
        if (icon != null && hasOwnIcon) {
            rounded(c, icon, box * 0.7f, box * 0.7f)
            return
        }
        // No icon of its own: use the TV banner, if any, at 16:9.
        val banner = runCatching { pm.getActivityBanner(cn) ?: pm.getApplicationBanner(e.packageName) }.getOrNull()
        if (banner != null) rounded(c, banner, box * 0.95f, box * 0.95f * 9f / 16f)
        else if (icon != null) rounded(c, icon, box * 0.7f, box * 0.7f)
        else letter(c, e.label)
    }

    private fun rounded(c: Canvas, dr: Drawable, w: Float, h: Float) {
        val l = (box - w) / 2
        val t = (box - h) / 2
        val clip = Path().apply { addRoundRect(RectF(l, t, l + w, t + h), w * 0.2f, w * 0.2f, Path.Direction.CW) }
        c.save()
        c.clipPath(clip)
        drawCentered(c, dr, w, h)
        c.restore()
    }

    private fun letter(c: Canvas, label: String) {
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.WHITE
            textSize = d.px(72f)
            typeface = Typeface.create(Typeface.DEFAULT, 600, false)
            textAlign = Paint.Align.CENTER
        }
        val fm = p.fontMetrics
        c.drawText(label.take(1).uppercase(), box / 2, box / 2 - (fm.ascent + fm.descent) / 2, p)
    }

    /** True if a foreground layer is light or colourful enough to stand alone on a dark scene. */
    private fun readableOnDark(fg: Drawable): Boolean {
        val n = 48
        val b = Bitmap.createBitmap(n, n, Bitmap.Config.ARGB_8888)
        fg.setBounds(0, 0, n, n)
        fg.draw(Canvas(b))
        var weight = 0.0
        var light = 0.0
        for (y in 0 until n) for (x in 0 until n) {
            val px = b.getPixel(x, y)
            val a = Color.alpha(px) / 255.0
            if (a < 0.1) continue
            val r = Color.red(px) / 255.0
            val g = Color.green(px) / 255.0
            val bl = Color.blue(px) / 255.0
            val lum = 0.2126 * r + 0.7152 * g + 0.0722 * bl
            val chroma = maxOf(r, g, bl) - minOf(r, g, bl)
            weight += a
            light += a * maxOf(lum, chroma)
        }
        b.recycle()
        // Mostly transparent with nothing drawn, or a full-bleed square: keep the whole icon instead.
        val coverage = weight / (n * n)
        return weight > 0 && coverage < 0.6 && light / weight >= 0.3
    }

    private fun input(c: Canvas, e: Entry.Input) {
        val console = e.console
        val logo = console?.let { consoleLogos[it.brand] }
        if (logo != null) {
            val bmp = runCatching { context.assets.open(logo).use { BitmapFactory.decodeStream(it) } }.getOrNull()
            if (bmp != null) {
                val max = d.px(93f)
                val k = minOf(max / bmp.width, max / bmp.height)
                val w = bmp.width * k
                val h = bmp.height * k
                val l = (box - w) / 2
                val t = (box - h) / 2
                c.drawBitmap(bmp, null, RectF(l, t, l + w, t + h), Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG))
                bmp.recycle()
                return
            }
        }
        if (console == null) {
            glyph(c, R.drawable.ic_hdmi, 69f, 45f)
            return
        }
        // zentv's fallback: the controller with the console's short name under it, as one icon.
        val textSize = d.px(19.5f)
        val gap = d.px(4.5f)
        val gw = d.px(69f)
        val gh = d.px(48f)
        val total = gh + gap + textSize
        val top = (box - total) / 2
        context.getDrawable(R.drawable.ic_controller)?.let { drawCentered(c, it, gw, gh, top + gh / 2 - box / 2) }
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = Color.rgb(243, 246, 250)
            this.textSize = textSize
            typeface = Typeface.create(Typeface.DEFAULT, 700, false)
            letterSpacing = 1.5f / 13f
            textAlign = Paint.Align.CENTER
        }
        c.drawText(console.shortName, box / 2, top + gh + gap + textSize * 0.8f, p)
    }
}
