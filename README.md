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

## Windows standalone `.exe` (PyInstaller)

1. Install runtime deps: `pip install -r requirements.txt`
2. Run `**build_exe.bat**` (installs PyInstaller from `requirements-build.txt`, then builds via `**Download_Sorter.spec**`).
3. Output: `**dist/Download_Sorter.exe**` — you can copy only that file; first run creates `**config.json**` and `**download_sorter.log**` in the **same folder as the `.exe`**.

Rebuild after code changes by running `build_exe.bat` again.

## Windows standalone `.exe` (Nuitka)

Run `**build_nuitka.bat**` (installs Nuitka, then builds a onefile GUI binary into `**nuitka-build/Download_Sorter.exe**`). The script uses **`--onefile-no-dll`**, which often avoids Windows Defender locking `main.dll` during post-processing (`Failed to add resources`). If the build still fails, add an exclusion for the project or output folder in Defender (see [Nuitka manual — Windows errors with resources](https://nuitka.net/doc/user-manual.html)).

## Configuration

- `**config.json**` — next to `main.py` when running from source; **next to the `.exe`** when using the frozen build.
- `**download_sorter.log**` — optional log file for troubleshooting (created when the app runs).

Do not commit your real `config.json` if it contains personal paths; use `config.json.example` as a template.

## Rule JSON shape

Rules are stored as in the app export format; each rule has `criteria` (list of objects with `if_type`, `condition`, `values`), `action` (`move` | `delete` | `ignore`), and `target_folder` for `move`.

## License

Use and modify as needed for your own projects.