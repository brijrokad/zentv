# Device profile: Sony KD-65X80K ("BRAVIA 4K VH21")

Source: `ZENTV_BUILD_PROMPT.md` v2, "Device profile". Every line is **unverified** until Phase 3 confirms it with read-only `adb` and records the evidence. Nothing here has been read from the TV yet.

| # | Line | Status | Phase 3 check |
|---|---|---|---|
| 1 | **Retail model:** KD-65X80K (2022 X80K series, 65") | unverified | `getprop ro.product.model`, `ro.boot.product.hardware.sku` |
| 2 | **Platform:** "BRAVIA 4K VH21" (what Settings → About shows) | unverified | `getprop ro.product.device`, `ro.product.name` |
| 3 | **OS:** ships with Google TV on Android TV OS. The user saw "Android TV" in About. Plan for Google TV. | unverified | `pm list packages` for `com.google.android.apps.tv.launcherx` vs `com.google.android.tvlauncher`; `getprop ro.build.version.release`, `ro.build.version.sdk` |
| 4 | **OS:** Basic TV mode on or off | unverified | home packages present and enabled; HOME resolver (`cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME`) |
| 5 | **Firmware:** updated to the latest Sony firmware before Phase 3. Build fingerprint to be recorded. | unverified | `getprop ro.build.fingerprint`, `ro.build.version.security_patch` |
| 6 | **Network:** Wi-Fi today | unverified | `dumpsys connectivity` (active transport); `dumpsys wifi` (saved-network owner, `cname=`) |
| 7 | **Network:** built-in Ethernet and USB Ethernet must stay usable | unverified (requirement) | Ethernet interface present (`ip link` read-only); smoke test links Ethernet if a cable or adapter is available |
| 8 | **Tuner/antenna:** unknown. Keep every tuner input enabled. | unverified | `dumpsys tv_input`; report whether any channels are configured |
| 9 | **Feature in use:** Sony IR/Bluetooth remote, including the voice button | unverified | map to packages in Phase 3; smoke test |
| 10 | **Feature in use:** Google TV phone remote | unverified | map to packages; smoke test |
| 11 | **Feature in use:** Google Home casting (Chromecast built-in) | unverified | map to packages; smoke test |
| 12 | **Feature in use:** Google Assistant | unverified | map to packages; smoke test |
| 13 | **Feature in use:** AirPlay/HomeKit | unverified | map to packages; smoke test |

## Reference data (not about this TV)

Hints from cleanyourtv `examples/sony-bravia-4k-vh21/` (read as data, pinned at `deba47ca`). That list covers the **KD-65X85K** on the same VH21 platform, not the X80K. Phase 3 checks each hint, and none of them is a fact about this TV.

- Google TV 12 (API 31), build `BRAVIA_VH21_M_PA-user 12 STT2.230505.001.S136 682241`, 3 GB RAM with about 480 MB available.
- Stock home `launcherx`. On two of three units `setupwraith` owned the saved Wi-Fi network (`cname=`).
- On the sibling VH22, `cmd package set-home-activity` "prints Success and changes nothing" while `launcherx` is enabled (`examples/sony-kd-65x82l`).
- The firmware asks for `targetSdk` 30 or higher, or Play Protect blocks the install.
- Live TV is `com.sony.dtv.tvx`. The remote's Settings button is scancode 646, and the YouTube and Prime Video buttons are scancodes 485 and 490.
