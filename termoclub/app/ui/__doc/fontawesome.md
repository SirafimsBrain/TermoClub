# Font Awesome Free in TermoClub

## Decision

Use **Font Awesome Free 7.3.1** (desktop bundle) for icons, shipped **locally**
with the app — no CDN, no system font install required.

- Source: `https://use.fontawesome.com/releases/v7.3.1/fontawesome-free-7.3.1-desktop.zip`
- License: **SIL OFL 1.1** for the font files. It allows bundling, embedding,
  and redistributing the fonts with software (commercial use included).
  Attribution is embedded in the files; the original `LICENSE.txt` is kept at
  `termoclub/assets/fonts/LICENSE.txt`.
- Only 3 OTF files are bundled (renamed to avoid spaces in asset paths):
  `fa-solid-900.otf`, `fa-regular-400.otf`, `fa-brands-400.otf`.
  SVGs and metadata from the desktop bundle are intentionally not shipped.

## How it works

- Flet resolves `page.fonts` values against `assets_dir`
  (`termoclub/assets/`, passed as an absolute path from `termoclub/main.py`),
  and supports `.otf`. The OTFs carry the standard PUA codepoints
  (verified: U+F120 `terminal` present in Solid), so glyphs render through
  plain `ft.Text` — no ligature support needed.
- `termoclub/app/ui/FontAwesome.py` (class `FontAwesome`) is the single
  access point: `FONTS` maps families to asset paths, `register(page)`
  adds them to `page.fonts` at startup, and `icon(name, size, color)`
  returns an `ft.Text` with the glyph. The curated `_ICONS` subset keeps
  codepoints next to the code; extend it from the bundle `metadata/icons.json`
  when new icons are needed.

## Limitation

- `ft.Icon` renders Material icons only and cannot use these fonts.
  Always use `FontAwesome.icon(...)` for Font Awesome glyphs.
