package io.github.brijrokad.zentv

import android.app.Activity
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Paint
import android.graphics.RectF
import android.os.Bundle
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import java.util.Calendar

/**
 * All apps: every app, HDMI port and shortcut on the home scene's own blurred "glass" copy (enlarged a
 * little so the blur reads as bokeh) under a dark tint, six to a row. Hold OK: favourite, move, hide.
 */
class AllAppsActivity : Activity() {
    private lateinit var d: Design
    private lateinit var prefs: Prefs
    private lateinit var catalog: Catalog
    private lateinit var art: IconArt
    private lateinit var grid: GridLayout
    private lateinit var footer: TextView
    private lateinit var clock: TextView
    private lateinit var backdrop: Backdrop
    private var entries: List<Entry> = emptyList()
    private var showHidden = false
    private val artCache = HashMap<String, TileArt>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        d = Design(this)
        prefs = Prefs(this)
        catalog = Catalog(this)
        art = IconArt(this, d)

        val root = FrameLayout(this)
        backdrop = Backdrop()
        root.addView(backdrop, FrameLayout.LayoutParams(-1, -1))

        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(d.ipx(120f), d.ipx(72f), d.ipx(120f), d.ipx(64f))
            clipChildren = false
            clipToPadding = false
        }
        val header = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.BOTTOM }
        header.addView(TextView(this).apply { text = "All apps"; d.text(this, 52f, 500) }, LinearLayout.LayoutParams(0, -2, 1f))
        clock = TextView(this).apply {
            d.text(this, 44f, 300, Color.argb(230, 255, 255, 255))
            typeface = Design.antonio(this@AllAppsActivity, 300)
        }
        header.addView(clock, LinearLayout.LayoutParams(-2, -2))
        column.addView(header, LinearLayout.LayoutParams(-1, -2))

        grid = GridLayout(this).apply {
            columnCount = COLUMNS
            clipChildren = false
            clipToPadding = false
            setPadding(0, d.ipx(36f), 0, d.ipx(36f))
        }
        val scroll = ScrollView(this).apply {
            isVerticalScrollBarEnabled = false
            clipChildren = false
            clipToPadding = false
            isFillViewport = true
            addView(grid, FrameLayout.LayoutParams(-1, -2))
        }
        column.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f).apply { topMargin = d.ipx(8f) })

        footer = TextView(this).apply {
            d.text(this, 21f, 400, Color.argb(184, 243, 246, 250))
            isFocusable = true
            setOnClickListener { showHidden = !showHidden; build() }
            setOnFocusChangeListener { v, has -> (v as TextView).setTextColor(if (has) Color.WHITE else Color.argb(184, 243, 246, 250)) }
        }
        column.addView(footer, LinearLayout.LayoutParams(-1, -2).apply { topMargin = d.ipx(8f) })
        root.addView(column, FrameLayout.LayoutParams(-1, -1))
        setContentView(root)
    }

    override fun onResume() {
        super.onResume()
        val cal = Calendar.getInstance()
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        clock.text = formatClock(hour, cal.get(Calendar.MINUTE), prefs.clock24)
        backdrop.show(prefs.sceneNow(hour), prefs.tint)
        (application as ZentvApp).worker.execute {
            val loaded = catalog.load()
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                entries = loaded
                build()
            }
        }
    }

    private fun build() {
        val focusedKey = (grid.findFocus() as? TileView)?.entry?.key
        val hidden = prefs.hidden
        val favs = prefs.favourites.toSet()
        val visible = entries.filter { showHidden || it.key !in hidden }
        grid.removeAllViews()
        val colWidth = (d.px(1920f - 240f) - (COLUMNS - 1) * d.px(32f)) / COLUMNS
        val tiles = visible.mapIndexed { i, e ->
            TileView(this, d, e, 240f).also { t ->
                t.favourite = e.key in favs
                t.dimmed = e.key in hidden
                t.setOnClickListener { Menus.open(this, catalog, e) { build(); backdrop.show(prefs.sceneNow(Calendar.getInstance().get(Calendar.HOUR_OF_DAY)), prefs.tint) } }
                t.setOnLongClickListener { Menus.options(this, prefs, e, onHome = false) { build() }; true }
                grid.addView(t, GridLayout.LayoutParams().apply {
                    width = colWidth.toInt()
                    height = GridLayout.LayoutParams.WRAP_CONTENT
                    if (i >= COLUMNS) topMargin = d.ipx(40f)
                    if (i % COLUMNS != 0) leftMargin = d.ipx(32f)
                })
            }
        }
        val missing = tiles.filter { artCache[it.entry.key] == null }
        tiles.forEach { t -> artCache[t.entry.key]?.let { t.art = it } }
        if (missing.isNotEmpty()) {
            (application as ZentvApp).worker.execute {
                val made = missing.map { it.entry.key to art.render(it.entry) }
                runOnUiThread {
                    made.forEach { (k, a) -> artCache[k] = a }
                    tiles.forEach { t -> artCache[t.entry.key]?.let { t.art = it } }
                }
            }
        }
        val n = hidden.size
        val tail = when {
            n == 0 -> ""
            showHidden -> "   ·   Showing $n hidden (OK to hide them again)"
            else -> "   ·   $n hidden ${if (n == 1) "app" else "apps"} (OK to show)"
        }
        footer.text = "OK: open   ·   Hold OK: favourite · move · hide   ·   Back: home$tail"
        footer.isFocusable = n > 0
        (tiles.firstOrNull { it.entry.key == focusedKey } ?: tiles.firstOrNull())?.requestFocus()
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            finish()
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    override fun onDestroy() {
        backdrop.release()
        super.onDestroy()
    }

    /** The scene's glass layer, 110% size and a little more saturated, under the tint. */
    private inner class Backdrop : View(this@AllAppsActivity) {
        private var bmp: Bitmap? = null
        private var shown: Scene? = null
        private var tint = 45
        private val dst = RectF()
        private val paint = Paint(Paint.FILTER_BITMAP_FLAG).apply {
            colorFilter = ColorMatrixColorFilter(ColorMatrix().apply { setSaturation(1.25f) })
        }

        fun show(s: Scene, tintPercent: Int) {
            tint = tintPercent
            if (s != shown) {
                bmp?.recycle()
                bmp = runCatching {
                    context.assets.open(s.glass).use {
                        BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inPreferredConfig = Bitmap.Config.RGB_565 })
                    }
                }.getOrNull()
                shown = s
            }
            invalidate()
        }

        override fun onDraw(c: Canvas) {
            bmp?.let {
                val dx = width * 0.05f
                val dy = height * 0.05f
                dst.set(-dx, -dy, width + dx, height + dy)
                c.drawBitmap(it, null, dst, paint)
            } ?: c.drawColor(0xFF0D1020.toInt())
            c.drawColor(Color.argb((tint / 100f * 255).toInt(), 8, 8, 14))
        }

        fun release() {
            bmp?.recycle()
            bmp = null
        }
    }

    companion object {
        const val COLUMNS = 6
    }
}
