# mtk_gui

PySide6 GUI over mtkclient. Primary target is now Linux (Omarchy/Arch); the
Windows PyInstaller build (`mtk-gui.spec`) is no longer maintained.

## Never

- Never unpin mtkclient casually. `mtk_wrapper.py` imports mtkclient internals
  (`Mtk`, `DaHandler`, `DAloader`, `MtkConfig`), not a public API. Bump the pin
  in `pyproject.toml` as its own change and retest connect on a real phone.
- Never change `pyproject.toml`'s mtkclient line back to plain `mtkclient`:
  mtkclient is not on PyPI, so installs fail with "no solution found".

## Run / verify

```bash
uv venv --python 3.13 && uv pip install -e . && uv run mtk-gui
QT_QPA_PLATFORM=offscreen timeout 10 .venv/bin/mtk-gui   # headless smoke test; exit 124 = still running = OK
```

Linux device access needs mtkclient's `Setup/Linux/52-mtk.rules` in
`/etc/udev/rules.d/` and the user in group `uucp` (Arch's serial group).

## Traps

- Worker and USB-poll signals are queued to the main thread; any slot that
  changes `DeviceState` must check the current state first, or a late signal
  undoes a user's Stop. `DeviceState.PRELOADER` auto-starts a connection.
- No test suite exists yet. Only a real phone in BROM/Preloader mode proves
  the connect path.
