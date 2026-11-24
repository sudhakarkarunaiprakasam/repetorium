# Microsoft Store listing assets

These assets are for the English-language desktop listing. The screenshots are
unmodified captures of the app at 1366 x 768 pixels, in PNG format, and are
below the Store's 50 MB per-image limit. Microsoft currently requires desktop
screenshots to be at least 1366 x 768 and recommends providing four or more.
`repetorium-app-tile-300x300.png` is the 300 x 300 app tile, and
`repetorium-app-icon-1024x1024.png` is the high-resolution 1024 x 1024 icon.
Regenerate app icons and Store icon assets with
`uv run python scripts/generate_icons.py`.

| File | Suggested caption |
| --- | --- |
| `screenshots/light-01-dashboard.png` | Review progress and choose what to study next. |
| `screenshots/light-02-skill-map.png` | Explore skills and how concepts connect. |
| `screenshots/light-03-library.png` | Import and manage learning packs. |
| `screenshots/light-04-settings.png` | Choose a theme and configure practice packs. |
| `screenshots/light-05-advanced-settings.png` | Customize mastery and review scheduling. |
| `screenshots/dark-01-dashboard.png` | Review progress and choose what to study next. |
| `screenshots/dark-02-skill-map.png` | Explore skills and how concepts connect. |
| `screenshots/dark-03-library.png` | Import and manage learning packs. |
| `screenshots/dark-04-settings.png` | Choose a theme and configure practice packs. |
| `screenshots/dark-05-advanced-settings.png` | Customize mastery and review scheduling. |

The dashboard, library, and settings captures use the repository's synthetic
test pack. The paired Skill Map captures use the locally installed pack,
filtered to `mortgage` to show a larger set of connected skills. Repetorium
itself ships without a learning pack. Refresh both themes at Store resolution
from the repository root with:

```sh
uv run python scripts/screenshots.py /tmp/repetorium-store-light 1366 768 light
uv run python scripts/screenshots.py /tmp/repetorium-store-dark 1366 768 dark
```

The renderer defaults to the synthetic test pack. Set `REPETORIUM_CONTENT_DIR`
to a local content-pack directory and `REPETORIUM_SCREENSHOT_MAP_SEARCH` to
`mortgage` to reproduce the focused map captures:

```sh
REPETORIUM_CONTENT_DIR=/path/to/pack REPETORIUM_SCREENSHOT_MAP_SEARCH=mortgage \
  uv run python scripts/screenshots.py /tmp/repetorium-map-light 1366 768 light
REPETORIUM_CONTENT_DIR=/path/to/pack REPETORIUM_SCREENSHOT_MAP_SEARCH=mortgage \
  uv run python scripts/screenshots.py /tmp/repetorium-map-dark 1366 768 dark
```

Copy `dashboard.png`, `library.png`, `settings.png`, and
`advanced_settings.png` from the general light/dark output directories, and
`knowledge_map.png` from the focused map directories, to the theme-prefixed
filenames in the table above.

Requirements reference: [Microsoft Store screenshots, images, and trailers](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images).
