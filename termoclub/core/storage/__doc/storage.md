# User Data Storage (`core/storage`)

## Decision

All file handling (app settings, temp data, user up/downloads) goes through
a single wrapper — `FileManager` (`termoclub/core/storage/FileManager.py`).
No other class touches the filesystem for user data directly. User data
lives in the user profile (Linux: `~/.termoclub`).

## Layout

- `StorageBackend.py` — abstract backend: create / read / modify / copy /
  delete / exists. Archive, remote, and other-location operations are
  concrete stubs raising `NotImplementedError` until implemented.
- `backends/ProfileBackend.py` — local profile implementation. All relative
  paths are resolved strictly inside the backend root; escaping the root
  raises `ValueError`. New locations = new backend subclass, no UI changes.
- `FileManager.py` — the only entry point for the rest of the app.
  Delegates everything to the active backend (default: profile), so future
  backends plug in without touching callers. Important calls are logged
  through the centralized logger.

## Interface summary

- Create: `create_file(path, content)`, `create_dir(path)`
- Read/modify: `read_text`, `read_bytes`, `write_text`, `write_bytes`
- Copy/delete: `copy(src, dst)` (files and dirs), `delete(path)` (recursive),
  `exists(path)`
- Archives (stubs): `archive(src, dst)`, `extract(archive, dst)`
- Remote/other locations (stubs): `download(url, dst)`, `upload(src, url)`
