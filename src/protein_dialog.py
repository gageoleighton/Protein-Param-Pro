"""Dialog for creating and editing protein library entries."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QTextEdit, QWidget

from protein import Protein, normalise_sequence, protein_properties


class ProteinDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, protein: Protein | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add protein" if protein is None else "Edit protein")
        self.setMinimumWidth(480)
        form = QFormLayout(self)
        self.name = QLineEdit(protein.name if protein else "")
        self.group = QLineEdit(protein.group if protein else "My proteins")
        self.sequence = QTextEdit(protein.sequence if protein else "")
        self.sequence.setPlaceholderText("Paste a one-letter amino-acid sequence, e.g. MKTIIAL...")
        self.sequence.setFixedHeight(150)
        form.addRow("Protein name", self.name)
        form.addRow("Folder", self.group)
        form.addRow("Sequence", self.sequence)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def value(self) -> Protein:
        return Protein(
            self.name.text().strip() or "Untitled protein",
            normalise_sequence(self.sequence.toPlainText()),
            self.group.text().strip() or "My proteins",
        )

    def accept(self) -> None:
        try:
            protein_properties(self.value().sequence)
        except ValueError as exc:
            QMessageBox.warning(self, "Check sequence", str(exc))
            return
        super().accept()
