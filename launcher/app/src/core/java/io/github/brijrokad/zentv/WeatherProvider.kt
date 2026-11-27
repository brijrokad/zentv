package io.github.brijrokad.zentv

import android.app.Activity

/**
 * Core build: no weather and no network code at all. The core APK has no INTERNET permission, and this
 * stub keeps any network class out of it. The weather build replaces this file (src/weather/).
 */
object WeatherProvider {
    const val AVAILABLE = false

    fun current(activity: Activity, onResult: (WeatherNow?) -> Unit) = onResult(null)

    fun settingsLabel(activity: Activity): String? = null

    fun openSettings(activity: Activity, done: () -> Unit) = done()
}
