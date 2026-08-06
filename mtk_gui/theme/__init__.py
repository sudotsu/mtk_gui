"""Theme management."""
from mtk_gui.theme.colors import Colors


def load_stylesheet(theme_name: str) -> str:
    """
    Load the QSS stylesheet associated with a theme name.
    
    Parameters:
        theme_name (str): Name of the theme stylesheet to load.
    
    Returns:
        str: The stylesheet contents, or an empty string if the file is unavailable.
    """
    import os
    qss_path = os.path.join(os.path.dirname(__file__), f"{theme_name}.qss")
    if os.path.isfile(qss_path):
        with open(qss_path, "r") as f:
            return f.read()
    return ""
