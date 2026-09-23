"""Dialog for creating and editing protein library entries."""

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

from protein import Protein, normalise_sequence, protein_properties


class ProteinDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        protein: Protein | None = None,
        default_group: str = "My proteins",
    ):
        super().__init__(parent)
        self.setWindowTitle("Add protein" if protein is None else "Edit protein")
        self.setMinimumWidth(480)
        self.original_color = protein.color if protein else ""
        self.original_absorbance_280 = protein.absorbance_280 if protein else None
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        details_tab = QWidget()
        form = QFormLayout(details_tab)
        self.name = QLineEdit(protein.name if protein else "")
        self.group = QLineEdit(protein.group if protein else default_group)
        self.sequence = QTextEdit(protein.sequence if protein else "")
        self.sequence.setPlaceholderText("Paste a one-letter amino-acid sequence, e.g. MKTIIAL...")
        self.sequence.setFixedHeight(150)
        form.addRow("Protein name", self.name)
        form.addRow("Folder", self.group)
        form.addRow("Sequence", self.sequence)
        tabs.addTab(details_tab, "Details")

        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        self.notes = QTextEdit(protein.notes if protein else "")
        self.notes.setPlaceholderText("Add experimental details, references, observations, or other notes…")
        notes_layout.addWidget(self.notes)
        tabs.addTab(notes_tab, "Notes")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> Protein:
        return Protein(
            name=self.name.text().strip() or "Untitled protein",
            sequence=normalise_sequence(self.sequence.toPlainText()),
            group=self.group.text().strip() or "My proteins",
            color=self.original_color,
            notes=self.notes.toPlainText().strip(),
            absorbance_280=self.original_absorbance_280,
        )

    def accept(self) -> None:
        try:
            protein_properties(self.value().sequence)
        except ValueError as exc:
            QMessageBox.warning(self, "Check sequence", str(exc))
            return
        super().accept()
