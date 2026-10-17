"""Live feature table and non-destructive sequence highlights."""

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QHBoxLayout, QLabel, QScrollArea, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from sequence_features import detect_features


class HoverHighlighter(QSyntaxHighlighter):
    """Apply temporary underlines during text layout, without editing document contents."""

    def __init__(self, document):
        super().__init__(document)
        self.ranges = []

    def highlightBlock(self, text):
        block_start = self.currentBlock().position()
        block_end = block_start + self.currentBlock().length() - 1
        style = QTextCharFormat()
        style.setFontUnderline(True)
        for start, end in self.ranges:
            left, right = max(start, block_start), min(end, block_end)
            if left < right:
                self.setFormat(left - block_start, right - left, style)


class SequenceFeatureView(QWidget):
    features_changed = Signal()

    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.hovered_feature = None
        self.hover_highlighter = HoverHighlighter(editor.document())
        layout = QVBoxLayout(self)
        description = QLabel(
            "Potential features from sequence matches. Positions are 1-based, inclusive, "
            "and exclude whitespace and *. Protease ranges show recognition motifs, not cleavage bonds. "
            "Tags require ≥95% identity across the full reference (substitutions only). "
            "Identity is similarity, not confidence. Select a row to locate it in the sequence."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.status = QLabel()
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Feature", "Type", "Start", "End", "Length", "Sequence", "Identity", "Substitutions"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.table.itemSelectionChanged.connect(self.locate)
        editor.textChanged.connect(self.refresh)
        self.refresh()
        editor.selectionChanged.connect(self.update_highlights)

    def refresh(self):
        raw = self.editor.toPlainText()
        self.features = detect_features(raw)
        # QTextCursor uses UTF-16 offsets; keep highlights aligned in pasted text.
        self.positions = []
        offset = 0
        for char in raw:
            width = len(char.encode("utf-16-le")) // 2
            if not char.isspace() and char != "*":
                self.positions.extend([(offset, offset + width)] * len(char.upper()))
            offset += width
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.features))
        for row, feature in enumerate(self.features):
            values = (feature.name, feature.kind, feature.start, feature.end,
                      feature.end - feature.start + 1, feature.sequence,
                      f"{feature.identity:.1f}%", str(feature.substitutions))
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setBackground(QColor(feature.color))
                item.setForeground(QColor("#202020"))
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        self.hovered_feature = None
        self.update_highlights()
        self.features_changed.emit()
        self.status.setText(f"{len(self.features)} potential feature(s) found." if self.features
                            else "No supported tag or protease motifs found.")

    def hover_feature(self, name):
        self.hovered_feature = name
        self.update_highlights()

    def update_highlights(self):
        highlights = []
        for feature in self.features:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = self.feature_cursor(feature)
            selection.format.setBackground(QColor(feature.color))
            selection.format.setForeground(QColor("#202020"))
            highlights.append(selection)
        self.editor.setExtraSelections(highlights)
        # Underlines emphasize hover/selection without changing glyph spacing.
        self.hover_highlighter.ranges = [
            (self.positions[feature.start - 1][0], self.positions[feature.end - 1][1])
            for feature in self.features if feature.name == self.hovered_feature
        ]
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            self.hover_highlighter.ranges.append((cursor.selectionStart(), cursor.selectionEnd()))
        with QSignalBlocker(self.editor):
            self.hover_highlighter.rehighlight()

    def feature_cursor(self, feature):
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(self.positions[feature.start - 1][0])
        cursor.setPosition(self.positions[feature.end - 1][1], QTextCursor.MoveMode.KeepAnchor)
        return cursor

    def locate(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.features):
            self.editor.setTextCursor(self.feature_cursor(self.features[row]))
            self.editor.ensureCursorVisible()


class LegendItem(QLabel):
    def __init__(self, feature, view):
        super().__init__(feature.name)
        self.feature_name = feature.name
        self.view = view
        self.setStyleSheet(f"background-color: {feature.color}; color: #202020; padding: 2px 4px; ")
        self.setToolTip(f"{feature.name} — {feature.kind}. Hover to underline matching sequence.")

    def enterEvent(self, event):
        self.view.hover_feature(self.feature_name)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.view.hover_feature(None)
        super().leaveEvent(event)

    def hideEvent(self, event):
        if self.view.hovered_feature == self.feature_name:
            self.view.hover_feature(None)
        super().hideEvent(event)


class FeatureLegend(QScrollArea):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.setObjectName("sequenceLegend")
        self.setAccessibleName("Sequence feature color legend")
        self.setWidgetResizable(True)
        self.setFixedWidth(160)
        self.setMinimumHeight(150)
        content = QWidget()
        self.entries = QVBoxLayout(content)
        self.entries.setContentsMargins(6, 4, 6, 4)
        self.entries.setSpacing(3)
        self.setWidget(content)
        view.features_changed.connect(self.refresh)
        self.refresh()

    def refresh(self):
        while self.entries.count():
            item = self.entries.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.entries.addWidget(QLabel("<b>Feature legend</b>"))
        seen = set()
        for feature in self.view.features:
            if feature.name not in seen:
                self.entries.addWidget(LegendItem(feature, self.view))
                seen.add(feature.name)
        if not seen:
            empty = QLabel("No features detected")
            empty.setWordWrap(True)
            self.entries.addWidget(empty)
        self.entries.addStretch()


def sequence_with_legend(editor: QTextEdit, view: SequenceFeatureView) -> QWidget:
    """Place the detected-feature color key beside either sequence editor."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(editor, 1)
    layout.addWidget(FeatureLegend(view))
    return container
