package io.github.brijrokad.zentv

import android.app.Application
import android.os.Process
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** One worker thread for decoding scenes, loading the catalog and (weather build) the network. */
class ZentvApp : Application() {
    val worker: ExecutorService by lazy { Executors.newSingleThreadExecutor { r -> Thread(r, "zentv-worker") } }

    override fun onCreate() {
        super.onCreate()
        // CrashGuard: note the crash, then let Android handle it as usual. Never swallows anything.
        if (processName() == packageName) {
            val previous = Thread.getDefaultUncaughtExceptionHandler()
            Thread.setDefaultUncaughtExceptionHandler { t, e ->
                runCatching { CrashGuard.onCrash(this) }
                previous?.uncaughtException(t, e) ?: Process.killProcess(Process.myPid())
            }
        }
    }

    private fun processName(): String = getProcessName()
}
