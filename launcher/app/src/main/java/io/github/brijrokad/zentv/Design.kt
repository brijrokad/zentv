package io.github.brijrokad.zentv

import android.content.Context
import android.graphics.Typeface
import android.util.TypedValue
import android.widget.TextView
import kotlin.math.roundToInt

/**
 * The approved design is drawn on a 1920x1080 canvas. [px] turns its pixel values into real pixels for
 * whatever resolution the TV renders its UI at, so the layout matches the preview on any panel.
 */
class Design(context: Context) {
    private val metrics = context.resources.displayMetrics
    val scale: Float = maxOf(metrics.widthPixels, metrics.heightPixels) / 1920f

    fun px(v: Float): Float = v * scale

    fun ipx(v: Float): Int = (v * scale).roundToInt()

    fun text(view: TextView, size: Float, weight: Int = 400, color: Int = 0xFFF3F6FA.toInt()) {
        view.setTextSize(TypedValue.COMPLEX_UNIT_PX, px(size))
        view.typeface = Typeface.create(Typeface.DEFAULT, weight, false)
        view.setTextColor(color)
        view.includeFontPadding = false
    }

    companion object {
        private val fonts = HashMap<Int, Typeface>()

        /** Antonio (SIL OFL 1.1, launcher/licenses/Antonio-OFL.txt), a variable font: one file, any weight. */
        fun antonio(context: Context, weight: Int): Typeface = synchronized(fonts) {
            fonts.getOrPut(weight) {
                runCatching {
                    Typeface.Builder(context.assets, "fonts/antonio.ttf")
                        .setFontVariationSettings("'wght' $weight")
                        .build()
                }.getOrNull() ?: Typeface.create("sans-serif-condensed", Typeface.NORMAL)
            }
        }
    }
}
