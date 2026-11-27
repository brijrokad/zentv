package io.github.brijrokad.zentv

import android.accessibilityservice.AccessibilityService
import android.app.ActivityManager
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent

/**
 * The Home-button helper (rule 9, M3a result on the TCL: GO with consume + re-check).
 *
 * - Key filtering only: it never asks for window content or accessibility events.
 * - Own process (:homekey), so a heavy UI process being trimmed never takes the helper with it.
 * - Consume mode: the Home press is eaten, so the stock home never starts and no "which home?" race
 *   happens; zentv is brought to the front instead.
 * - Re-check: 1.2 s and 2.4 s later it checks whether zentv's own UI process is in the foreground
 *   (getRunningAppProcesses() only lists this app's processes) and relaunches once if not.
 * - CrashGuard: while zentv is stepping aside, Home is passed through to the stock home untouched.
 * - No boot receiver and no self-enable: the owner turns it on with `zentv launcher enable-home-key`.
 */
class HomeKeyService : AccessibilityService() {
    private val main = Handler(Looper.getMainLooper())

    override fun onKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_HOME) return false
        if (CrashGuard.steppingAside(this)) return false
        if (event.action == KeyEvent.ACTION_UP && !event.isCanceled) bringToFront()
        return true
    }

    private fun bringToFront() {
        main.removeCallbacksAndMessages(null)
        launch()
        for (delay in longArrayOf(1200L, 2400L)) {
            main.postDelayed({ if (!uiInForeground()) launch() }, delay)
        }
    }

    private fun launch() {
        val i = Intent(this, MainActivity::class.java)
            .setAction(MainActivity.ACTION_HOME_KEY)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
        runCatching { startActivity(i) }
    }

    private fun uiInForeground(): Boolean {
        val am = getSystemService(ActivityManager::class.java) ?: return false
        return am.runningAppProcesses.orEmpty().any {
            it.processName == packageName && it.importance == ActivityManager.RunningAppProcessInfo.IMPORTANCE_FOREGROUND
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        super.onDestroy()
    }
}
