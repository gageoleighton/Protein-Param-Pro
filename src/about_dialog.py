"""About dialog for Protein Param Pro."""

from __future__ import annotations

from html import escape
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from app_info import APP_CONTACT, APP_DESCRIPTION, APP_NAME, APP_VERSION, APP_WEBSITE

import sentry_sdk


class AboutDialog(QDialog):
    """Display application identity, version, and support information."""

    def __init__(self, icon_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setMinimumWidth(410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(QPixmap(icon_path).scaled(
            84, 84, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))
        layout.addWidget(icon)

        name = QLabel(APP_NAME)
        name.setObjectName("aboutName")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        description = QLabel(APP_DESCRIPTION)
        description.setObjectName("aboutDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)

        details = QFormLayout()
        details.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        details.addRow("Version", QLabel(APP_VERSION))
        details.addRow("Website", self.link_label(APP_WEBSITE, APP_WEBSITE))
        details.addRow("Contact", self.contact_label(APP_CONTACT))
        layout.addLayout(details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        sentry_sdk.capture_message("Protein Param Pro Sentry test")
        sentry_sdk.flush(timeout=2)

    @staticmethod
    def link_label(url: str, text: str) -> QLabel:
        """Create a label that opens an external URL in the user's browser."""
        label = QLabel(f'<a href="{escape(url, quote=True)}">{escape(text)}</a>')
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label

    @classmethod
    def contact_label(cls, contact: str) -> QLabel:
        """Render a ``Name <mailto:email>`` contact with only the email linked."""
        match = re.fullmatch(r"\s*(.*?)\s*<mailto:([^>]+)>\s*", contact)
        if not match:
            return cls.link_label(f"mailto:{contact}", contact)
        name, email = match.groups()
        label = QLabel(
            f'{escape(name)} &lt;<a href="mailto:{escape(email, quote=True)}">{escape(email)}</a>&gt;'
        )
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        return label
