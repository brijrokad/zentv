package io.github.brijrokad.zentv.spike

import android.accessibilityservice.AccessibilityService
import android.app.ActivityManager
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

/**
 * M3a: does a key-filter-only accessibility service receive the real remote's Home key on this TV,
 * and can it bring zentv to the front? Rule 9: key filtering only, own process (:homekey), no window
 * watching, no self-revival. The re-check reads only this app's own process importance.
 */
class HomeKeyService : AccessibilityService() {
    private val main = Handler(Looper.getMainLooper())
    private var launches = 0

    override fun onServiceConnected() {
        SpikeLog.log(this, "service connected config=${SpikeLog.config(this)}")
    }

    override fun onKeyEvent(event: KeyEvent): Boolean {
        val code = event.keyCode
        val interesting = code == KeyEvent.KEYCODE_HOME || code == KeyEvent.KEYCODE_VOLUME_UP ||
            code == KeyEvent.KEYCODE_VOLUME_DOWN || code >= 4000
        if (interesting) {
            SpikeLog.log(
                this,
                "key ${KeyEvent.keyCodeToString(code)}($code) action=${event.action} repeat=${event.repeatCount} " +
                    "device=${event.deviceId} source=0x${Integer.toHexString(event.source)} " +
                    "flags=0x${Integer.toHexString(event.flags)} scan=${event.scanCode}"
            )
        }
        if (code != KeyEvent.KEYCODE_HOME) return false
        val cfg = SpikeLog.config(this)
        return when (cfg.mode) {
            "consume" -> {
                if (event.action == KeyEvent.ACTION_UP) bringToFront(cfg, "consume")
                true
            }
            "passthrough" -> {
                if (event.action == KeyEvent.ACTION_UP) main.postDelayed({ bringToFront(cfg, "passthrough") }, 350)
                false
            }
            else -> false // observe: log only
        }
    }

    private fun bringToFront(cfg: SpikeLog.Config, why: String) {
        launch("$why launch")
        if (!cfg.recheck) return
        for ((i, delay) in listOf(1200L, 2400L).withIndex()) {
            main.postDelayed({
                val fg = uiInForeground()
                SpikeLog.log(this, "recheck ${i + 1} at +${delay}ms ui_foreground=$fg")
                if (!fg) launch("recheck ${i + 1} relaunch")
            }, delay)
        }
    }

    private fun launch(why: String) {
        launches++
        SpikeLog.log(this, "$why #$launches")
        val i = Intent(this, SpikeActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        runCatching { startActivity(i) }.onFailure { SpikeLog.log(this, "launch failed: ${it.javaClass.simpleName}: ${it.message}") }
    }

    /** Own app only: getRunningAppProcesses() returns just this app's processes. */
    private fun uiInForeground(): Boolean {
        val am = getSystemService(ActivityManager::class.java) ?: return false
        return am.runningAppProcesses.orEmpty().any {
            it.processName == packageName && it.importance == ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit // no event types requested

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        SpikeLog.log(this, "service destroyed")
        super.onDestroy()
    }
}
