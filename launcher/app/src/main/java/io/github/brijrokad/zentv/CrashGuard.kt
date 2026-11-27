package io.github.brijrokad.zentv

import android.content.Context
import java.io.File

/**
 * CrashGuard (docs/ARCHITECTURE.md §6). If zentv crashes before it settles twice within 3 minutes, it
 * steps aside: for 5 minutes the Home button goes to the stock home and zentv opens it instead of itself.
 * A process death with no crash record (a vendor memory trim, the low-memory killer) is not a failure.
 *
 * The log is a small text file in app storage, shared by the UI process and the :homekey process
 * (SharedPreferences is not safe across processes). Nothing here repairs or re-applies anything.
 */
class CrashPolicy(
    private val windowMs: Long = 3 * 60_000L,
    private val failuresToStepAside: Int = 2,
    private val stepAsideMs: Long = 5 * 60_000L,
) {
    enum class Kind { START, SETTLED, CRASH }

    data class Event(val kind: Kind, val atMs: Long)

    /** Time (ms) of each start that crashed before it settled. */
    fun failures(events: List<Event>): List<Long> {
        val out = mutableListOf<Long>()
        var openStart: Long? = null
        var crashed = false
        fun close() {
            val s = openStart
            if (s != null && crashed) out += s
            openStart = null
            crashed = false
        }
        for (e in events.sortedBy { it.atMs }) {
            when (e.kind) {
                Kind.START -> {
                    close()
                    openStart = e.atMs
                }
                Kind.SETTLED -> {
                    openStart = null
                    crashed = false
                }
                Kind.CRASH -> if (openStart != null) crashed = true
            }
        }
        close()
        return out
    }

    /** Until when zentv should step aside, or null. */
    fun stepAsideUntil(events: List<Event>, nowMs: Long): Long? {
        val recent = failures(events).filter { nowMs - it <= windowMs }
        if (recent.size < failuresToStepAside) return null
        val lastCrash = events.filter { it.kind == Kind.CRASH }.maxOfOrNull { it.atMs } ?: return null
        val until = lastCrash + stepAsideMs
        return if (until > nowMs) until else null
    }

    fun parse(text: String): List<Event> = text.lineSequence().mapNotNull { line ->
        val parts = line.trim().split(' ')
        if (parts.size != 2) return@mapNotNull null
        val kind = runCatching { Kind.valueOf(parts[0]) }.getOrNull() ?: return@mapNotNull null
        val at = parts[1].toLongOrNull() ?: return@mapNotNull null
        Event(kind, at)
    }.toList()

    fun format(events: List<Event>): String = events.joinToString("") { "${it.kind} ${it.atMs}\n" }
}

object CrashGuard {
    private val policy = CrashPolicy()
    private const val KEEP_MS = 60 * 60_000L

    private fun file(context: Context) = File(context.filesDir, "crashguard.log")

    @Synchronized
    private fun append(context: Context, kind: CrashPolicy.Kind, now: Long = System.currentTimeMillis()) {
        val f = file(context)
        val old = runCatching { policy.parse(f.readText()) }.getOrDefault(emptyList())
        val kept = old.filter { now - it.atMs <= KEEP_MS } + CrashPolicy.Event(kind, now)
        runCatching {
            val tmp = File(f.path + ".tmp")
            tmp.writeText(policy.format(kept))
            tmp.renameTo(f)
        }
    }

    fun onStart(context: Context) = append(context, CrashPolicy.Kind.START)

    fun onSettled(context: Context) = append(context, CrashPolicy.Kind.SETTLED)

    fun onCrash(context: Context) = append(context, CrashPolicy.Kind.CRASH)

    /** True while zentv should leave the Home button to the stock home. Read by both processes. */
    fun steppingAside(context: Context, now: Long = System.currentTimeMillis()): Boolean {
        val events = runCatching { policy.parse(file(context).readText()) }.getOrDefault(emptyList())
        return policy.stepAsideUntil(events, now) != null
    }
}
