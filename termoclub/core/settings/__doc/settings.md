# Settings (`core/settings`)

## Decision

Settings are opened as a regular workspace tab (through `WorkspaceManager`,
kind `settings`), not a modal or a separate window. The tab is a
two-column layout: chevrons (categories) on the left, the selected
category's settings on the right.

Settings live in `~/.termoclub/settings/*.json`; plugin settings live in
`~/.termoclub/plugins/<plugin>/values.json`. Everything is JSON with a
closed set of value types — no ad-hoc types in the UI.

## Layers

1. **Built-in schema** (`schema/*.json`) — defaults that ship with the app.
2. **User profile** (`~/.termoclub/settings`) — overrides built-ins.
3. **Unsaved edits** in the current session (dirty keys).

If the profile is missing or not writable, the store runs read-only: values
come from the built-in schema and writes raise `SettingsError`. The user
profile always wins over built-ins.

## Files

- `ValueType.py` — the fixed type list (`string`, `text`, `integer`,
  `number`, `boolean`, `date`, `time`, `datetime`, `color`, `choice`,
  `multi_choice`, `file`, `directory`, `image`, `link`). Extending the list
  happens here only.
- `LinkType.py`, `Choice.py` — link target kinds and choice options.
- `SettingSpec.py` — one setting: type, default, bounds, choices, link type,
  `applier` name, `requires_restart`, and so on. Built from JSON.
- `Category.py` — a group of settings (a chevron). Knows where its values go:
  the app settings dir or a plugin dir.
- `SettingsSchema.py` — ordered set of categories (app + plugins).
- `SchemaLoader.py` — reads built-in `schema/*.json` and
  `schema/plugins/*.json`.
- `ValueCodec.py` — coerces and validates values against a spec; converts
  to/from JSON (dates and colors are stored as strings).
- `SettingsStore.py` — **the mediator**. The only settings entry point for
  the app: read, write, validate, merge layers, search, reset, save. The GUI
  never touches `FileManager` directly.
- `PluginSettingsScanner.py` — scans `~/.termoclub/plugins/*`, reads
  `settings.json` + `manifest.json`, and feeds plugin categories and the
  `plugins.disabled_plugins` choices. The scanned folder is
  `plugins.plugin_directory` from the schema (default: the profile's
  `plugins/`); absolute paths are rejected because `FileManager` resolves
  only paths inside the profile.
- `PluginInfo.py` — scan result for one plugin (name, title, enabled,
  problems).
- `SettingsApplier.py` — applies changes to live targets: window theme, log
  level, active external terminal, and terminal tab appearance/refresh rate.

## Startup

`TermoClubApp._bootstrap` calls `apply_all()` and then `_scan_plugins()`,
which runs the same plugin discovery as the Rescan button when
`plugins.enable_plugins` and `plugins.auto_discover` are both on. Scanned
categories and values then survive the restart through the profile. Failures
are logged and never block startup.

## GUI layer

`app/ui/settings` renders settings and forwards user actions to
`SettingsStore` — it holds no values of its own.

- `SettingControl.py` — base row: title, description, editor, error text,
  reset. `commit()` validates through the store and shows errors.
- `TextSettingControl.py`, `NumberSettingControl.py`,
  `BooleanSettingControl.py`, `ChoiceSettingControl.py` (single choice plus
  multi choice), `ColorSettingControl.py`, `DateTimeSettingControl.py`,
  `PathSettingControl.py` (file/directory/image), `LinkSettingControl.py`.
- `SettingsControls.py` — factory: value type -> widget class; unknown types
  fall back to a text field.
- `SettingsDeps.py`, `PathPicker.py`, `LinkOpener.py` — page services
  (dialogs, clipboard, URL launching).
- `CategoryList.py` — left column of chevrons, marks changed categories and
  disabled plugins.
- `SettingsPanel.py` — right column: category header, rows, and actions
  (Save all, Reset category, Rescan plugins).

The workspace tab itself is `app/pages/settings.py` (`SettingsSession` +
`SettingsPage`), registered in `SessionFactory` under `settings`. The
`/settings` route and the `Settings` main-menu items only open or activate
that single tab; the menu items pass a category slug to jump straight to it.

## Applying changes

`SettingsApplier` subscribes to `SettingsStore.subscribe_changes`
(`listener(slug, key)`). Handlers are keyed by the `applier` name in the
schema, so a new setting only needs a name in JSON plus a method in the
applier. Failures are logged, never raised: a broken setting must not block
the rest. Terminal appearance is scoped to the category that owns it — a
session declares `appearance_category`, so editing the pyte tab never
rewrites smartcli tab colours.

The settings tab subscribes to `SettingsStore.subscribe` while open and
calls `unsubscribe` from `SettingsSession.cleanup`, so closing the tab does
not leave the closed screen reachable from the store.

## Runtime flow

1. The user opens the Settings tab (menu or `/settings`).
2. Chevrons appear on the left, built from the schema.
3. Selecting a category draws its settings on the right.
4. Edits go GUI control -> `SettingsStore` -> `~/.termoclub/settings` (or a
   plugin dir).
5. `SettingsApplier` applies the change to running terminals and the window.
