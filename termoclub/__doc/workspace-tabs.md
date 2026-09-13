# Workspace Tabs Plan (`core/sessions`, `app/workspace`)

## Goal

Tabbed sessions (internal terminal now; editor and RDP later) on the
workspace panel: a custom tab bar (`ft.Row` + buttons) and an `ft.Stack`
content host — no `ft.Tabs`. Python classes own logic, Flet controls
only render.

## Verified facts (Flet 0.86.5, Python 3.13)

- `flet-terminal` (PyPI, requires `flet>=0.85.3`, compatible with our
  `flet==0.86.5`) exposes a `Terminal` control (xterm.dart canvas,
  DataChannel streaming). It renders only: `write()`, `send_bytes()`,
  `set_on_bytes()`, `focus()`, `clear()`. The PTY/shell bridge is our code
  (`asyncio` + `pty` on Linux/macOS; Windows initially unsupported).
- `page.run_task(coro)` exists — used for PTY spawn and the read-pump;
  the returned `Future` is the cancellation handle.
- `ft.Stack` exists — session controls are mounted once and switched via
  `visible`, so xterm state survives tab switches (no rebuild on switch).
- Canvas lives in the `flet.canvas` submodule (`import flet.canvas as cv`),
  not `ft.Canvas`. Future custom renderers (e.g. a `pyte` grid painted as
  `cv.Text` shapes) are possible without native extensions.

## Rules compliance (AGENTS.md)

- `TerminalController` keeps its external-window contract untouched
  (`open_new_tab` stays mandatory); internal sessions get their own
  `WorkspaceItem` abstraction under `core/sessions`. The UI never imports
  concrete sessions — only the factory.
- One class per file, file named as the class; class nesting mirrors
  directories; first line of every `*.py` is the project-root path comment.
- All major session events go through the centralized logger.

## Module tree (to be created)

```text
termoclub/core/sessions/
  WorkspaceItem.py     # ABC: id/title/icon/status, get_content/on_focus/on_blur/cleanup
  SessionStatus.py     # Enum: CREATED/RUNNING/FOCUSED/CLOSED/ERROR
  SessionFactory.py    # kind -> class registry; create/register (mirrors terminal factory)
  terminal/
    TerminalSession.py # WorkspaceItem: owns PtyBridge + lazily built Terminal control
    PtyBridge.py       # asyncio PTY: spawn, write, read-pump, terminate
  editor/EditorSession.py  # stub placeholder content (infra testable before real impl)
  rdp/RdpSession.py        # stub placeholder content
termoclub/app/workspace/
  WorkspaceManager.py  # sessions dict, active_id, add/close/activate, subscribers, cap policy
termoclub/app/ui/
  WorkspaceTabBar.py   # Row of tab buttons + close + "+" (display only, callbacks out)
  WorkspaceStage.py    # ft.Stack host: mount once, toggle visible
```

## Key contracts

- `WorkspaceItem`: `get_content()` builds the control once (manager caches
  it); `on_focus()` (e.g. `terminal.focus()`); `on_blur()`; `cleanup()`
  cancels the pump `Future`, terminates the child, closes fds. Status
  transitions are logged.
- `SessionFactory.create(kind, **params)` (`cwd`, `env`, `cols`/`rows`);
  `register(kind, cls)` for future `pyte`/`smartcli-toolkit` renderers
  behind the same interface.
- `WorkspaceManager` holds no Flet state beyond item references; the view
  subscribes via `on_change`. Session cap (e.g. 10, oldest inactive closed
  first) guards memory with many xterm canvases.
- `PtyBridge`: `loop.add_reader` on the master fd (or executor reader);
  input `set_on_bytes -> os.write`; output pump `-> term.write()`.
  If `term.write()` proves unsafe off the UI loop, route writes via
  `call_soon_threadsafe` (spike must verify).
- `main.py` wiring only: workspace panel becomes
  `Column[WorkspaceTabBar, WorkspaceStage]`; route `/` shows it, `/logs`
  stays; first terminal session is created deferred via `run_task`.
  The existing external "New Tab/Window" menu (via `TerminalController`)
  is unchanged.

## Stages

0. Spike: install `flet-terminal` (pin version in `requirements.txt`),
   echo PTY, visibility switching in a `Stack`. Verdict on write safety.
1. `core/sessions` ABC + status + factory (+ registry tests).
2. `PtyBridge` + `TerminalSession` (Linux/macOS; Windows raises a clear error).
3. Manager + tab bar + stage + `main.py` wiring.
4. Tests: factory, manager state machine with stub items (no page needed),
   PTY echo against `cat`, tab-bar callbacks.
5. Editor/RDP placeholders as real registry entries.
Later (planned, not implemented): `flet.canvas` renderers (e.g. `pyte`
grid), session layout persistence via `FileManager` (`~/.termoclub`).

## Risks

- Third-party `flet-terminal` maturity (0.3.x, single maintainer): pin the
  version; the `WorkspaceItem` seam allows swapping renderers.
- Background-task control updates: verify in the spike, fallback above.
- `page.update()` granularity: refresh only bar/stage, never the whole page.

## Implementation notes (done)

- `flet-terminal==0.3.6` pinned in `requirements.txt`; PTY echo verified
  headless in `PtyBridge_test.py` (real `/bin/cat` roundtrip).
- `WorkspaceItem.on_terminated` attribute (set by the manager) closes the
  tab when the shell exits; `cleanup()` stays synchronous.
- `WorkspaceStage.prune()` drops controls of closed sessions; the wiring
  test caught its absence before the GUI did.
- `SessionCardData.from_item()` is the only UI touchpoint for sessions;
  `from_external()` stays reserved for the external-tracker stage.
- Reorder uses native `ReorderableListView` + `ReorderableDragHandle`
  (`grip-vertical` glyph); Flutter's post-removal `new_index` is corrected
  in `SessionCardList` before `manager.move()`.
- `main.py` holds only wiring: `manager.subscribe(_refresh_workspace)`,
  first terminal bootstrapped deferred via `page.run_task()`; the `Home`
  menu gained an `Internal Terminal` item, external actions unchanged.

## Implementation notes, round 2 (live GUI verified)

- "Unknown control: FletTerminal" in the stock client: `flet-terminal` is a
  Flutter extension — its Dart side only ships via `flet build` (needs the
  Flutter SDK, absent here). So the default `terminal` session is now
  pure-Python: `pyte` screen + `ft.Text` (bundled JetBrains Mono) +
  `PtyBridge`. `terminal-gpu` keeps the `flet-terminal` renderer for
  custom-built clients.
- Input rides `page.on_keyboard_event` (full modifiers, unlike
  `KeyboardListener` which exposes only the key name). `main.py` forwards
  keys to the active session only on route `/` (`key_to_bytes` mapping:
  printable, Enter/Backspace/Tab/Escape, arrows, F-keys, Ctrl+letter,
  Alt-prefix). Known v1 gap: no block cursor highlight.
- Screenshot-verified: tab bar, session card (`focused`), mono prompt,
  status bar. Key roundtrip (dispatcher -> `cat` -> display) is covered by
  `WorkspaceWiring_test.py`; the live GUI screenshot confirmed rendering.

## Addendum: session cards in the left panel

### Requirements

- The left collapsible panel drops its current demo content (action
  buttons stay available in the `Home` menu — no functionality is lost)
  and hosts one card per open workspace tab.
- A card is the future monitoring/management surface for a tab/session,
  where "session" also covers external terminals (e.g. an open Ghostty
  window) — not only in-workspace tabs.
- Cards appear/disappear as tabs open/close.
- The user can reorder cards by dragging a dedicated handle.

### Verified controls (Flet 0.86.5)

- `ft.ReorderableListView` with `on_reorder(old_index, new_index)`,
  `show_default_drag_handles=False`, optional `header`/`footer`.
- `ft.ReorderableDragHandle(content=...)` accepts custom content, so the
  handle is a Font Awesome `grip-vertical` glyph (U+F58E, verified in the
  bundle metadata) with a move cursor. Drag starts from the handle only.

### Design

- New UI classes (display only, callbacks out):
  `SessionCard.py` (card: header with kind icon + title + close, status
  row with state dot, reserved metrics/actions rows),
  `SessionCardList.py` (header with session count + the reorderable list).
- `SessionCardData.py`: plain descriptor
  (`session_id`, `title`, `kind`, `source`, `status`, `icon`) built via
  `SessionCardData.from_item(item)` — the UI never touches `WorkspaceItem`
  or future external handles directly.
- Single source of truth for order: `WorkspaceManager` (ordered sessions).
  `SessionCardList.sync()` is incremental (add/drop/update in place by
  `session_id`, user order preserved); `on_reorder` calls
  `manager.move(id, to_index)` (mind Flutter's post-removal `new_index`
  semantics); the tab bar renders the same order. Selecting a card calls
  `manager.activate(id)`.
- External sessions (Ghostty et al.) are a later stage: today's
  `TerminalController` returns only `Result` (no handles), so external
  windows are untrackable yet. The seam is ready —
  `SessionCardData.from_external(handle)` plus an `ExternalSessionTracker`
  (platform-specific discovery, open question: Ghostty CLI vs process
  polling) — rendered in the same list with a kind badge, without tabs.
  `kind`/`source` fields on the descriptor already carry this.
- Extend `FontAwesome._ICONS` with `grip-vertical` (F58E) and, for the
  external stage, `ghost` (F6E2) / `window-maximize` (F2D0).
- Tests: card builds from a descriptor, list sync add/remove, reorder
  event forwards correct indices, adapter maps a stub item.

## Implementation notes, round 3: ввод, кириллица и буфер обмена

### Симптомы

В терминале workspace (сессия `terminal`) печаталась только латиница, всегда
в верхнем регистре, кириллица не вводилась вообще, вставки из буфера обмена
не было.

### Причина

Ввод шёл одним каналом: `page.on_keyboard_event` -> `_on_page_key` ->
`TerminalSession.handle_key()` -> `key_to_bytes(event.key)`. Flet собирает
`KeyboardEvent.key` в Dart как `e.logicalKey.keyLabel`
(`flet/packages/flet/lib/src/controls/page.dart`, версия 0.86.5):

```dart
KeyboardEvent(key: k.keyLabel, isAltPressed: ..., isShiftPressed: ...)
```

а `LogicalKeyboardKey.keyLabel` во Flutter — это
`String.fromCharCode(keyId).toUpperCase()`: **логическая** (US-раскладка)
метка клавиши в верхнем регистре, игнорирующая раскладку и модификаторы.
Отсюда ровно оба симптома: раскладка не учитывается (вместо `ф` приходит
`A`), а регистр и Shift теряются (`shift+8` -> `8`, а не `*`). Вставка
не работала потому, что текста в этом событии нет вообще — ни `Ctrl+V`, ни
`Shift+Insert` не доходили до PTY.

`flet-terminal` (`terminal-gpu`) в этом не виноват: он ввод не обрабатывает,
символы отдаёт xterm.dart через свой IME, а наш Python только принимает байты
(`set_on_bytes`). Но и у него не была подключена вставка из буфера обмена.

### Решение

Ввод разделён на два канала:

- **Настоящие символы** (кириллица, регистр, AltGr, dead keys, вставка) идут
  из невидимого `ft.TextField` (`width=1, height=1, opacity=0`, autofocus) —
  Flutter пропускает его через IME и отдаёт настоящий текст. Поле всегда
  пустое: `_on_text_input()` переводит очередное значение в байты
  (`TextInputBridge`), очищает поле и пишет в PTY. Enter приходит в
  `on_submit` -> `\r`.
- **Служебные клавиши** (Backspace, стрелки, Tab, Esc, F-клавиши, `Ctrl+<буква>`)
  остаются на `page.on_keyboard_event`: для них логической метки достаточно.
  `handle_key()` отдаёт поле ввода то, что оно «съедает» само (печатаемые
  символы, пробел, Enter, `Ctrl+V`, `Shift+Insert`), иначе ввод дублировался бы.

Вставка из буфера: `Ctrl+V` / `Shift+Insert` обрабатывает само поле ввода
(Flutter вставляет текст в него, дальше работает тот же diff),
а `Ctrl+Shift+V` (и те же хоткеи, пока поле ещё не смонтировано) читает
`ft.Clipboard()` и пишет текст в PTY напрямую.

Сессия `terminal-gpu` получила `handle_key()` с теми же хоткеями
(на Python остаётся только вставка — клавиатуру обрабатывает xterm.dart через
`Terminal.paste()`), а также обработчик события `on_data`: без открытого
`DataChannel` flet-terminal отдаёт ввод строкой, и раньше эти байты терялись.

## Implementation notes, round 4: разбор pyte-терминала по классам

Один класс на файл, имя файла = имя класса — как в остальном проекте.
`TerminalSession` осталась только оркестрацией, всё остальное вынесено:

| Класс | Ответственность |
| --- | --- |
| `PtyBridge` | псевдотерминал: `start()`, `write()`, `pump()`, `resize()` (TIOCSWINSZ -> SIGWINCH шеллу), `terminate()` |
| `PyteScreen` | эмуляция VT100/ANSI: `feed_bytes()`/`feed()`, `row(y)`, `cursor`, `resize()`, `text()`; инкрементальный UTF-8-декодер (символ, разрезанный чанком, не ломается) |
| `TerminalPalette` | цвета pyte -> Flet: имена ANSI, `bright*`, 6-hex truecolor; `bold` подсвечивает базовый цвет до bright (сетка не съезжает, bold-начертания в бандле нет) |
| `TerminalView` | контролы Flet: `ft.Text` со спанами (цвет «прогона» ячеек, `italics`/`underline`/`strike`, инверсия под `reverse`), блочный курсор, скрытое поле ввода, `on_size_change` -> колонки/строки |
| `TextInputBridge` | diff значений скрытого поля (дописывание/Backspace/замена) в байты PTY |
| `TerminalKeymap` | служебные клавиши и `Ctrl+<буква>`/`Alt+<символ>` в байты (в т.ч. `Alt+Ctrl+C` -> `ESC 0x03`) |
| `TerminalSession` | сессия рабочей области: PTY + экран + вью, каналы ввода, буфер обмена, фокус |

Порядок отрисовки: `TerminalView.spans(screen)` строит по строке список
атрибутов ячеек, срезает пустой хвост (проверяя и символ, и атрибуты —
иначе срезались бы обычные буквы), склеивает соседние одинаковые ячейки в
один спан и добавляет блок курсора. Обновление — по троттлингу сессии
(`REFRESH_MIN_INTERVAL`, 20 Гц).

Размер терминала: `ft.Container.on_size_change` даёт пиксели контейнера,
`TerminalView` переводит их в колонки/строки (ширина знакоместа `0.6em`,
высота строки `1.25` кегля) и сообщает наружу; `TerminalSession.resize()`
меняет `PyteScreen` и PTY. Повторный тот же размер не рассылается.

Файлы round 3/4: `TextInputBridge.py`, `TerminalKeymap.py`, `PyteScreen.py`,
`TerminalPalette.py`, `TerminalView.py`, `TerminalSession.py`,
`FletTerminalSession.py` (+ `*_test.py` на каждый).

## Implementation notes, round 5: почему экран был пустым и два терминала во вкладках

### Симптомы

Открытая вкладка терминала не имела строки приглашения («вводить текст
некуда»), «заполнялась пробелами», показывала вертикальную полосу прокрутки
и не реагировала на ввод. Какой терминал открывается — было непонятно.

### Причины (три независимые)

**1. Скролл, который уезжал вниз.** Экран рисовался одним `ft.Text` внутри
`ft.ListView(auto_scroll=True)`. Высота контента считалась по кеглю
(13 x 1.25 = 16.25 px на строку), а Flutter брал её из метрик шрифта —
реальное значение больше. Сетка на 42 строки не влезала во вьюпорт, у
списка появлялась полоса прокрутки, а `auto_scroll` прижимал вид к низу:
пользователь видел ровно пустые строки под приглашением. Плюс
`WorkspaceStage` использовал умолчание Flet `StackFit.LOOSE`, поэтому
контейнер вкладки сжимался по содержимому: сетка «растила» контейнер,
контейнер увеличивал сетку — обратная связь до упора в максимум.

**2. Молчаливая потеря отрисовки.** `REFRESH_MIN_INTERVAL` (20 Гц)
отбрасывал чанк, попавший в окно троттлинга, и ничего не откладывал. Если
после этого шелл молчал (обычный случай — `bash` ждёт ввода), приглашение
оставалось только в буфере pyte, а на экране не появлялось никогда.
Плюс `get_content()` строил контрол с пустыми спанами и не рисовал уже
накопленный экран.

**3. Утечка на закрытии.** `PtyBridge.pump` читал PTY блокирующим
`os.read` в потоке executor'а. Такой поток не разбудить ни закрытием
master-fd, ни `request_stop()`, а интерактивный `bash` игнорирует SIGTERM —
каждая закрытая вкладка оставляла живой шелл и висящий поток (`asyncio.run`
ждал его на shutdown).

### Решение

- **Терминал — фиксированная сетка, а не список.** `ListView` убран совсем:
  скроллбек живёт в pyte, а видимая область обязана совпадать с контейнером.
  Всем спанам (включая переводы строк) задан `TextStyle.height`, поэтому
  число строк и высота отрисовки считаются по одной и той же формуле, а
  `clip_behavior=HARD_EDGE` не даёт содержимому вылезти.
- **Тугие ограничения.** `WorkspaceStage` переведён на `StackFit.EXPAND`,
  рабочая колонка — на `CrossAxisAlignment.STRETCH`; контейнер вкладки
  получает размер области, а не размер содержимого.
- **Ничего не теряется.** `get_content()` рисует текущий буфер сразу (если
  шелл ответил до монтирования), а троттлинг при отбросе планирует
  хвостовую отрисовку (`_flush_refresh`).
- **PTY освобождается.** Ожидание в потоке — короткими `select`
  (`READ_POLL_TIMEOUT`), поэтому pump отзывается на stop; `terminate()`
  шлёт SIGHUP группе процессов, затем SIGKILL, затем закрывает master-fd.
- **Размер не сбрасывается в минимум.** `on_size_change` с нулевым
  контейнером игнорируется (иначе PTY схлопывался до 20x4 и шелл
  перерисовывал приглашение в четыре строки).
- **Фокус и ввод.** Клик по терминалу возвращает фокус скрытому полю;
  если фокус всё же потерян, печатаемые клавиши обрабатывает диспетчер, а
  сессия тут же запрашивает фокус обратно — ввод не теряется никогда.
- **Буфер обмена.** `Ctrl+Shift+C` / `Ctrl+Insert` — копировать (видимую
  область экрана, `PyteScreen.visible_text()`); `Ctrl+V` / `Shift+Insert` /
  `Ctrl+Shift+V` — вставить. Обычный `Ctrl+C` остаётся SIGINT.

### Два терминала во вкладках

`SessionFactory` хранит оба рендерера, и они вызываются раздельно:

| Меню | kind | Заголовок вкладки | Клиент |
| --- | --- | --- | --- |
| Internal Terminal (pyte) | `terminal` | `Terminal (pyte)` | stock (`flet run`) |
| Internal Terminal (flet-terminal) | `terminal-gpu` | `Terminal (flet)` | собранный `flet build` |

`flet-terminal` — Flutter-расширение: в stock-клиенте выводится «Unknown
control: FletTerminal», и вкладка осталась бы пустой. Сессия сама это
замечает (`on_mount` не пришёл за `MOUNT_TIMEOUT`) и сообщает в статусную
панель и снекбаром.

У `terminal-gpu` размер PTY берётся из события `on_resize` самого контрола
(Dart присылает готовые `cols`/`rows` сетки xterm.dart), копирование —
`Ctrl+Shift+C`/`Ctrl+Insert` через `get_selection_async()`, вставка —
`Terminal.paste()` (буфер читает Dart).

### Ограничения (осознанные):

- Фокус скрытого поля — единственный путь для IME-символов, поэтому `Tab`
  возвращает фокус обратно, а `Alt+<буква>` не префиксуется `ESC` (иначе
  AltGr-символы вроде `@` ломались бы); `Ctrl+<буква>`, стрелки, `Esc`,
  `F-клавиши` и вставка работают штатно.
- История (`pyte.HistoryScreen`, 1000 строк) пока не отрисовывается: у
  скрытого скролла нет доступа к позиции, и вид «прилипал» бы к низу.
  Слот под скроллбек есть (`PyteScreen`, `history=`).
- Копирование в pyte-терминале берёт видимую область экрана целиком:
  мышиного выделения в `ft.Text` нет, а отдавать фокус тексту — значит
  потерять IME-ввод кириллицы.
- `terminal-gpu` нельзя проверить в этом окружении: Dart-расширение
  требует Flutter SDK (`flet build`), которого здесь нет. Логика сессии
  (размер из `on_resize`, вставка, копирование, сигнал об отсутствии
  контрола) покрыта тестами без GUI.
