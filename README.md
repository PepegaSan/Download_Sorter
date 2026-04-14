# Download Sorter

Desktop app (Python) that watches a folder and sorts incoming files using configurable rules: match by file extension, file name, or (on Windows) source URL from the `Zone.Identifier` alternate data stream. Built with **customtkinter** and **watchdog**.

## Features

- **Watch folder** — non-recursive monitoring; on Windows uses a polling observer for reliability.
- **Rules** — ordered list; **first matching rule wins**. Each rule can have multiple criteria combined with **AND**; each criterion can list multiple values combined with **OR**.
- **Actions** — move (with unique target name on collision), delete, or ignore.
- **Stable file wait** — delays and size polling so downloads are finished before moving.
- **Scan folder now** — enqueue existing files (watchdog only sees new changes).
- **Export / import rules** — JSON backup.
- **UI languages** — English and German (stored in `config.json` as `ui_language`: `"en"` or `"de"`).

## Requirements

- Python 3.10+ recommended
- Windows, macOS, or Linux (source-URL matching is Windows-specific)

## Install

```bash
pip install -r requirements.txt
```

Or use `install.bat` on Windows.

## Run

```bash
python main.py
```

Or `start_gui.bat` on Windows.

On first run, copy `config.json.example` to `config.json` and set `watch_folder` and `rules`, or configure everything in the UI.

## Configuration

- **`config.json`** — lives next to `main.py`. Contains `watch_folder`, timing options, `ui_language`, and `rules`.
- **`download_sorter.log`** — optional log file for troubleshooting (created when the app runs).

Do not commit your real `config.json` if it contains personal paths; use `config.json.example` as a template.

## Rule JSON shape

Rules are stored as in the app export format; each rule has `criteria` (list of objects with `if_type`, `condition`, `values`), `action` (`move` | `delete` | `ignore`), and `target_folder` for `move`.

## License

Use and modify as needed for your own projects.
