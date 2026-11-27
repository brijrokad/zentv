# Private console icons (not committed)

Put your own console logos here to show them on the zentv home and All apps screens.
Everything in this folder except this README is **git-ignored**. The logos are other companies'
trademarked artwork: they go into **your** APK only, built on your Mac, and never into the public repo.
CI never has them. To build without them on purpose: `./gradlew -Pzentv.localIcons=false ...`.

| File | Shown for an HDMI-CEC device whose name contains |
|---|---|
| `playstation.png` / `.webp` / `.jpg` | `PlayStation`, `PS5`, `PS4` |
| `xbox.png` / `.webp` / `.jpg` | `Xbox` |
| `nintendo.png` / `.webp` / `.jpg` | `Nintendo`, `Switch` |

- PNG, WebP or JPG; the build copies it into your APK as-is (Android reads all three). Use a **real** transparent background (not a checkerboard drawn into the picture), about 256–512 px square.
- The tile's label is always the port, `HDMI 1`, `HDMI 2`, …, never the console's name.
- No file, or a console not in the table: zentv draws its own fallback logo, a controller glyph with the
  console's short name (`PS5`, `XBOX`, `SWITCH`) underneath, all as one icon.
