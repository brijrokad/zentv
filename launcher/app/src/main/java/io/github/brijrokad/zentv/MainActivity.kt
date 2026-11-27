package io.github.brijrokad.zentv

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.format.DateFormat
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import java.util.Calendar
import java.util.Locale

/**
 * The home screen: scene + clock, the date, the weather pill (weather build only) and the favourites
 * row, ending in an "All apps" tile. Menu also opens All apps. Hold OK on a tile for its options.
 */
class MainActivity : Activity() {
    private lateinit var d: Design
    private lateinit var prefs: Prefs
    private lateinit var catalog: Catalog
    private lateinit var art: IconArt
    private lateinit var scene: SceneView
    private lateinit var dock: LinearLayout
    private lateinit var weather: LinearLayout
    private val main = Handler(Looper.getMainLooper())
    private var entries: List<Entry> = emptyList()
    private val artCache = HashMap<String, TileArt>()
    private var catalogDirty = true
    private var settled = false

    private val ticks = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) = refreshTime()
    }
    private val packages = object : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            i.data?.schemeSpecificPart?.let { pkg -> artCache.keys.removeAll { it.startsWith("app:$pkg/") } }
            catalogDirty = true
            if (hasWindowFocus()) loadCatalog()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        CrashGuard.onStart(this)
        catalog = Catalog(this)
        if (CrashGuard.steppingAside(this)) {
            stepAside()
            return
        }
        d = Design(this)
        prefs = Prefs(this)
        art = IconArt(this, d)

        val root = FrameLayout(this).apply { clipChildren = false; clipToPadding = false }
        scene = SceneView(this, d)
        root.addView(scene, FrameLayout.LayoutParams(-1, -1))

        weather = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(d.ipx(24f), d.ipx(12f), d.ipx(24f), d.ipx(12f))
            background = GradientDrawable().apply {
                cornerRadius = d.px(999f)
                setColor(Color.argb(87, 10, 14, 26))
                setStroke(maxOf(1, d.ipx(1f)), Color.argb(51, 255, 255, 255))
            }
            visibility = View.GONE
        }
        root.addView(weather, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.END).apply {
            topMargin = d.ipx(56f - 13f); marginEnd = d.ipx(96f)
        })

        dock = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.TOP
            clipChildren = false
            clipToPadding = false
        }
        root.addView(dock, FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL).apply {
            bottomMargin = d.ipx(56f)
        })
        setContentView(root)

        registerReceiver(packages, IntentFilter().apply {
            addAction(Intent.ACTION_PACKAGE_ADDED)
            addAction(Intent.ACTION_PACKAGE_REMOVED)
            addAction(Intent.ACTION_PACKAGE_CHANGED)
            addDataScheme("package")
        }, RECEIVER_NOT_EXPORTED) // system broadcasts still arrive; nothing else can send to it
    }

    private fun stepAside() {
        catalog.stockHome()?.let { runCatching { startActivity(it) } }
        finish()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (!::dock.isInitialized) return
        if (CrashGuard.steppingAside(this)) return stepAside()
        // Home pressed while zentv is already in front: back to the first favourite.
        dock.getChildAt(0)?.requestFocus()
    }

    override fun onResume() {
        super.onResume()
        if (!::dock.isInitialized) return
        registerReceiver(ticks, IntentFilter().apply {
            addAction(Intent.ACTION_TIME_TICK)
            addAction(Intent.ACTION_TIME_CHANGED)
            addAction(Intent.ACTION_TIMEZONE_CHANGED)
        }, RECEIVER_NOT_EXPORTED)
        scene.face = prefs.clockFace
        scene.h24 = prefs.clock24
        refreshTime()
        if (catalogDirty) loadCatalog() else buildDock()
        WeatherProvider.current(this) { showWeather(it) }
        if (!settled) main.postDelayed({ if (!settled) { settled = true; CrashGuard.onSettled(this) } }, 3000)
    }

    override fun onPause() {
        super.onPause()
        if (::dock.isInitialized) runCatching { unregisterReceiver(ticks) }
    }

    override fun onDestroy() {
        if (::dock.isInitialized) {
            runCatching { unregisterReceiver(packages) }
            scene.release()
        }
        main.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private fun refreshTime() {
        val cal = Calendar.getInstance()
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        scene.setTime(hour, cal.get(Calendar.MINUTE))
        scene.showScene(prefs.sceneNow(hour))
        val pattern = DateFormat.getBestDateTimePattern(Locale.getDefault(), "EEEEdMMMM")
        scene.dateLine = DateFormat.format(pattern, cal).toString()
    }

    private fun loadCatalog() {
        catalogDirty = false
        val app = application as ZentvApp
        app.worker.execute {
            val loaded = catalog.load()
            runOnUiThread {
                if (isDestroyed) return@runOnUiThread
                entries = loaded
                if (!prefs.favouritesChosen) prefs.favourites = FavouriteOps.defaults(loaded)
                buildDock()
            }
        }
    }

    private fun favouriteEntries(): List<Entry> {
        val byKey = entries.associateBy { it.key }
        return prefs.favourites.mapNotNull { byKey[it] }.filter { it.key !in prefs.hidden } + Entry.AllApps
    }

    private fun buildDock() {
        if (entries.isEmpty()) return
        val wanted = favouriteEntries()
        val current = (0 until dock.childCount).map { (dock.getChildAt(it) as TileView).entry.key }
        if (current == wanted.map { it.key }) return
        val focusedKey = (dock.findFocus()?.let { it as? TileView })?.entry?.key
        dock.removeAllViews()
        val tiles = wanted.map { e ->
            TileView(this, d, e, 204f).also { t ->
                t.setOnClickListener { Menus.open(this, catalog, e) { buildDockForced() } }
                t.setOnLongClickListener { Menus.options(this, prefs, e, onHome = true) { buildDockForced() }; true }
                dock.addView(t, LinearLayout.LayoutParams(-2, -2))
            }
        }
        val missing = tiles.filter { artCache[it.entry.key] == null }
        tiles.forEach { t -> artCache[t.entry.key]?.let { t.art = it } }
        if (missing.isNotEmpty()) {
            (application as ZentvApp).worker.execute {
                val made = missing.map { it.entry.key to art.render(it.entry) }
                runOnUiThread {
                    made.forEach { (k, a) -> artCache[k] = a }
                    tiles.forEach { t -> artCache[t.entry.key]?.let { t.art = it } }
                }
            }
        }
        (tiles.firstOrNull { it.entry.key == focusedKey } ?: tiles.firstOrNull())?.requestFocus()
    }

    private fun buildDockForced() {
        dock.removeAllViews()
        buildDock()
        scene.face = prefs.clockFace
        scene.h24 = prefs.clock24
        refreshTime()
        WeatherProvider.current(this) { showWeather(it) }
    }

    private fun showWeather(w: WeatherNow?) {
        weather.removeAllViews()
        if (w == null) {
            weather.visibility = View.GONE
            return
        }
        weather.addView(ImageView(this).apply { setImageResource(w.icon) }, LinearLayout.LayoutParams(d.ipx(32f), d.ipx(32f)))
        weather.addView(TextView(this).apply { text = w.temperature; d.text(this, 28f, 500) },
            LinearLayout.LayoutParams(-2, -2).apply { marginStart = d.ipx(14f) })
        weather.addView(TextView(this).apply { text = w.description; d.text(this, 20f, 400, Color.argb(209, 243, 246, 250)) },
            LinearLayout.LayoutParams(-2, -2).apply { marginStart = d.ipx(14f) })
        weather.visibility = View.VISIBLE
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_MENU && ::dock.isInitialized) {
            startActivity(Intent(this, AllAppsActivity::class.java))
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    @Deprecated("Back on the home screen stays on the home screen.")
    override fun onBackPressed() = Unit

    companion object {
        const val ACTION_HOME_KEY = "io.github.brijrokad.zentv.HOME_KEY"
    }
}
