"""Main application window and user-interface behavior."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QColorDialog, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
    QSplitter, QStatusBar, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from about_dialog import AboutDialog
from app_info import APP_NAME, APP_VERSION
from protein import Protein, protein_properties
from protein_analysis_dialog import ProteinAnalysisDialog
from protein_dialog import ProteinDialog
from storage import load_proteins, save_proteins


def bundled_asset_path(*parts: str) -> Path:
    """Locate an asset both from source and from a PyInstaller macOS bundle."""
    source_root = Path(__file__).resolve().parent.parent
    relative_path = Path(*parts)
    candidates = [source_root / relative_path]
    if getattr(sys, "frozen", False):
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        candidates.extend((
            bundle_root / relative_path,
            Path(sys.executable).resolve().parent.parent / "Resources" / relative_path,
        ))
    return next((path for path in candidates if path.is_file()), candidates[0])


APP_ICON_PATH = bundled_asset_path("icons", "favicon_io", "android-chrome-512x512.png")


class AnalysisCard(QFrame):
    """A detail card that opens the full analysis on double-click."""

    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()
        event.accept()


class AppIconLabel(QLabel):
    """Brand image that opens the About dialog on double-click."""

    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit()
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1220, 760)
        self.proteins = load_proteins()
        self.build_ui()
        self.refresh()

    def build_ui(self) -> None:
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.build_navigation())
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        heading = QLabel("Protein library")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        subheading = QLabel("Select one or more proteins to calculate molecular properties and concentration from absorbance.")
        subheading.setObjectName("subheading")
        layout.addWidget(subheading)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Protein", "Length", "Molecular weight", "ε 280", "ε 214 (est.)", "A280 concentration", "A214 concentration"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.update_detail)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_selected())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.build_detail_card())
        layout.addWidget(self.build_analysis_card())
        splitter.addWidget(content)
        splitter.setSizes([245, 975])
        self.setCentralWidget(splitter)

    def build_navigation(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("sidebar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 18, 12, 12)
        brand = QHBoxLayout()
        brand.setSpacing(9)
        logo = AppIconLabel()
        logo.setObjectName("brandImage")
        logo.setFixedSize(48, 48)
        logo.setToolTip("Double-click for app information")
        logo.setPixmap(QPixmap(str(APP_ICON_PATH)).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))
        logo.double_clicked.connect(self.show_about)
        brand.addWidget(logo)
        title = QLabel("PROTEIN PARAM PRO")
        title.setObjectName("brand")
        brand.addWidget(title)
        brand.addStretch(1)
        layout.addLayout(brand)
        button = QPushButton("+  New protein")
        button.clicked.connect(self.add_protein)
        layout.addWidget(button)
        label = QLabel("SEQUENCE FOLDERS")
        label.setObjectName("navlabel")
        layout.addWidget(label)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self.filter_folder)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        layout.addWidget(self.tree, 1)
        layout.addWidget(QLabel("All data stays on this computer."))
        return panel

    def show_about(self) -> None:
        AboutDialog(str(APP_ICON_PATH), self).exec()

    def build_detail_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("detail")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        self.detail_label = QLabel("Select a protein to calculate concentration.")
        self.detail_label.setMinimumWidth(220)
        layout.addWidget(self.detail_label)
        layout.addWidget(QLabel("Absorbance"))
        self.absorbance = QLineEdit()
        self.absorbance.setPlaceholderText("e.g. 0.85")
        self.absorbance.setMaximumWidth(105)
        self.absorbance.textChanged.connect(self.update_detail)
        layout.addWidget(self.absorbance)
        self.wavelength = QComboBox()
        self.wavelength.addItems(["A280", "A214"])
        self.wavelength.currentTextChanged.connect(self.update_detail)
        layout.addWidget(self.wavelength)
        self.concentration = QLabel("—")
        self.concentration.setObjectName("concentration")
        layout.addWidget(self.concentration, 1)
        return card

    def build_analysis_card(self) -> QFrame:
        """Build the single-protein physicochemical analysis display."""
        card = AnalysisCard()
        card.setObjectName("analysis")
        card.setToolTip("Double-click to open the full sequence analysis")
        card.double_clicked.connect(self.show_selected_analysis)
        self.analysis_card = card
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(7)

        heading = QLabel("Sequence analysis")
        heading.setObjectName("analysisHeading")
        heading.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(heading)

        metrics = QHBoxLayout()
        metrics.setSpacing(26)
        self.pi_value = self.add_analysis_metric(metrics, "Calculated pI")
        self.aromaticity_value = self.add_analysis_metric(metrics, "Aromaticity (F/W/Y)")
        self.gravy_value = self.add_analysis_metric(metrics, "GRAVY hydropathy")
        self.instability_value = self.add_analysis_metric(metrics, "Instability index")
        metrics.addStretch(1)
        layout.addLayout(metrics)

        self.composition_label = QLabel("Select one protein to view amino-acid composition.")
        self.composition_label.setObjectName("composition")
        self.composition_label.setWordWrap(True)
        self.composition_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.composition_label)
        return card

    @staticmethod
    def add_analysis_metric(layout: QHBoxLayout, title: str) -> QLabel:
        metric = QWidget()
        metric.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        metric_layout = QVBoxLayout(metric)
        metric_layout.setContentsMargins(0, 0, 0, 0)
        metric_layout.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("analysisMetricLabel")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        value = QLabel("—")
        value.setObjectName("analysisValue")
        value.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        metric_layout.addWidget(label)
        metric_layout.addWidget(value)
        layout.addWidget(metric)
        return value

    def save(self) -> None:
        save_proteins(self.proteins)

    def selected_indices(self) -> list[int]:
        rows = self.table.selectionModel().selectedRows()
        return sorted(self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole) for row in rows)

    def selected_index(self) -> int | None:
        indices = self.selected_indices()
        return indices[0] if len(indices) == 1 else None

    def add_protein(self) -> None:
        dialog = ProteinDialog(self)
        if dialog.exec():
            self.proteins.append(dialog.value())
            self.save()
            self.refresh()
            self.statusBar().showMessage("Protein saved", 3000)

    def edit_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            if self.selected_indices():
                self.statusBar().showMessage("Double-click one protein at a time to edit it", 3000)
            return
        dialog = ProteinDialog(self, self.proteins[index])
        if dialog.exec():
            self.proteins[index] = dialog.value()
            self.save()
            self.refresh()

    def delete_selected(self) -> None:
        indices = self.selected_indices()
        if indices:
            self.delete_proteins(indices)

    def delete_protein(self, index: int) -> None:
        self.delete_proteins([index])

    def delete_proteins(self, indices: list[int]) -> None:
        names = ", ".join(self.proteins[index].name for index in indices[:3])
        suffix = "…" if len(indices) > 3 else ""
        prompt = f"Delete {len(indices)} proteins ({names}{suffix})?" if len(indices) > 1 else f"Delete {names}?"
        if QMessageBox.question(self, "Delete protein", prompt) == QMessageBox.StandardButton.Yes:
            for index in sorted(indices, reverse=True):
                self.proteins.pop(index)
            self.save()
            self.refresh()
            self.statusBar().showMessage(f"Deleted {len(indices)} protein(s)", 3000)

    def filter_folder(self, item: QTreeWidgetItem) -> None:
        folder = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(folder, tuple):
            kind, value = folder
            if kind == "protein":
                self.select_protein(value)
            else:
                self.refresh(value if kind == "folder" else None)

    def select_protein(self, index: int) -> None:
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == index:
                self.table.selectionModel().select(
                    self.table.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
                return

    def show_table_context_menu(self, position) -> None:
        row = self.table.rowAt(position.y())
        if row >= 0:
            if not self.table.selectionModel().isRowSelected(row, self.table.rootIndex()):
                self.table.selectRow(row)
            index = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.show_protein_context_menu(self.table.viewport().mapToGlobal(position), index)

    def show_tree_context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        payload = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if isinstance(payload, tuple) and payload[0] == "protein":
            self.show_protein_context_menu(self.tree.viewport().mapToGlobal(position), payload[1])

    def show_protein_context_menu(self, global_position, index: int) -> None:
        menu = QMenu(self)
        view_analysis = menu.addAction("View sequence analysis…")
        export_menu = menu.addMenu("Export CSV")
        export_this = export_menu.addAction("This protein…")
        selected_indices = self.selected_indices()
        export_selected = export_menu.addAction(f"Selected proteins ({len(selected_indices)})…")
        export_selected.setEnabled(bool(selected_indices))
        export_all = export_menu.addAction(f"All proteins ({len(self.proteins)})…")
        menu.addSeparator()
        choose_color = menu.addAction("Change item color…")
        clear_color = menu.addAction("Clear item color")
        clear_color.setEnabled(bool(self.proteins[index].color))
        menu.addSeparator()
        delete = menu.addAction("Delete protein")
        action = menu.exec(global_position)
        if action == view_analysis:
            self.show_analysis(index)
        elif action == export_this:
            self.export_csv([self.proteins[index]], "protein.csv")
        elif action == export_selected:
            self.export_csv([self.proteins[selected_index] for selected_index in selected_indices], "selected-proteins.csv")
        elif action == export_all:
            self.export_csv(self.proteins, "protein-library.csv")
        elif action == choose_color:
            color = QColorDialog.getColor(QColor(self.proteins[index].color or "#dce9ff"), self, "Choose protein color")
            if color.isValid():
                self.proteins[index].color = color.name()
                self.save()
                self.refresh()
        elif action == clear_color:
            self.proteins[index].color = ""
            self.save()
            self.refresh()
        elif action == delete:
            self.delete_protein(index)

    def show_selected_analysis(self) -> None:
        """Open analysis for the single protein currently selected in the table."""
        index = self.selected_index()
        if index is None:
            self.statusBar().showMessage("Select one protein to view its full sequence analysis", 3000)
            return
        self.show_analysis(index)

    def show_analysis(self, index: int) -> None:
        ProteinAnalysisDialog(self.proteins[index], self).exec()

    def refresh(self, folder: str | None = None) -> None:
        self.tree.clear()
        all_item = QTreeWidgetItem([f"All proteins ({len(self.proteins)})"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, ("all", None))
        self.tree.addTopLevelItem(all_item)
        for group in sorted({protein.group for protein in self.proteins}):
            parent = QTreeWidgetItem([group])
            parent.setData(0, Qt.ItemDataRole.UserRole, ("folder", group))
            for index, protein in enumerate(self.proteins):
                if protein.group == group:
                    child = QTreeWidgetItem([protein.name])
                    child.setData(0, Qt.ItemDataRole.UserRole, ("protein", index))
                    self.apply_item_color(child, protein.color)
                    parent.addChild(child)
            self.tree.addTopLevelItem(parent)
        self.tree.expandAll()
        rows = [(index, protein) for index, protein in enumerate(self.proteins) if not folder or protein.group == folder]
        self.table.setRowCount(len(rows))
        for row, (index, protein) in enumerate(rows):
            props = protein_properties(protein.sequence)
            values = [protein.name, str(props["length"]), f"{props['mw'] / 1000:.2f} kDa", f"{props['e280']:,}", f"{props['e214']:,}", "—", "—"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, index)
                    self.apply_item_color(item, protein.color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignRight))
                self.table.setItem(row, column, item)
        self.update_detail()

    @staticmethod
    def apply_item_color(item: QTableWidgetItem | QTreeWidgetItem, color: str) -> None:
        if color:
            icon = MainWindow.color_dot_icon(QColor(color))
            if isinstance(item, QTreeWidgetItem):
                item.setIcon(0, icon)
            else:
                item.setIcon(icon)

    @staticmethod
    def color_dot_icon(color: QColor) -> QIcon:
        pixmap = QPixmap(12, 12)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#ffffff"))
        painter.setBrush(color)
        painter.drawEllipse(1, 1, 10, 10)
        painter.end()
        return QIcon(pixmap)

    def update_detail(self) -> None:
        indices = self.selected_indices()
        if not indices:
            self.detail_label.setText("Select one or more proteins to calculate concentration.")
            self.concentration.setText("—")
            self.update_analysis(None)
            return
        components = [protein_properties(self.proteins[index].sequence) for index in indices]
        props = {key: sum(component[key] for component in components) for key in ("length", "mw", "e280", "e214")}
        label = self.proteins[indices[0]].name if len(indices) == 1 else f"Protein complex ({len(indices)} components; 1 × each)"
        self.detail_label.setText(f"{label}  ·  {props['length']} aa  ·  {props['mw'] / 1000:.2f} kDa")
        self.update_analysis(components[0] if len(components) == 1 else None)
        for row in range(self.table.rowCount()):
            self.table.item(row, 5).setText("—")
            self.table.item(row, 6).setText("—")
        try:
            absorbance = float(self.absorbance.text())
            epsilon = props["e280"] if self.wavelength.currentText() == "A280" else props["e214"]
            if epsilon == 0:
                raise ValueError
            molar = absorbance / epsilon
            self.concentration.setText(f"{molar * 1e6:.2f} µM  ·  {molar * props['mw']:.3f} mg/mL")
            a280 = (absorbance / props["e280"]) * props["mw"] if props["e280"] else None
            a214 = (absorbance / props["e214"]) * props["mw"]
            for row in self.table.selectionModel().selectedRows():
                self.table.item(row.row(), 5).setText(f"{a280:.3f} mg/mL" if a280 is not None else "n/a")
                self.table.item(row.row(), 6).setText(f"{a214:.3f} mg/mL")
        except (ValueError, TypeError):
            self.concentration.setText("Enter an absorbance value")

    def update_analysis(self, props: dict | None) -> None:
        """Display non-additive properties only when exactly one protein is selected."""
        if props is None:
            for label in (self.pi_value, self.aromaticity_value, self.gravy_value, self.instability_value):
                label.setText("—")
            message = "Select one protein to view amino-acid composition."
            if self.selected_indices():
                message = "Composition and non-additive properties are shown for one protein at a time."
            self.composition_label.setText(message)
            return

        self.pi_value.setText(f"{props['pi']:.2f}")
        self.aromaticity_value.setText(f"{props['aromaticity'] * 100:.1f}%")
        self.gravy_value.setText(f"{props['gravy']:.2f}")
        self.instability_value.setText(f"{props['instability_index']:.1f}")
        composition = "  ·  ".join(
            f"{amino_acid} {count} ({props['aa_percentages'][amino_acid]:.1f}%)"
            for amino_acid, count in props["aa_counts"].items()
        )
        self.composition_label.setText(f"Amino-acid composition: {composition}")

    def export_csv(self, proteins: list[Protein], suggested_name: str) -> None:
        """Export a caller-selected subset of the library to a CSV file."""
        if not proteins:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export proteins to CSV", suggested_name, "CSV files (*.csv)")
        if not path:
            return
        with Path(path).open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                "Name", "Folder", "Length", "Molecular weight (Da)", "Extinction coefficient 280",
                "Extinction coefficient 214 estimate", "Calculated pI", "Aromaticity", "GRAVY hydropathy",
                "Instability index", "Amino-acid counts", "Amino-acid percentages", "Sequence",
            ])
            for protein in proteins:
                props = protein_properties(protein.sequence)
                counts = "; ".join(f"{aa}:{count}" for aa, count in props["aa_counts"].items())
                percentages = "; ".join(f"{aa}:{percentage:.2f}%" for aa, percentage in props["aa_percentages"].items())
                writer.writerow([
                    protein.name, protein.group, props["length"], f"{props['mw']:.2f}", props["e280"], props["e214"],
                    f"{props['pi']:.2f}", f"{props['aromaticity']:.4f}", f"{props['gravy']:.2f}",
                    f"{props['instability_index']:.2f}", counts, percentages, protein.sequence,
                ])
        self.statusBar().showMessage(f"Exported {len(proteins)} protein(s)", 3000)
