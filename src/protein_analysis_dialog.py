"""Read-only dialog for detailed protein sequence analysis."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from protein import Protein, protein_properties


class ProteinAnalysisDialog(QDialog):
    """Show calculated properties and amino-acid composition for one protein."""

    def __init__(self, protein: Protein, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Sequence analysis — {protein.name}")
        self.resize(650, 610)
        props = protein_properties(protein.sequence)

        layout = QVBoxLayout(self)
        title = QLabel(protein.name)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        subtitle = QLabel(f"{protein.group}  ·  {props['length']} amino acids")
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(subtitle)

        summary = QFormLayout()
        summary.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.add_row(summary, "Molecular weight", f"{props['mw'] / 1000:.2f} kDa")
        self.add_row(summary, "Calculated pI", f"{props['pi']:.2f}")
        self.add_row(summary, "Aromaticity (F/W/Y)", f"{props['aromaticity'] * 100:.1f}%")
        self.add_row(summary, "GRAVY hydropathy", f"{props['gravy']:.2f}")
        self.add_row(summary, "Instability index", f"{props['instability_index']:.1f}")
        self.add_row(summary, "Extinction coefficient at 280 nm", f"{props['e280']:,} M⁻¹ cm⁻¹")
        self.add_row(summary, "Extinction coefficient at 214 nm (est.)", f"{props['e214']:,} M⁻¹ cm⁻¹")
        layout.addLayout(summary)

        composition_title = QLabel("Amino-acid composition")
        composition_title.setObjectName("dialogSectionTitle")
        layout.addWidget(composition_title)
        composition = QTableWidget(len(props["aa_counts"]), 3)
        composition.setHorizontalHeaderLabels(["Amino acid", "Count", "Percentage"])
        composition.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        composition.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        composition.verticalHeader().setVisible(False)
        composition.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, (amino_acid, count) in enumerate(props["aa_counts"].items()):
            values = (amino_acid, str(count), f"{props['aa_percentages'][amino_acid]:.1f}%")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                composition.setItem(row, column, item)
        layout.addWidget(composition, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def add_row(form: QFormLayout, label: str, value: str) -> None:
        value_label = QLabel(value)
        value_label.setObjectName("dialogMetricValue")
        form.addRow(label, value_label)
