"""Shared test setup.

mtkclient's ``Library/utils.py`` runs, at import time:

    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

guarded by ``except (io.UnsupportedOperation, AttributeError)``. Run against
pytest's capture object that call succeeds, detaching pytest's own buffer, and
the entire run dies with "underlying buffer has been detached" before a single
test reports a result.

So the tee goes in first -- its ``detach()`` raises ``UnsupportedOperation``,
which that guard swallows -- and then mtkclient is imported here, deliberately,
while the tee is the thing holding stdout. Once it has been imported the
module-level code cannot run again, so later capture swaps are safe.

This mirrors the load-bearing import order in ``mtk_gui/app.py``.
"""
import os

# Tests must never try to open a real window; this also lets the suite run in
# CI and over SSH. Set before anything imports Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mtk_gui.backend.stdio_bridge import install_windowed_streams

install_windowed_streams()

import mtkclient.Library.utils  # noqa: E402,F401  (import for its side effect)
