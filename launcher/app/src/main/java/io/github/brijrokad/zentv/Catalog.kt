package io.github.brijrokad.zentv

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ResolveInfo
import android.media.tv.TvContract
import android.media.tv.TvInputInfo
import android.media.tv.TvInputManager

/** One thing the owner can open: an app, an HDMI port, or a zentv shortcut. */
sealed class Entry {
    abstract val key: String
    abstract val label: String

    data class App(
        override val key: String,
        override val label: String,
        val packageName: String,
        val className: String,
        val isLiveTv: Boolean = false,
    ) : Entry()

    /** An HDMI port. [label] is always "HDMI n"; [console] is what the CEC device name says, if anything. */
    data class Input(
        override val key: String,
        override val label: String,
        val port: Int,
        val inputId: String,
        val console: ConsoleMatch?,
        val cecName: String?,
    ) : Entry()

    /** Opens the TV's own Settings. */
    data object SystemSettings : Entry() {
        override val key = "zentv:settings"
        override val label = "Settings"
    }

    /** Opens zentv's settings. */
    data object ZentvSettings : Entry() {
        override val key = "zentv:self"
        override val label = "zentv"
    }

    /** The "All apps" tile at the end of the favourites row. */
    data object AllApps : Entry() {
        override val key = "zentv:allapps"
        override val label = "All apps"
    }

    companion object {
        /** Packages of the TV's live-channels app on the TVs zentv knows. Shown as "Live TV". */
        val LIVE_TV = setOf("com.google.android.tv", "com.android.tv", "com.tcl.tv", "com.sony.dtv.tvx")
    }
}

/** Reads what can be launched. Package visibility comes from the manifest's <queries>, not QUERY_ALL_PACKAGES. */
class Catalog(private val context: Context) {
    private val pm: PackageManager = context.packageManager

    fun load(): List<Entry> = apps() + inputs() + listOf(Entry.SystemSettings, Entry.ZentvSettings)

    private fun apps(): List<Entry.App> {
        val seen = LinkedHashMap<String, Entry.App>()
        for (category in listOf(Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER)) {
            val q = Intent(Intent.ACTION_MAIN).addCategory(category)
            for (ri in pm.queryIntentActivities(q, 0)) {
                val ai = ri.activityInfo ?: continue
                if (ai.packageName == context.packageName) continue
                // One tile per app: the TV (leanback) entry wins over a phone-style one.
                if (seen.values.any { it.packageName == ai.packageName }) continue
                val live = ai.packageName in Entry.LIVE_TV
                val label = if (live) "Live TV" else label(ri)
                seen["${ai.packageName}/${ai.name}"] =
                    Entry.App("app:${ai.packageName}/${ai.name}", label, ai.packageName, ai.name, live)
            }
        }
        return seen.values.sortedBy { it.label.lowercase() }
    }

    private fun label(ri: ResolveInfo): String =
        runCatching { ri.loadLabel(pm).toString().trim() }.getOrNull().orEmpty().ifEmpty { ri.activityInfo.packageName }

    /** HDMI ports from TvInputManager, with the HDMI-CEC device on each port (if one answered). */
    private fun inputs(): List<Entry.Input> {
        val tim = context.getSystemService(TvInputManager::class.java) ?: return emptyList()
        val all = runCatching { tim.tvInputList }.getOrNull().orEmpty()
        val ports = all.filter { it.type == TvInputInfo.TYPE_HDMI && it.parentId == null && !hidden(it) }
        val numbered = ports.mapIndexed { i, info ->
            val n = Consoles.portNumber(runCatching { info.loadLabel(context).toString() }.getOrNull()) ?: (i + 1)
            n to info
        }.sortedBy { it.first }
        return numbered.map { (n, port) ->
            val child = all.firstOrNull { it.parentId == port.id }
            val cec = child?.let { runCatching { it.loadLabel(context).toString() }.getOrNull() }
            Entry.Input("hdmi:$n", Consoles.portLabel(n), n, port.id, Consoles.match(cec), cec)
        }
    }

    private fun hidden(info: TvInputInfo) = runCatching { info.isHidden(context) }.getOrDefault(false)

    /** The intent that opens an entry, or null if it cannot be opened here. */
    fun intentFor(e: Entry): Intent? = when (e) {
        is Entry.App -> Intent(Intent.ACTION_MAIN)
            .setComponent(ComponentName(e.packageName, e.className))
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
        is Entry.Input -> Intent(Intent.ACTION_VIEW, TvContract.buildChannelUriForPassthroughInput(e.inputId))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Entry.SystemSettings -> Intent(android.provider.Settings.ACTION_SETTINGS)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        Entry.ZentvSettings, Entry.AllApps -> null
    }

    /** The stock home (any HOME activity that is not zentv), for CrashGuard's step-aside. */
    fun stockHome(): Intent? {
        val q = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
        val ri = pm.queryIntentActivities(q, 0)
            .filter { it.activityInfo?.packageName != context.packageName }
            .maxByOrNull { it.priority } ?: return null
        return Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME)
            .setComponent(ComponentName(ri.activityInfo.packageName, ri.activityInfo.name))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }
}
