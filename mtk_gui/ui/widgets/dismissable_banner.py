"""Dismissable banner widget — colored warning/info message with persistent close."""
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton


_STYLES = {
    "danger": {
        "background": "#440000",
        "color": "#ff4444",
        "border": "#cc4444",
    },
    "warning": {
        "background": "#442200",
        "color": "#ffaa44",
        "border": "#cc8844",
    },
}


class DismissableBanner(QWidget):
    """A colored banner with a close button that remembers dismissal via QSettings.

    Parameters
    ----------
    message : str
        Text to display.
    banner_type : str
        ``"warning"`` or ``"danger"`` — selects the color scheme.
    settings_key : str
        QSettings key used to persist the dismissed state.
    parent : QWidget | None
        Parent widget.
    """

    def __init__(
        self,
        message: str,
        banner_type: str = "warning",
        settings_key: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._settings_key = settings_key

        # Hide if previously dismissed
        if settings_key:
            settings = QSettings()
            if settings.value(settings_key, False, type=bool):
                self.setVisible(False)
                return

        style = _STYLES.get(banner_type, _STYLES["warning"])

        self.setStyleSheet(
            f"background-color: {style['background']}; "
            f"border: 1px solid {style['border']}; "
            f"border-radius: 3px;"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {style['color']}; font-weight: bold; "
            "border: none; background: transparent;"
        )
        layout.addWidget(label, 1)

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(self.cursor())
        close_btn.setStyleSheet(
            f"color: {style['color']}; background: transparent; "
            "border: none; font-weight: bold; font-size: 14px;"
        )
        close_btn.clicked.connect(self._dismiss)
        layout.addWidget(close_btn)

    def _dismiss(self):
        self.setVisible(False)
        if self._settings_key:
            settings = QSettings()
            settings.setValue(self._settings_key, True)
