# What the zentv launcher can and cannot do

This page lists everything the zentv launcher asks Android for, and what it deliberately does without. CI checks the permission lists on every push.

## Permissions

| Build | `uses-permission` | Why |
|---|---|---|
| `core` (default) | **none** | It only lists and opens apps and HDMI inputs, and draws the home screen. |
| `weather` (opt-in) | `INTERNET` only | It fetches the current weather for one town from Open-Meteo (`api.open-meteo.com`, `geocoding-api.open-meteo.com`) over HTTPS. Any other host is refused in code before a connection opens. |

## What it can see

- **Apps that can be opened from a launcher.** The manifest's `<queries>` names the `LEANBACK_LAUNCHER` and `LAUNCHER` intents. It does not use `QUERY_ALL_PACKAGES`.
- **Other home apps.** zentv needs to see them so CrashGuard can hand over to the stock home.
- **TV inputs.** These provide the HDMI tiles, including the name an HDMI-CEC device announces (for example "PlayStation 5").

## The Home-button helper (`HomeKeyService`)

The helper is an accessibility service, and you switch it on yourself with `zentv launcher enable-home-key`. It never enables itself.

- **It filters key presses only.** `canRetrieveWindowContent="false"` is set and it asks for no accessibility events, so it cannot read the screen or anything you type.
- **It handles only the Home key.** It swallows the Home press and brings zentv to the front. Every other key passes through untouched.
- **It runs in its own process (`:homekey`).** A memory trim of the UI process does not take it down.
- **It checks once, briefly.** After a Home press it checks twice, at 1.2 s and 2.4 s, whether zentv's own window is in front. If not, it opens zentv once. It only looks at zentv's own process.
- **It has no boot receiver.** Nothing starts at boot, and nothing re-applies itself.
- **It steps aside after crashes.** If zentv crashes twice within 3 minutes before it finishes starting, Home goes to the stock home for 5 minutes.

## Things zentv does not have

- No boot receiver.
- No notification listener.
- No `WRITE_SECURE_SETTINGS`, `READ_TV_LISTINGS`, location, microphone or camera.
- No analytics and no crash reporting to anyone. Crash records stay in app storage, and only CrashGuard reads them.
- No native code (`.so` files), no WebView, no AndroidX, no coroutines.

## The HOME role

`MainActivity`'s HOME filter sits on an activity-alias, `.Home`, which ships **disabled**. On the TCL, Home reaches zentv through the helper, so the system never sees a second home app and never asks "which home?". The alias is turned on only by `zentv launcher set-home`, and only on TVs that honour `set-home-activity`.

## Removing it

zentv never uninstalls anything, itself included.

1. Run `zentv launcher revert --yes`. It turns the helper off and puts back what was recorded.
2. Remove zentv in Settings → Apps.
