package io.github.brijrokad.zentv.spike

import android.content.Context
import android.os.SystemClock
import android.util.Log
import java.io.File

/**
 * Shared event log and config for the two processes (UI and :homekey). Plain files in the app's
 * own storage; the spike only records key codes, timings and its own state (never screen content).
 */
object SpikeLog {
    const val TAG = "zentv-spike"
    private const val LOG = "events.log"
    private const val CONFIG = "config.txt"

    fun log(ctx: Context, msg: String) {
        val line = "${System.currentTimeMillis()} up=${SystemClock.uptimeMillis()} ${procName()} $msg"
        Log.i(TAG, line)
        runCatching { File(ctx.filesDir, LOG).appendText(line + "\n") }
    }

    fun tail(ctx: Context, n: Int): List<String> =
        runCatching { File(ctx.filesDir, LOG).readLines().takeLast(n) }.getOrDefault(emptyList())

    fun clear(ctx: Context) {
        runCatching { File(ctx.filesDir, LOG).writeText("") }
    }

    /** mode = observe | passthrough | consume; recheck = on | off. Default: passthrough, recheck on. */
    data class Config(val mode: String = "passthrough", val recheck: Boolean = true)

    fun config(ctx: Context): Config =
        runCatching {
            val kv = File(ctx.filesDir, CONFIG).readLines().mapNotNull {
                it.split("=", limit = 2).takeIf { p -> p.size == 2 }?.let { p -> p[0] to p[1] }
            }.toMap()
            Config(kv["mode"] ?: "passthrough", kv["recheck"] != "off")
        }.getOrDefault(Config())

    fun save(ctx: Context, c: Config) {
        File(ctx.filesDir, CONFIG).writeText("mode=${c.mode}\nrecheck=${if (c.recheck) "on" else "off"}\n")
    }

    private fun procName(): String =
        runCatching { File("/proc/self/cmdline").readText().trim('\u0000').substringAfterLast(':', "ui") }
            .getOrDefault("?")
}
