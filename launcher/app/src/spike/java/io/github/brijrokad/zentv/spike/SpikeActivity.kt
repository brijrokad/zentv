package io.github.brijrokad.zentv.spike

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/** The test "home": shows the mode, lets the owner switch it with the D-pad, and tails the event log. */
class SpikeActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var log: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(64, 48, 64, 48)
            setBackgroundColor(Color.rgb(16, 24, 32))
        }
        status = TextView(this).apply { textSize = 28f; setTextColor(Color.WHITE) }
        root.addView(status)
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.START }
        for (mode in listOf("passthrough", "consume", "observe")) {
            row.addView(Button(this).apply {
                text = mode
                setOnClickListener { save(SpikeLog.config(context).copy(mode = mode)) }
            })
        }
        row.addView(Button(this).apply {
            text = "re-check on/off"
            setOnClickListener { val c = SpikeLog.config(context); save(c.copy(recheck = !c.recheck)) }
        })
        row.addView(Button(this).apply {
            text = "clear log"
            setOnClickListener { SpikeLog.clear(context); refresh() }
        })
        root.addView(row)
        log = TextView(this).apply { textSize = 13f; setTextColor(Color.rgb(170, 200, 220)); typeface = android.graphics.Typeface.MONOSPACE }
        root.addView(log)
        setContentView(root)
        SpikeLog.log(this, "activity created")
    }

    override fun onResume() {
        super.onResume()
        SpikeLog.log(this, "activity resumed")
        refresh()
    }

    override fun onPause() {
        SpikeLog.log(this, "activity paused")
        super.onPause()
    }

    private fun save(c: SpikeLog.Config) {
        SpikeLog.save(this, c)
        SpikeLog.log(this, "config changed to $c")
        refresh()
    }

    private fun refresh() {
        val c = SpikeLog.config(this)
        status.text = "zentv spike   mode=${c.mode}   re-check=${if (c.recheck) "on" else "off"}"
        log.text = SpikeLog.tail(this, 18).joinToString("\n") { it.substringAfter(' ') }
    }
}
