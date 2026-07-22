"""Application entry point for Protein Param Pro.

Run with: ``.venv/bin/python src/main.py``.
"""

import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from main_window import APP_ICON_PATH, MainWindow
from styles import STYLE


def main() -> int:
    """Create and run the Qt application."""
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Arial", 11))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
