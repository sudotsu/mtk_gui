# mtk_gui hardening — handoff state

Live working state for the multi-chunk hardening effort. Updated as work
happens, not at the end of a session. If you are a fresh context: read this,
then `docs/audit-2026-10-26.md`, then the plan at
`~/.claude/plans/instead-can-you-just-robust-koala.md`.

**Last updated:** 2026-10-26, during Chunk 2 prep.

---

## Why this effort exists

The app segfaulted on exit on 2026-10-26. The owner asked for a whole-codebase
audit rather than a point fix. The audit found ~60 defects; the exit crash is
the least dangerous of them. Target quality is public-release, because the
owner's judgment is that MTK tooling is weak enough that this project could
matter to other people if it earns it.

**Owner's safety stance (do not re-litigate):** no babying. The warning banners
stay; the typed-`YES` gauntlet goes. One acknowledgment, then plain Yes/No
dialogs that state concretely what is about to happen. Irreversible means
irreversible.

---

## Chunk status

| Chunk | Scope | Branch | State |
|---|---|---|---|
| 1 | Phase 0 — observability, diagnostics, crash mitigation, packaging blockers | `feat/phase0-observability` | **Committed `b90aaaf`. Not pushed.** |
| 2 | Phase 1 — worker substrate, `operation.py`, typed errors | not started | next |
| 3 | Phase 2 — destructive-path correctness | not started | |
| 4 | Phase 3a — `validation.py`, `safety.py` + tests | not started | |
| 5 | Phase 3b — `BaseTab`, confirmation redesign | not started | |
| 6 | Phase 4 — remaining tests, ruff, CI | not started | |

---

## Chunk 1 — what landed, and why it differs from the plan

The plan said "attach `LogSignalHandler` to the mtkclient/root loggers."
**That would not have worked**, and the reason matters for anyone touching
logging here:

mtkclient's `LogBase` metaclass calls `logging.config.dictConfig()` at
*class-definition time*, with a handler bound to `ext://sys.stdout` as it is at
that instant. Every new mtkclient class definition re-runs it and replaces
root's handlers. So a handler attached to root gets stomped, and the handler
mtkclient installs holds whatever stdout existed at first import.

The working fix is therefore to **install the stdout tee before mtkclient is
imported**, so mtkclient's own handler is bound to our stream. That makes the
import order in `mtk_gui/app.py` load-bearing — a future "tidy the imports"
commit would silently break it. `tests/test_import_order.py` pins it, and that
test was checked to genuinely fail under the old ordering rather than pass
vacuously.

`LogSignalHandler` is now attached to the `mtk_gui` logger tree only (not root),
so application failures such as a plugin that will not load become visible,
without double-logging everything mtkclient emits.

Also landed: rotating file log at `~/.local/state/mtk-gui/mtk-gui.log`,
`faulthandler`, an excepthook that shows the traceback, USB enumeration failures
promoted from DEBUG to WARNING with repeat suppression, `requires-python` 3.10,
`pyusb` declared, `.qss` package-data, `uv.lock` tracked, explicit ruff rule set.

### Verified vs. merely written

**Verified:** 10 tests pass; ruff clean on changed files; import-order invariant
holds and is falsifiable; 5 open/close cycles of the real `MainWindow` with no
coredump; log file written end to end.

**NOT verified — the crash fix.** The original segfault never reproduced, in two
minimal scripts or otherwise. Five clean cycles prove no regression; they do not
prove the fix, because cycles were clean before the change too. The
`PySide6>=6.11,<6.13` bound is reproducibility, not a known-good version. Real
proof is hardware use. `faulthandler` means a recurrence now leaves evidence.

### Known debt deliberately left

12 pre-existing `Optional[X]` annotations in `device_manager.py` now flag under
the new ruff config (UP045). Mechanical and safe on 3.10, but fixing them would
mix unrelated churn into the Chunk 1 diff. Do them in Chunk 6.

---

## Chunk 2 — next, in order

1. Rename `Worker.finished` → `result_ready` **first** (it shadows
   `QThread.finished` and is emitted before the thread exits). Doing the rename
   before anything else is deliberate: it touches every call site that step 3
   then collapses.
2. Fix `backend/worker.py:61-63` — stop discarding the exception and traceback
   when `is_cancelled` is set. Carry the error *with* cancellation context.
   This is the single highest-value fix in the codebase: it is why a failed
   erase currently reports nothing at all.
3. New `backend/operation.py` dispatch helper: connects `result_ready`, `error`
   **and `cancelled`**, starts the thread *after* connecting. Kills the
   `_start_op` race (17 sites), the unhandled-`cancelled` hang, ~20 duplicated
   wiring blocks and 28 silent `if not wrapper: return` no-ops.
4. Typed `MtkOperationError` from the wrapper, replacing ~40
   `except SystemExit: return False` sites, so a half-finished erase says why
   and how far.

Expect ~180–230 lines net removed.

---

## Standing constraints

- Work on branches; never commit to `main` without authorization in the current
  exchange. Never push without asking.
- No destructive operation is verified against the owner's phone without his
  explicit go-ahead at that moment. His MT65xx is attached in Preloader mode and
  mid-bootloader-unlock.
- Conventional Commits.
- Lint only files changed in the current task, never the whole codebase.
