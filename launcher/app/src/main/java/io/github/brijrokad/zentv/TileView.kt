package io.github.brijrokad.zentv

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.text.TextUtils
import android.view.Gravity
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView

/**
 * One tile: the bare icon with a soft shadow and the name underneath. Focus lifts the icon a little
 * (scale 1.16, up 6px) and swaps the shadow for a white glow, as in the approved preview.
 */
class TileView(context: Context, private val d: Design, val entry: Entry, labelWidth: Float) : LinearLayout(context) {
    private val icon = IconView(context)
    private val label = TextView(context)
    var art: TileArt? = null
        set(v) { field = v; icon.invalidate() }
    var favourite = false
        set(v) { field = v; icon.invalidate() }
    var dimmed = false
        set(v) { field = v; alpha = if (v) 0.45f else 1f }
    private val star = context.getDrawable(R.drawable.ic_star)

    init {
        orientation = VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        isFocusable = true
        isFocusableInTouchMode = true
        clipChildren = false
        clipToPadding = false
        contentDescription = when (entry) {
            is Entry.Input -> entry.cecName?.let { "${entry.label}, $it" } ?: entry.label
            else -> entry.label
        }
        val box = d.ipx(144f)
        addView(icon, LayoutParams(box, box))
        label.text = entry.label
        label.maxLines = 1
        label.ellipsize = TextUtils.TruncateAt.END
        label.gravity = Gravity.CENTER_HORIZONTAL
        label.setShadowLayer(d.px(4f), 0f, d.px(1f), Color.argb(102, 0, 0, 0))
        d.text(label, 20f, 400, Color.argb(230, 243, 246, 250))
        addView(label, LayoutParams(d.ipx(labelWidth), LayoutParams.WRAP_CONTENT).apply { topMargin = d.ipx(12f) })
        setOnFocusChangeListener { _, has -> focus(has) }
    }

    private fun focus(has: Boolean) {
        icon.animate().scaleX(if (has) 1.16f else 1f).scaleY(if (has) 1.16f else 1f)
            .translationY(if (has) -d.px(6f) else 0f).setDuration(140).start()
        d.text(label, 20f, if (has) 600 else 400, if (has) Color.WHITE else Color.argb(230, 243, 246, 250))
        icon.invalidate()
    }

    private inner class IconView(context: Context) : View(context) {
        private val paint = Paint(Paint.FILTER_BITMAP_FLAG or Paint.ANTI_ALIAS_FLAG)

        override fun onDraw(c: Canvas) {
            val a = art ?: return
            val left = -a.pad
            val top = -a.pad
            c.drawBitmap(if (this@TileView.hasFocus() || this@TileView.isFocused) a.glow else a.shadow, left, top, paint)
            c.drawBitmap(a.icon, left, top, paint)
            if (favourite && star != null) {
                val s = d.ipx(30f)
                val inset = d.ipx(12f)
                star.setBounds(width - inset - s, inset, width - inset, inset + s)
                star.draw(c)
            }
        }
    }
}
