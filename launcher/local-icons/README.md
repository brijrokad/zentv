# Private console icons (not committed)

Put your own console logos here to show them on the zentv home and All apps screens.
Everything in this folder except this README is **git-ignored**. The logos are other companies'
trademarked artwork: they go into **your** APK only, built on your Mac, and never into the public repo.

| File | Shown for an HDMI-CEC device whose name contains |
|---|---|
| `playstation.png` | `PlayStation`, `PS5`, `PS4` |
| `xbox.png` | `Xbox` |
| `nintendo.png` | `Nintendo`, `Switch` |

- Use a PNG with a transparent background, about 256×256.
- The tile's label is always the port, `HDMI 1`, `HDMI 2`, …, never the console's name.
- No file, or a console not in the table: zentv draws its own fallback logo, a controller glyph with the
  console's short name (`PS5`, `XBOX`, `SWITCH`) underneath, all as one icon.
