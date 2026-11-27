package io.github.brijrokad.zentv

import android.app.Activity
import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.widget.Toast

/** Opening entries, the hold-OK menu and zentv's own settings, shared by both screens. */
object Menus {
    fun open(activity: Activity, catalog: Catalog, e: Entry, onChanged: () -> Unit) {
        when (e) {
            Entry.ZentvSettings -> settings(activity, onChanged)
            Entry.AllApps -> activity.startActivity(android.content.Intent(activity, AllAppsActivity::class.java))
            else -> {
                val intent = catalog.intentFor(e) ?: return
                try {
                    activity.startActivity(intent)
                } catch (_: ActivityNotFoundException) {
                    Toast.makeText(activity, "${e.label} can't be opened on this TV", Toast.LENGTH_LONG).show()
                } catch (_: SecurityException) {
                    Toast.makeText(activity, "${e.label} can't be opened on this TV", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    /** Hold OK: favourite/unfavourite, move (home row), hide/unhide (All apps). */
    fun options(activity: Activity, prefs: Prefs, e: Entry, onHome: Boolean, onChanged: () -> Unit) {
        if (e == Entry.AllApps) return
        val fav = e.key in prefs.favourites
        val hidden = e.key in prefs.hidden
        val actions = mutableListOf<Pair<String, () -> Unit>>()
        actions += (if (fav) "Remove from favourites" else "Add to favourites") to {
            prefs.favourites = FavouriteOps.toggle(prefs.favourites, e.key)
        }
        if (fav) {
            actions += "Move left" to { prefs.favourites = FavouriteOps.move(prefs.favourites, e.key, -1) }
            actions += "Move right" to { prefs.favourites = FavouriteOps.move(prefs.favourites, e.key, +1) }
        }
        val hideable = e is Entry.App || e is Entry.Input
        if (!onHome && hideable) {
            actions += (if (hidden) "Show in All apps" else "Hide from All apps") to {
                prefs.hidden = if (hidden) prefs.hidden - e.key else prefs.hidden + e.key
                if (!hidden) prefs.favourites = prefs.favourites - e.key
            }
        }
        AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle(e.label)
            .setItems(actions.map { it.first }.toTypedArray()) { _, i ->
                actions[i].second()
                onChanged()
            }.show()
    }

    fun settings(activity: Activity, onChanged: () -> Unit) {
        val prefs = Prefs(activity)
        val sceneLabel = if (prefs.scene == "auto") "Auto (by time of day)" else Wallpapers.byId(activity, prefs.scene)?.label ?: "Auto (by time of day)"
        val items = mutableListOf(
            "Scene: $sceneLabel",
            "Clock: ${prefs.clockFace.label}",
            if (prefs.clock24) "24-hour clock: on" else "24-hour clock: off",
            "All apps background: ${prefs.tint}% dark",
        )
        WeatherProvider.settingsLabel(activity)?.let { items += it }
        AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle("zentv")
            .setItems(items.toTypedArray()) { _, which ->
                val again = { onChanged(); settings(activity, onChanged) }
                when (which) {
                    0 -> choose(activity, "Scene", listOf("auto" to "Auto (by time of day)") + Wallpapers.all(activity).map { it.id to it.label }, prefs.scene) {
                        prefs.scene = it; again()
                    }
                    1 -> choose(activity, "Clock", ClockFace.entries.map { it.id to it.label }, prefs.clockFace.id) {
                        prefs.clockFace = ClockFace.byId(it); again()
                    }
                    2 -> { prefs.clock24 = !prefs.clock24; again() }
                    3 -> choose(activity, "All apps background", (20..80 step 10).map { it.toString() to "$it% dark" }, prefs.tint.toString()) {
                        prefs.tint = it.toInt(); again()
                    }
                    else -> WeatherProvider.openSettings(activity) { again() }
                }
            }.show()
    }

    private fun choose(activity: Activity, title: String, options: List<Pair<String, String>>, current: String, pick: (String) -> Unit) {
        val checked = options.indexOfFirst { it.first == current }
        AlertDialog.Builder(activity, R.style.Theme_Zentv_Dialog).setTitle(title)
            .setSingleChoiceItems(options.map { it.second }.toTypedArray(), checked) { dlg, i ->
                dlg.dismiss()
                pick(options[i].first)
            }.show()
    }
}
