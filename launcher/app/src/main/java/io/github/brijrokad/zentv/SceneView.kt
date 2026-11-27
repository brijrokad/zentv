package io.github.brijrokad.zentv

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapShader
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.LinearGradient
import android.graphics.Matrix
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import android.view.View
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

/**
 * The home screen above the favourites row, drawn natively (no WebView, no couch-tv code):
 * scene background → clock (frosted glass or tall) → the scene's cut-out, so the peaks overlap the
 * digits → flip or analog clock → the date → a soft scrim behind the favourites row.
 *
 * The frosted-glass clock fills the digits with the scene's own pre-blurred "glass" layer, aligned to
 * the screen, then adds a thin bright rim and a diagonal sheen. Android 11 has no RenderEffect, so the
 * blur comes from the ready-made glass image rather than a live blur.
 */
class SceneView(context: Context, private val d: Design) : View(context) {
    var scene: Background? = null
        private set
    var face: ClockFace = ClockFace.FROSTED
        set(v) { field = v; invalidate() }
    var h24 = false
        set(v) { field = v; invalidate() }
    var hour = 0
        private set
    var minute = 0
        private set
    var dateLine = ""
        set(v) { field = v; invalidate() }

    private var bg: Bitmap? = null
    private var fg: Bitmap? = null
    private var glass: Bitmap? = null
    private var loading: Background? = null

    private val bmpPaint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rimFill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(20, 255, 255, 255) }
    private val rimStroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        color = Color.argb(140, 255, 255, 255)
        strokeJoin = Paint.Join.ROUND
    }
    private val sheen = Paint(Paint.ANTI_ALIAS_FLAG)
    private val plain = Paint(Paint.ANTI_ALIAS_FLAG)
    private val datePaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val scrim = Paint()
    private val card = Paint(Paint.ANTI_ALIAS_FLAG)
    private val line = Paint(Paint.ANTI_ALIAS_FLAG)
    private val full = RectF()
    private val faceFill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.argb(115, 12, 14, 24) }
    private val ring = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; color = Color.argb(191, 255, 255, 255) }
    private val tick = Paint(Paint.ANTI_ALIAS_FLAG).apply { strokeCap = Paint.Cap.ROUND; color = Color.argb(217, 255, 255, 255) }
    private val hand = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE; strokeCap = Paint.Cap.ROUND }
    private val border = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; color = Color.argb(31, 255, 255, 255) }
    private val cardRect = RectF()
    private val clockFont: Typeface = Design.antonio(context, 300)
    private val flipFont: Typeface = Design.antonio(context, 400)

    init {
        datePaint.typeface = Typeface.create(Typeface.DEFAULT, 400, false)
        datePaint.textSize = d.px(30f)
        datePaint.color = Color.argb(235, 255, 255, 255)
        datePaint.letterSpacing = 0.5f / 30f
        datePaint.setShadowLayer(d.px(6f), 0f, d.px(1f), Color.argb(89, 0, 0, 0))
    }

    fun setTime(h: Int, m: Int) {
        if (h == hour && m == minute) return
        hour = h
        minute = m
        invalidate()
    }

    /** Switches scene; images are decoded off the UI thread and swapped in when ready. */
    fun showScene(s: Background) {
        if (s == scene || s == loading) return
        loading = s
        val app = context.applicationContext as ZentvApp
        app.worker.execute {
            val w = screenWidth()
            val b = Wallpapers.decode(context, s.image, Bitmap.Config.RGB_565, w)
            // Built-in scenes bring their own blurred layer; a wallpaper without one is blurred here.
            val g = s.glass?.let { Wallpapers.decode(context, it, Bitmap.Config.RGB_565, 1920) } ?: b?.let { Wallpapers.blur(it) }
            val f = s.cutout?.let { Wallpapers.decode(context, it, Bitmap.Config.ARGB_8888, w) }
            post {
                if (loading != s) return@post
                bg?.recycle(); fg?.recycle(); glass?.recycle()
                bg = b; glass = g; fg = f; scene = s; loading = null
                fillPaint.shader = null
                invalidate()
            }
        }
    }

    private fun screenWidth(): Int = resources.displayMetrics.let { maxOf(it.widthPixels, it.heightPixels) }


    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        fillPaint.shader = null
        scrim.shader = LinearGradient(
            0f, h - d.px(300f), 0f, h.toFloat(),
            Color.argb(0, 0, 0, 0), Color.argb(107, 0, 0, 0), Shader.TileMode.CLAMP,
        )
    }

    override fun onDraw(c: Canvas) {
        val w = width.toFloat()
        val h = height.toFloat()
        full.set(0f, 0f, w, h)
        val s = scene
        bg?.let { c.drawBitmap(it, null, full, bmpPaint) } ?: c.drawColor(0xFF0D1020.toInt())
        if (s != null) {
            when (face) {
                ClockFace.FROSTED -> frosted(c, s)
                ClockFace.TALL -> tall(c, s)
                else -> Unit
            }
            fg?.let { c.drawBitmap(it, null, full, bmpPaint) }
            when (face) {
                ClockFace.FLIP -> flip(c)
                ClockFace.ANALOG -> analog(c)
                else -> Unit
            }
        }
        c.drawRect(0f, h - d.px(300f), w, h, scrim)
        if (dateLine.isNotEmpty()) c.drawText(dateLine, d.px(96f), d.px(56f + 38f), datePaint)
    }

    private fun text(): String = formatClock(hour, minute, h24)

    /** Sets up [p] for the scene's clock and returns the baseline and left edge of the text. */
    private fun place(p: Paint, s: Background, t: String): Triple<Float, Float, Float> {
        p.typeface = clockFont
        p.textSize = d.px(s.clockSize)
        p.letterSpacing = -0.02f
        p.textAlign = Paint.Align.LEFT
        val width = p.measureText(t)
        val left = s.clockLeft?.let { d.px(it) } ?: ((this.width - width) / 2f)
        val fm = p.fontMetrics
        val lineHeight = p.textSize * 0.82f
        val baseline = d.px(s.clockTop) + (lineHeight - (fm.descent - fm.ascent)) / 2f - fm.ascent
        return Triple(left, baseline, width)
    }

    private fun frosted(c: Canvas, s: Background) {
        val t = text()
        val g = glass ?: return
        if (fillPaint.shader == null) {
            fillPaint.shader = BitmapShader(g, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP).apply {
                setLocalMatrix(Matrix().apply { setScale(width / g.width.toFloat(), height / g.height.toFloat()) })
            }
            fillPaint.colorFilter = if (s.fill.isIdentity) null else ColorMatrixColorFilter(ColorMatrix(s.fill.matrix()))
            fillPaint.alpha = (s.fill.alpha * 255).toInt()
        }
        val (x, y, tw) = place(fillPaint, s, t)
        place(rimFill, s, t)
        place(rimStroke, s, t)
        place(sheen, s, t)
        rimStroke.strokeWidth = d.px(1.5f)
        fillPaint.setShadowLayer(d.px(14f), 0f, d.px(6f), Color.argb(41, 0, 0, 0))
        c.drawText(t, x, y, fillPaint)
        c.drawText(t, x, y, rimFill)
        c.drawText(t, x, y, rimStroke)
        // Diagonal sheen across the clock box (CSS-style 160° gradient).
        val top = d.px(s.clockTop)
        val bh = d.px(s.clockSize) * 0.82f
        val a = Math.toRadians(160.0)
        val dx = sin(a).toFloat()
        val dy = -cos(a).toFloat()
        val len = abs(tw * dx) + abs(bh * dy)
        val cx = x + tw / 2
        val cy = top + bh / 2
        sheen.shader = LinearGradient(
            cx - dx * len / 2, cy - dy * len / 2, cx + dx * len / 2, cy + dy * len / 2,
            intArrayOf(Color.argb(128, 255, 255, 255), 0, 0, Color.argb(51, 255, 255, 255)),
            floatArrayOf(0f, 0.38f, 0.7f, 1f), Shader.TileMode.CLAMP,
        )
        c.drawText(t, x, y, sheen)
    }

    private fun tall(c: Canvas, s: Background) {
        val t = text()
        val (x, y, _) = place(plain, s, t)
        plain.shader = null
        plain.color = Color.argb(240, 255, 255, 255)
        plain.setShadowLayer(d.px(15f), 0f, d.px(6f), Color.argb(64, 0, 0, 0))
        c.drawText(t, x, y, plain)
        plain.clearShadowLayer()
    }

    private fun flip(c: Canvas) {
        val hh = (if (h24) hour else ((hour + 11) % 12) + 1).toString().padStart(2, '0')
        val mm = minute.toString().padStart(2, '0')
        val cw = d.px(300f)
        val ch = d.px(340f)
        val gap = d.px(28f)
        val top = d.px(170f)
        var left = (width - (2 * cw + gap)) / 2
        plain.typeface = flipFont
        plain.textSize = d.px(250f)
        plain.textAlign = Paint.Align.CENTER
        plain.letterSpacing = 0f
        plain.color = Color.rgb(244, 241, 234)
        plain.shader = null
        card.color = Color.argb(209, 14, 16, 26)
        card.setShadowLayer(d.px(25f), 0f, d.px(20f), Color.argb(102, 0, 0, 0))
        line.color = Color.argb(140, 0, 0, 0)
        border.strokeWidth = d.px(1f)
        val fm = plain.fontMetrics
        for (digits in listOf(hh, mm)) {
            val r = cardRect.apply { set(left, top, left + cw, top + ch) }
            c.drawRoundRect(r, d.px(28f), d.px(28f), card)
            c.drawRoundRect(r, d.px(28f), d.px(28f), border)
            c.drawText(digits, r.centerX(), r.centerY() - (fm.ascent + fm.descent) / 2, plain)
            c.drawRect(left, r.centerY() - d.px(1.5f), left + cw, r.centerY() + d.px(1.5f), line)
            left += cw + gap
        }
        plain.textAlign = Paint.Align.LEFT
    }

    private fun analog(c: Canvas) {
        val k = d.px(380f) / 200f
        val cx = width / 2f
        val cy = d.px(140f) + 100f * k
        ring.strokeWidth = 2f * k
        c.drawCircle(cx, cy, 96f * k, faceFill)
        c.drawCircle(cx, cy, 96f * k, ring)
        tick.strokeWidth = 3f * k
        for (i in 0 until 4) {
            val a = Math.toRadians(i * 90.0)
            c.drawLine(cx + (88f * sin(a)).toFloat() * k, cy - (88f * cos(a)).toFloat() * k,
                cx + (76f * sin(a)).toFloat() * k, cy - (76f * cos(a)).toFloat() * k, tick)
        }
        val ha = Math.toRadians(((hour % 12) + minute / 60.0) * 30.0)
        val ma = Math.toRadians(minute * 6.0)
        hand.strokeWidth = 6f * k
        c.drawLine(cx, cy, cx + (39.6f * sin(ha)).toFloat() * k, cy - (39.6f * cos(ha)).toFloat() * k, hand)
        hand.strokeWidth = 3.5f * k
        c.drawLine(cx, cy, cx + (53.7f * sin(ma)).toFloat() * k, cy - (53.7f * cos(ma)).toFloat() * k, hand)
        c.drawCircle(cx, cy, 5f * k, hand)
    }

    fun release() {
        bg?.recycle(); fg?.recycle(); glass?.recycle()
        bg = null; fg = null; glass = null; scene = null
    }
}
