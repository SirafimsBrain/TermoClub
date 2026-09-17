# Проверка соответствия API после обновления зависимостей (2026-09-17)

Дата: 2026-09-17. Окружение: Linux, Python 3.13.
Установлено фактически (`pip show`):
- `flet 1.0.0` (было `0.86.5`)
- `smartcli-toolkit 0.3.2` (было `0.2.3`)
- `pyte 0.8.2` (без изменений)
- попутно: `flet-terminal` (зависит от `flet 1.0.0`, в коде не используется).

Проверка: статический разбор всех `ft.*` / `page.*` / `pyte.*` /
`smartcli_core.*` в `termoclub/`, сверка сигнатур с установленным пакетом
(`inspect.signature`, `__dataclass_fields__`, исходники классов), запуск
`pytest` (247 passed), миграционная документация Flet
(`flet.dev/docs/updates/migrate-to-1-0/`, issue `flet-dev/flet#5238`).

Итог: `pytest` зелёный (247 passed), но часть кода опирается на API,
удалённое/помеченное устаревшим в Flet 1.0, или на недокументированные
детали `smartcli_core`. Приоритет: **P0** — сломано в рантайме,
**P1** — deprecated/хрупкое, **P2** — стилистическое.

---

## 1. Flet 1.0.0 (было 0.86.5)

### P0-1. `app/ui/components.py::show_snack` — `page.snack_bar` удалён
Файл: `termoclub/app/ui/components.py:10-14`:
```python
page.snack_bar = ft.SnackBar(...)
page.snack_bar.open = True
page.update()
```
В `flet 1.0.0` у `ft.Page` нет поля `snack_bar` (проверено:
`'snack_bar' not in dir(ft.Page)`, нет в `Page.__dataclass_fields__`).
Присвоение упадёт (`AttributeError`/`ValueError` — контролы 1.0 это
dataclass'ы со строгими полями), т.е. **любой вызов `show_snack()` — пути
ошибок `_open_terminal`, `_open_settings`, `SettingsPanel` — роняет
приложение**, а не показывает уведомление. `ft.SnackBar` существует и
является `DialogControl`, правильный путь в 1.0 —
`page.show_dialog(ft.SnackBar(...))` (гайд: `page.open(dialog)` →
`page.show_dialog(dialog)`). Используется в: `termoclub/main.py:129,145,244`,
`termoclub/app/ui/settings/SettingsPanel.py:198`.
Тестами не покрыт, поэтому `pytest` зелёный.

### P0-2. `page.dialogs` существует только в тестовых фейках
Файл: `termoclub/app/ui/settings/SettingsControls_test.py:217`:
```python
assert isinstance(control.page.dialogs[-1], ft.DatePicker)
```
У реального `ft.Page 1.0` атрибута `dialogs` нет (есть внутренний `_dialogs`,
публичного нет — проверено). Тест проходит только потому, что фейк
`FakePage` сам заводит `dialogs`/`show_dialog`. Прод не роняет, но тест
больше не проверяет реальный контракт `Page.show_dialog(DialogControl)`.

### P1-1. LinkOpener / PathPicker — ручная регистрация сервисов
Файлы: LinkOpener.py:60,72, PathPicker.py:76 (page.services.append).
В Flet 1.0 сервисы (Clipboard, UrlLauncher, FilePicker — наследники Service)
саморегистрируются при конструировании; гайд Step 4: ничего добавлять на
страницу не нужно. Явный append оставлен для совместимости, код работает,
но держит сервис на странице вечно и расходится с каноном 1.0
(file_picker = ft.FilePicker(); await file_picker.pick_files()).
Проект уже использует await-вариант без on_result (удалён в 1.0) — корректно.

### P1-2. SegmentedButton.selected — set вместо list[str]
Файл: ChoiceSettingControl.py:78,92,107 (selected=set(selected)).
В 1.0 поле объявлено selected: list[str] (дефолт list); breaking change из
flet-dev/flet#5238: selected List[str] instead of Optional[Set]. На 1.0.0 set
молча принимается (проверено), рантайм не падает, но нарушен контракт типов
и порядок set недетерминирован. Заменить на list(...) / sorted(...).

### P1-3. Позиционные ft.Padding(...) против keyword-only symmetric()
Файлы: WorkspaceTabBar.py:42 (Padding(8,4,4,4)), SessionCardList.py:59
(Padding(0,8,0,8)). Гайд и #5238 требуют именованные аргументы для
symmetric(). Позиционный конструктор на 1.0.0 работает (проверено),
остальные места уже используют only()/symmetric()/all() — эти два стоит
унифицировать. Работает, P1, не рантайм-баг.

### P1-4. TerminalView.INPUT_BORDER — наполовину мигрирован
Файл: TerminalView.py:57-61 (NoInputBorder() if hasattr else InputBorder.NONE).
На 1.0.0 обращение к InputBorder.NONE печатает DeprecationWarning (deprecated
since 1.0.0, removal in 1.3.0, use NoInputBorder()). Ветка hasattr выбирает
NoInputBorder(), но fallback для 0.86 можно удалить, оставив NoInputBorder().

### P2-1. page.window существует; ссылка на page.dart устарела
window — поле ft.Page, Window.close() существует (main.py:109 корректен),
page.width/height и PageResizeEvent.width/height на месте. Несоответствий нет.
P2: в докстрингах TerminalSession.py:22, TerminalView.py:25 осталась ссылка на

### P2-2. Явные control.update() / page.update() — избыточны, но безвредны
Гайд Step 5: Flet сам вызывает update() после каждого обработчика и main().
В проекте ~11 мест (WorkspaceTabBar.py:75, SessionCardList.py:79,
SystemStatuses.py:45, SettingsPanel.py:206, SettingControl.py:201,
CategoryList.py:131, WorkspaceStage.py:55, layout.py:106,225,
TerminalView.py:455, main.py:102). В 1.0 control.update() бросает, если
контрол ещё не на странице — проект это учитывает через _safe_update() с
except RuntimeError. Менять не требуется.

### Проверено и соответствует Flet 1.0 (менять не нужно)
- ft.run(main, view=AppView.FLET_APP, assets_dir=...) (main.py:372) — канон
  1.0 (ft.app(target=...) удалён, не используется).
- page.run_task(coro_fn) — сигнатура 1.0 (handler -> Awaitable) -> Future;
  проект передаёт корутинные функции — корректно.
- KeyboardEvent.{key,shift,ctrl,alt,meta} — поля на месте.
- Clipboard().set()/get(), UrlLauncher().launch_url() — async, проект зовёт
  через page.run_task / await — корректно.
- TextField(text_size, read_only, on_submit, on_blur), Row/Column(tight),
  IconButton(icon_size), Dropdown(on_select), DropdownOption(key, text),
  Checkbox/Switch/Slider(on_change), TextStyle(height), Text(no_wrap),
  Stack(fit), Icons.CALENDAR_MONTH/SCHEDULE, ScrollMode.AUTO, ThemeMode,
  Theme.color_scheme_seed (SettingsApplier.py:130) — всё существует в 1.0.
  Нижние регистры ft.colors/ft.icons/ft.padding не используются — по гайду.

---

## 2. smartcli-toolkit 0.3.2 (было 0.2.3)

### P1-5. Завязка на внутренние детали ScreenModel
Файл: SmartCLIScreen.py:73,86-88 (self._model.display,
self._model.screen.buffer[y]). display/cursor/cursor_hidden/cols/rows/text/
resize — публичные и стабильные. Но row() лезет в screen.buffer[y] — _Screen
(наследник pyte.Screen) и buffer: defaultdict — внутренняя деталь
screen_model.py. Отказ от row_cells() осознан (CellAttrs по-прежнему только
data/fg/bg/bold/reverse — проверено CellAttrs._fields; italics/underscore/
strikethrough/blink теряются + лишние NamedTuple на кадр). Работает, но
хрупко к рефакторингу апстрима. P1, не блокер. PtySession.pump(max_bytes)
получил опциональный параметр — вызов pump() без аргументов
(SmartCLIPtyBridge.py:149) эквивалентен прежнему поведению. send_text,
resize, is_alive, close, start(cmd), model — сигнатуры на месте.

### P2-3. Неиспользуемые новые возможности 0.3.2 (не баги)
content_hash()/visual_hash(), wait_ready/wait_for/wait_stable/wait_change/,
snapshot(), KEY_MAP, send_keys/send_line, close() -> dict — проект не
использует и не обязан. terminate() игнорирует dict от close() — корректно
(идемпотентен). Собственный ScreenModel.py (pyte-обёртка, get_text()
возвращает list) никем не импортируется — мёртвый код, кандидат на удаление
отдельно, к обновлению отношения не имеет.

---

## 3. pyte 0.8.2 (без изменений)

Несоответствий нет: HistoryScreen(columns, lines, history=...),
Stream.feed(str), ByteStream.feed(bytes), Screen.resize(lines, columns)
(порядок lines, columns!) — проект вызывает корректно (PyteScreen.py:28-29,
63; ScreenModel.py:31-32,91). Утверждение про потерю italics/underscore/
strikethrough в CellAttrs подтверждено.

---

## 4. Что сделать (по приоритету)

1. P0-1: show_snack() на page.show_dialog(ft.SnackBar(...)).
2. P0-2: SettingsControls_test.py:217 — проверять вызов show_dialog.
3. P1-1: убрать page.services.append в LinkOpener/PathPicker.
4. P1-2: selected=set(...) -> selected=list(...) в ChoiceSettingControl.
5. P1-3: Padding(8,4,4,4) -> Padding.only()/symmetric() с именами (2 места).
6. P1-4: INPUT_BORDER = ft.NoInputBorder(), удалить fallback 0.86.
7. P1-5: зафиксировать контракт SmartCLIScreen.row() (пин 0.3.2 либо
   fallback на row_cells()).

Ничего из списка здесь не исправлялось — только диагностика. Все 247 тестов
проходят, т.к. P0-пути (show_snack) тестами не покрыты.

