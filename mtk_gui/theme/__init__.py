"""Theme management."""
from mtk_gui.theme.colors import Colors


def load_stylesheet(theme_name: str) -> str:
    """Load a QSS stylesheet by theme name."""
    import os
    qss_path = os.path.join(os.path.dirname(__file__), f"{theme_name}.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r") as f:
            return f.read()
    return ""
