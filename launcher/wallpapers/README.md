# Your wallpapers

Put your own home-screen wallpapers here. They are **committed to the repo** and built into the APK, next to couch-tv's five scenes. They become public when the branch is pushed, so only add pictures you own and are happy to publish.

## Files

| File | What it is |
|---|---|
| `<name>.jpg` / `.png` / `.webp` | The wallpaper. Best at **3840×2160** (4K) or 1920×1080, 16:9. |
| `<name>-fg.png` / `.webp` (optional) | A cut-out with a transparent background, drawn **over** the clock. This is how the mountains overlap the digits in the built-in scenes. |
| `<name>-glass.jpg` (optional) | A blurred copy, used to fill the frosted-glass clock and behind All apps. Without one, zentv blurs the wallpaper itself. |
| `schedule.txt` | Which background shows at which time of day. See the comments inside. |

Names may use letters, digits, `.`, `-` and `_`. No spaces.

## Showing them

1. Add the image, for example `lake.jpg`.
2. In `schedule.txt`, put it in a time slot: `08:00  scene:fog, wall:lake.jpg`. With two or more entries in one slot, they take turns, one per day.
3. Optionally place the clock: `clock  lake.jpg  top=150 size=400`.
4. Every wallpaper also appears in zentv settings → Scene, so you can pick it as a fixed background.

## Privacy

Photos often carry hidden metadata, such as GPS location, camera serial numbers and dates.

- **CI rejects any wallpaper that still has metadata.**
- **Strip it, without re-compressing the image:**
  ```
  uv run python -m zenctl.imagemeta strip launcher/wallpapers/*
  ```
