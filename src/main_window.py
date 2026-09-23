"""Main application window and user-interface behavior."""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QColorDialog, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QStatusBar, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget,
)

from about_dialog import AboutDialog
from app_info import APP_NAME, APP_VERSION
from protein import Protein, normalise_sequence, protein_properties
from protein_analysis_dialog import ProteinAnalysisDialog
from protein_dialog import ProteinDialog
from storage import load_collapsed_folders, load_folders, load_proteins, save_collapsed_folders, save_folders, save_proteins


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
FOLDER_SEPARATOR = " / "


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


class ProteinTree(QTreeWidget):
    """Folder tree that reports protein drops without moving its own items."""

    protein_dropped = Signal(int, str, object)
    folder_dropped = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    def dropEvent(self, event) -> None:
        source = self.currentItem()
        source_payload = source.data(0, Qt.ItemDataRole.UserRole) if source else None
        target = self.itemAt(event.position().toPoint())
        target_payload = target.data(0, Qt.ItemDataRole.UserRole) if target else None
        if not isinstance(source_payload, tuple):
            event.ignore()
            return

        # Dropping a folder on "All proteins" or the tree's blank area moves
        # it back to the root level.
        if source_payload[0] == "folder" and (
            target_payload is None
            or (isinstance(target_payload, tuple) and target_payload[0] == "all")
        ):
            self.folder_dropped.emit(source_payload[1], "")
            event.acceptProposedAction()
            return

        if not isinstance(target_payload, tuple):
            event.ignore()
            return

        if source_payload[0] == "folder" and target_payload[0] == "folder":
            self.folder_dropped.emit(source_payload[1], target_payload[1])
        elif source_payload[0] == "protein" and target_payload[0] == "folder":
            folder, adjacent_index = target_payload[1], None
            self.protein_dropped.emit(source_payload[1], folder, adjacent_index)
        elif source_payload[0] == "protein" and target_payload[0] == "protein":
            folder = target.parent().data(0, Qt.ItemDataRole.UserRole)[1]
            adjacent_index = target_payload[1]
            if self.dropIndicatorPosition() == QAbstractItemView.DropIndicatorPosition.BelowItem:
                adjacent_index += 1
            self.protein_dropped.emit(source_payload[1], folder, adjacent_index)
        else:
            event.ignore()
            return
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1220, 760)
        self.proteins = load_proteins()
        self.folders = load_folders()
        self.sync_folders()
        save_folders(self.folders)
        self.last_used_folder = self.proteins[-1].group if self.proteins else "My proteins"
        self.collapsed_folders = load_collapsed_folders()
        self.restoring_folder_state = False
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
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Name", "Amino Acids", "Weight (kDa)", "ε 280", "ε 214 (est.)", "A280", "A280 concentration", "A214 concentration"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        # Start compact, then preserve the user's widths for every column.
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setResizeContentsPrecision(-1)
        self.table_columns_initialized = False
        self.table.setColumnWidth(0, 320)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.itemSelectionChanged.connect(self.update_detail)
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_selected() if column != 5 else None)
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
        import_button = QPushButton("Import FASTA…")
        import_button.clicked.connect(lambda: self.import_fasta())
        layout.addWidget(import_button)
        label = QLabel("SEQUENCE FOLDERS")
        label.setObjectName("navlabel")
        layout.addWidget(label)
        self.tree = ProteinTree()
        self.tree.setHeaderHidden(True)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.invisibleRootItem().setFlags(
            self.tree.invisibleRootItem().flags() | Qt.ItemFlag.ItemIsDropEnabled
        )
        # Rebuild only after Qt finishes cleaning up the internal drag operation.
        self.tree.protein_dropped.connect(self.move_protein, Qt.ConnectionType.QueuedConnection)
        self.tree.folder_dropped.connect(self.move_folder, Qt.ConnectionType.QueuedConnection)
        self.tree.itemClicked.connect(self.filter_folder)
        self.tree.itemExpanded.connect(self.remember_folder_expansion)
        self.tree.itemCollapsed.connect(self.remember_folder_expansion)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_tree_context_menu)
        layout.addWidget(self.tree, 1)
        layout.addWidget(QLabel(
            "Protein data stays on this computer. Anonymous crash diagnostics reported."
        ))
        return panel

    def show_about(self) -> None:
        AboutDialog(str(APP_ICON_PATH), self).exec()

    def build_detail_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("detail")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        layout = QHBoxLayout()
        card_layout.addLayout(layout)
        self.detail_label = QLabel("Select a protein to calculate concentration.")
        self.detail_label.setMinimumWidth(220)
        layout.addWidget(self.detail_label)
        self.absorbance_label = QLabel("Absorbance")
        layout.addWidget(self.absorbance_label)
        self.saved_a214_input = ""
        self.saved_complex_a280_input = ""
        self.detail_input_mode = "single_a280"
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
        self.stoichiometry_values = {}
        self.stoichiometry_selection = ()
        self.stoichiometry_spins = {}
        self.stoichiometry_contributions = {}
        self.stoichiometry_panel = QWidget()
        panel_layout = QVBoxLayout(self.stoichiometry_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.addWidget(QLabel("Stoichiometry — copies of each protein in the complex"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(160)
        self.stoichiometry_content = QWidget()
        self.stoichiometry_form = QFormLayout(self.stoichiometry_content)
        self.stoichiometry_form.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self.stoichiometry_content)
        contributions_layout = QHBoxLayout()
        contributions_layout.addWidget(scroll, 1)
        self.stoichiometry_total = QLabel("Combined molecular weight\n—")
        self.stoichiometry_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.stoichiometry_total.setObjectName("analysisValue")
        contributions_layout.addWidget(self.stoichiometry_total)
        panel_layout.addLayout(contributions_layout)
        card_layout.addWidget(self.stoichiometry_panel)
        self.stoichiometry_panel.hide()
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

    def sync_folders(self) -> None:
        self.folders.update(protein.group for protein in self.proteins)
        for path in tuple(self.folders):
            parts = path.split(FOLDER_SEPARATOR)
            self.folders.update(FOLDER_SEPARATOR.join(parts[:depth]) for depth in range(1, len(parts)))

    def save(self) -> None:
        self.sync_folders()
        save_proteins(self.proteins)
        save_folders(self.folders)

    def create_folder(self, parent: str = "") -> None:
        name, accepted = QInputDialog.getText(self, "New subfolder" if parent else "New folder", "Folder name:")
        if not accepted:
            return
        name = name.strip()
        if not name or FOLDER_SEPARATOR in name:
            QMessageBox.warning(self, "New folder", "Enter a folder name without ' / '.")
            return
        path = f"{parent}{FOLDER_SEPARATOR}{name}" if parent else name
        if path in self.folders:
            QMessageBox.warning(self, "New folder", "A folder with this name already exists here.")
            return
        self.folders.add(path)
        parts = path.split(FOLDER_SEPARATOR)
        self.collapsed_folders.difference_update(FOLDER_SEPARATOR.join(parts[:depth]) for depth in range(1, len(parts)))
        save_collapsed_folders(self.collapsed_folders)
        self.save()
        self.refresh(path)
        self.statusBar().showMessage(f"Created {name}", 3000)

    def remap_folder(self, old: str, new: str) -> None:
        def remap(path: str) -> str:
            return new + path[len(old):] if path == old or path.startswith(old + FOLDER_SEPARATOR) else path
        self.folders = {remap(path) for path in self.folders}
        self.collapsed_folders = {remap(path) for path in self.collapsed_folders}
        self.last_used_folder = remap(self.last_used_folder)
        save_collapsed_folders(self.collapsed_folders)

    def selected_indices(self) -> list[int]:
        rows = self.table.selectionModel().selectedRows()
        return sorted(self.table.item(row.row(), 0).data(Qt.ItemDataRole.UserRole) for row in rows)

    def selected_index(self) -> int | None:
        indices = self.selected_indices()
        return indices[0] if len(indices) == 1 else None

    def add_protein(self) -> None:
        dialog = ProteinDialog(self, default_group=self.last_used_folder)
        if dialog.exec():
            protein = dialog.value()
            self.proteins.append(protein)
            self.last_used_folder = protein.group
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

    def remember_folder_expansion(self, item: QTreeWidgetItem) -> None:
        """Persist a user's folder toggle so it can be restored after a restart."""
        if self.restoring_folder_state:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, tuple) or payload[0] != "folder":
            return
        folder = payload[1]
        if item.isExpanded():
            self.collapsed_folders.discard(folder)
        else:
            self.collapsed_folders.add(folder)
        save_collapsed_folders(self.collapsed_folders)

    def select_protein(self, index: int) -> None:
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == index:
                self.table.selectionModel().select(
                    self.table.model().index(row, 0),
                    QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
                )
                return
        # A protein clicked in the tree may belong to a different folder than
        # the one currently displayed in the main table.
        self.refresh(self.proteins[index].group)
        self.select_protein(index)

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
        global_position = self.tree.viewport().mapToGlobal(position)
        if not isinstance(payload, tuple) or payload[0] == "all":
            menu = QMenu(self)
            create = menu.addAction("New folder…")
            if menu.exec(global_position) == create:
                self.create_folder()
            return
        kind, value = payload
        if kind == "protein":
            self.show_protein_context_menu(global_position, value)
        elif kind == "folder":
            self.show_folder_context_menu(global_position, value)

    def show_protein_context_menu(self, global_position, index: int) -> None:
        menu = QMenu(self)
        view_analysis = menu.addAction("View sequence analysis…")
        selected_indices = self.selected_indices()
        csv_menu = menu.addMenu("Export CSV")
        export_this_csv = csv_menu.addAction("This protein…")
        export_selected_csv = csv_menu.addAction(f"Selected proteins ({len(selected_indices)})…")
        export_selected_csv.setEnabled(bool(selected_indices))
        export_all_csv = csv_menu.addAction(f"All proteins ({len(self.proteins)})…")
        fasta_menu = menu.addMenu("Export FASTA")
        export_this_fasta = fasta_menu.addAction("This protein…")
        export_selected_fasta = fasta_menu.addAction(f"Selected proteins ({len(selected_indices)})…")
        export_selected_fasta.setEnabled(bool(selected_indices))
        export_all_fasta = fasta_menu.addAction(f"All proteins ({len(self.proteins)})…")
        menu.addSeparator()
        color_indices = selected_indices if index in selected_indices else [index]
        color_label = "selected items" if len(color_indices) > 1 else "item"
        choose_color = menu.addAction(f"Change {color_label} color…")
        clear_color = menu.addAction(f"Clear {color_label} color")
        clear_color.setEnabled(any(self.proteins[item_index].color for item_index in color_indices))
        menu.addSeparator()
        delete = menu.addAction("Delete protein")
        action = menu.exec(global_position)
        if action == view_analysis:
            self.show_analysis(index)
        elif action == export_this_csv:
            self.export_csv([self.proteins[index]], "protein.csv")
        elif action == export_selected_csv:
            self.export_csv([self.proteins[selected_index] for selected_index in selected_indices], "selected-proteins.csv")
        elif action == export_all_csv:
            self.export_csv(self.proteins, "protein-library.csv")
        elif action == export_this_fasta:
            self.export_fasta([self.proteins[index]], "protein.fasta")
        elif action == export_selected_fasta:
            self.export_fasta(
                [self.proteins[selected_index] for selected_index in selected_indices],
                "selected-proteins.fasta",
            )
        elif action == export_all_fasta:
            self.export_fasta(self.proteins, "protein-library.fasta")
        elif action == choose_color:
            self.choose_color_for_proteins(color_indices)
        elif action == clear_color:
            self.clear_color_for_proteins(color_indices)
        elif action == delete:
            self.delete_protein(index)

    def show_folder_context_menu(self, global_position, folder: str) -> None:
        iterator = QTreeWidgetItemIterator(self.tree)
        folder_item = None
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == ("folder", folder):
                folder_item = item
                break
            iterator += 1
        if folder_item is None:
            return
        indices = [
            index for index, protein in enumerate(self.proteins)
            if protein.group == folder or protein.group.startswith(f"{folder}{FOLDER_SEPARATOR}")
        ]
        menu = QMenu(self)
        toggle_expansion = menu.addAction(
            "Collapse folder and subfolders" if folder_item.isExpanded() else "Expand folder and subfolders"
        )
        menu.addSeparator()
        new_folder = menu.addAction("New subfolder…")
        rename_folder = menu.addAction("Rename folder…")
        menu.addSeparator()
        import_fasta = menu.addAction("Import FASTA into folder…")
        export_fasta = menu.addAction(f"Export folder as FASTA ({len(indices)} proteins)…")
        menu.addSeparator()
        choose_color = menu.addAction(f"Change color for folder ({len(indices)} proteins)…")
        clear_color = menu.addAction(f"Clear color for folder ({len(indices)} proteins)")
        clear_color.setEnabled(any(self.proteins[index].color for index in indices))
        menu.addSeparator()
        delete_folder = menu.addAction(f"Delete folder and contents ({len(indices)} proteins)…")
        export_fasta.setEnabled(bool(indices))
        choose_color.setEnabled(bool(indices))
        action = menu.exec(global_position)
        if action == toggle_expansion:
            expanded = not folder_item.isExpanded()
            self.restoring_folder_state = True
            try:
                pending = [folder_item]
                while pending:
                    item = pending.pop()
                    payload = item.data(0, Qt.ItemDataRole.UserRole)
                    if isinstance(payload, tuple) and payload[0] == "folder":
                        item.setExpanded(expanded)
                        if expanded:
                            self.collapsed_folders.discard(payload[1])
                        else:
                            self.collapsed_folders.add(payload[1])
                    pending.extend(item.child(index) for index in range(item.childCount()))
            finally:
                self.restoring_folder_state = False
            save_collapsed_folders(self.collapsed_folders)
        elif action == new_folder:
            self.create_folder(folder)
        elif action == rename_folder:
            self.rename_folder(folder)
        elif action == import_fasta:
            self.import_fasta(folder)
        elif action == export_fasta:
            folder_name = folder.rsplit(FOLDER_SEPARATOR, 1)[-1]
            self.export_fasta([self.proteins[index] for index in indices], f"{folder_name}.fasta")
        elif action == choose_color:
            self.choose_color_for_proteins(indices)
        elif action == clear_color:
            self.clear_color_for_proteins(indices)
        elif action == delete_folder:
            self.delete_folder(folder, indices)

    def choose_color_for_proteins(self, indices: list[int]) -> None:
        """Choose and apply one color to every supplied protein."""
        if not indices:
            return
        color = QColorDialog.getColor(
            QColor(self.proteins[indices[0]].color or "#dce9ff"), self, "Choose protein color",
        )
        if color.isValid():
            for index in indices:
                self.proteins[index].color = color.name()
            self.save()
            self.refresh()

    def clear_color_for_proteins(self, indices: list[int]) -> None:
        """Clear the assigned color from every supplied protein."""
        for index in indices:
            self.proteins[index].color = ""
        self.save()
        self.refresh()

    def delete_folder(self, folder: str, indices: list[int]) -> None:
        """Confirm and delete a folder, including all nested folders and proteins."""
        folder_name = folder.rsplit(FOLDER_SEPARATOR, 1)[-1]
        prompt = (
            f'Delete the folder "{folder_name}" and its {len(indices)} protein(s)?\n\n'
            "Any nested folders and their proteins will also be deleted."
        )
        if QMessageBox.question(self, "Delete folder", prompt) != QMessageBox.StandardButton.Yes:
            return
        for index in sorted(indices, reverse=True):
            self.proteins.pop(index)
        removed = {path for path in self.folders if path == folder or path.startswith(folder + FOLDER_SEPARATOR)}
        self.folders.difference_update(removed)
        self.collapsed_folders.difference_update(removed)
        if self.last_used_folder in removed:
            self.last_used_folder = "My proteins"
        save_collapsed_folders(self.collapsed_folders)
        self.save()
        self.refresh()
        self.statusBar().showMessage(f"Deleted {folder_name} and {len(indices)} protein(s)", 3000)

    def rename_folder(self, folder: str) -> None:
        """Rename a folder while retaining its nested folders and proteins."""
        old_name = folder.rsplit(FOLDER_SEPARATOR, 1)[-1]
        new_name, accepted = QInputDialog.getText(self, "Rename folder", "Folder name:", text=old_name)
        new_name = new_name.strip()
        if not accepted or new_name == old_name:
            return
        if not new_name:
            QMessageBox.warning(self, "Rename folder", "A folder name is required.")
            return
        if FOLDER_SEPARATOR in new_name:
            QMessageBox.warning(self, "Rename folder", "Folder names cannot contain ' / '.")
            return
        parent_folder = folder.rpartition(FOLDER_SEPARATOR)[0]
        new_folder = f"{parent_folder}{FOLDER_SEPARATOR}{new_name}" if parent_folder else new_name
        if new_folder in self.folders:
            QMessageBox.warning(self, "Rename folder", "A folder with this name already exists here.")
            return
        for protein in self.proteins:
            if protein.group == folder or protein.group.startswith(f"{folder}{FOLDER_SEPARATOR}"):
                protein.group = f"{new_folder}{protein.group[len(folder):]}"
        self.remap_folder(folder, new_folder)
        self.save()
        self.refresh(new_folder)
        self.statusBar().showMessage(f"Renamed {old_name} to {new_name}", 3000)

    def show_selected_analysis(self) -> None:
        """Open analysis for the single protein currently selected in the table."""
        index = self.selected_index()
        if index is None:
            self.statusBar().showMessage("Select one protein to view its full sequence analysis", 3000)
            return
        self.show_analysis(index)

    def show_analysis(self, index: int) -> None:
        ProteinAnalysisDialog(self.proteins[index], self).exec()

    def move_protein(self, source_index: int, folder: str, adjacent_index: int | None) -> None:
        """Move a protein within the library and optionally assign it to another folder."""
        protein = self.proteins.pop(source_index)
        protein.group = folder
        if adjacent_index is None:
            destination = max(
                (index + 1 for index, item in enumerate(self.proteins) if item.group == folder),
                default=len(self.proteins),
            )
        else:
            # Account for removing an item before its destination in the list.
            destination = adjacent_index - (source_index < adjacent_index)
        self.proteins.insert(destination, protein)
        self.save()
        self.refresh()
        self.statusBar().showMessage(f"Moved {protein.name} to {folder}", 3000)

    def move_folder(self, source_folder: str, destination_folder: str) -> None:
        """Nest a folder under another folder, moving all of its contents with it."""
        if source_folder == destination_folder or (
            destination_folder and destination_folder.startswith(f"{source_folder}{FOLDER_SEPARATOR}")
        ):
            self.statusBar().showMessage("A folder cannot be dropped into itself or one of its subfolders", 3000)
            return
        leaf_name = source_folder.rsplit(FOLDER_SEPARATOR, 1)[-1]
        new_folder = (
            f"{destination_folder}{FOLDER_SEPARATOR}{leaf_name}"
            if destination_folder else leaf_name
        )
        if new_folder == source_folder:
            return
        if new_folder in self.folders:
            self.statusBar().showMessage("That folder already contains a folder with this name", 3000)
            return
        for protein in self.proteins:
            if protein.group == source_folder or protein.group.startswith(f"{source_folder}{FOLDER_SEPARATOR}"):
                protein.group = f"{new_folder}{protein.group[len(source_folder):]}"
        self.remap_folder(source_folder, new_folder)
        # Reveal the moved folder even when its destination was collapsed.
        parts = new_folder.split(FOLDER_SEPARATOR)
        self.collapsed_folders.difference_update(
            FOLDER_SEPARATOR.join(parts[:depth]) for depth in range(1, len(parts))
        )
        save_collapsed_folders(self.collapsed_folders)
        self.save()
        self.refresh(new_folder)
        location = destination_folder or "the root"
        self.statusBar().showMessage(f"Moved {leaf_name} into {location}", 3000)

    def refresh(self, selected_folder: str | None = None) -> None:
        self.restoring_folder_state = True
        self.tree.clear()
        all_item = QTreeWidgetItem([f"All proteins ({len(self.proteins)})"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, ("all", None))
        all_item.setFlags(
            (all_item.flags() | Qt.ItemFlag.ItemIsDropEnabled) & ~Qt.ItemFlag.ItemIsDragEnabled
        )
        self.tree.addTopLevelItem(all_item)
        self.sync_folders()
        folders = self.folders
        folder_items: dict[str, QTreeWidgetItem] = {}
        for folder_path in sorted(folders, key=lambda value: (value.count(FOLDER_SEPARATOR), value.casefold())):
            label = folder_path.rsplit(FOLDER_SEPARATOR, 1)[-1]
            parent = QTreeWidgetItem([label])
            parent.setData(0, Qt.ItemDataRole.UserRole, ("folder", folder_path))
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            folder_items[folder_path] = parent
            parent_folder = folder_path.rpartition(FOLDER_SEPARATOR)[0]
            if parent_folder:
                folder_items[parent_folder].addChild(parent)
            else:
                self.tree.addTopLevelItem(parent)
        for index, protein in enumerate(self.proteins):
            child = QTreeWidgetItem([protein.name])
            child.setData(0, Qt.ItemDataRole.UserRole, ("protein", index))
            child.setFlags(
                (child.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsDropEnabled
            )
            self.apply_item_color(child, protein.color)
            folder_items[protein.group].addChild(child)
        for folder_path, item in folder_items.items():
            item.setExpanded(folder_path not in self.collapsed_folders)
        if selected_folder in folder_items:
            self.tree.setCurrentItem(folder_items[selected_folder])
            self.tree.scrollToItem(folder_items[selected_folder])
        self.restoring_folder_state = False
        rows = [
            (index, protein) for index, protein in enumerate(self.proteins)
            if not selected_folder
            or protein.group == selected_folder
            or protein.group.startswith(f"{selected_folder}{FOLDER_SEPARATOR}")
        ]
        self.table.setRowCount(len(rows))
        for row, (index, protein) in enumerate(rows):
            props = protein_properties(protein.sequence)
            values = [protein.name, str(props["length"]), f"{props['mw'] / 1000:.2f} kDa", f"{props['e280']:,}", f"{props['e214']:,}", "", self.a280_concentration(protein), "—"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setToolTip(protein.name)
                    item.setData(Qt.ItemDataRole.UserRole, index)
                    self.apply_item_color(item, protein.color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | (Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignRight))
                self.table.setItem(row, column, item)
            absorbance_input = QLineEdit()
            absorbance_input.setObjectName("proteinAbsorbanceInput")
            absorbance_input.ensurePolished()
            absorbance_input.setAlignment(Qt.AlignmentFlag.AlignRight)
            absorbance_input.setPlaceholderText("Enter A280")
            absorbance_input.setText("" if protein.absorbance_280 is None else str(protein.absorbance_280))
            absorbance_input.setToolTip("Saved A280 for this protein (1 cm optical path). Clear to remove.")
            absorbance_input.textChanged.connect(
                lambda text, record=protein, editor=absorbance_input: self.save_protein_absorbance(record, editor, text)
            )
            self.table.setCellWidget(row, 5, absorbance_input)
            self.table.setRowHeight(row, max(38, self.table.rowHeight(row), absorbance_input.sizeHint().height()))
        self.update_detail()
        if not self.table_columns_initialized:
            for column in range(1, self.table.columnCount()):
                self.table.resizeColumnToContents(column)
            self.table_columns_initialized = True

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

    @staticmethod
    def a280_concentration(protein: Protein) -> str:
        if protein.absorbance_280 is None:
            return "—"
        props = protein_properties(protein.sequence)
        if not props["e280"]:
            return "n/a"
        return f"{protein.absorbance_280 / props['e280'] * props['mw']:.3f} mg/mL"

    def save_protein_absorbance(self, protein: Protein, editor: QLineEdit, text: str) -> None:
        try:
            value = float(text) if text.strip() else None
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError
        except ValueError:
            editor.setStyleSheet("border: 1px solid #bc4545;")
            editor.setToolTip("Enter a finite, non-negative A280. This entry has not been saved.")
            return
        editor.setStyleSheet("")
        editor.setToolTip("Saved A280 for this protein (1 cm optical path). Clear to remove.")
        if not any(record is protein for record in self.proteins):
            return
        protein.absorbance_280 = value
        self.save()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 5) is editor:
                self.table.item(row, 6).setText(self.a280_concentration(protein))
                break
        self.update_detail()

    def update_stoichiometry_controls(self, indices: list[int]) -> None:
        records = [self.proteins[index] for index in indices] if len(indices) > 1 else []
        selection = tuple((id(record), record.name) for record in records)
        self.stoichiometry_panel.setVisible(bool(records))
        if selection == self.stoichiometry_selection:
            return
        self.stoichiometry_selection = selection
        while self.stoichiometry_form.rowCount():
            self.stoichiometry_form.removeRow(0)
        self.stoichiometry_spins.clear()
        self.stoichiometry_contributions.clear()
        # Keep counts attached to record objects, not their changing table rows.
        live_ids = {id(record) for record in self.proteins}
        self.stoichiometry_values = {
            key: value for key, value in self.stoichiometry_values.items() if key in live_ids
        }
        for record in records:
            spin = QSpinBox()
            spin.setRange(1, 9999)
            spin.setMaximumWidth(140)
            spin.setValue(self.stoichiometry_values.get(id(record), (record, 1))[1])
            spin.setAccessibleName(f"Copies of {record.name}")
            spin.valueChanged.connect(lambda value, protein=record: self.set_stoichiometry(protein, value))
            label = QLabel(record.name)
            label.setWordWrap(True)
            contribution_row = QWidget()
            contribution_layout = QHBoxLayout(contribution_row)
            contribution_layout.setContentsMargins(0, 0, 0, 0)
            contribution_layout.addWidget(spin)
            contribution = QLabel()
            contribution_layout.addWidget(contribution)
            contribution_layout.addStretch(1)
            self.stoichiometry_form.addRow(label, contribution_row)
            self.stoichiometry_spins[id(record)] = spin
            self.stoichiometry_contributions[id(record)] = contribution

    def set_stoichiometry(self, protein: Protein, copies: int) -> None:
        self.stoichiometry_values[id(protein)] = (protein, copies)
        self.update_detail()

    def update_detail(self) -> None:
        indices = self.selected_indices()
        self.update_stoichiometry_controls(indices)
        is_a280 = self.wavelength.currentText() == "A280"
        # Keep calculator measurements separate from each record's saved A280.
        if self.detail_input_mode == "a214":
            self.saved_a214_input = self.absorbance.text()
        elif self.detail_input_mode == "complex_a280":
            self.saved_complex_a280_input = self.absorbance.text()
        single_a280 = is_a280 and len(indices) <= 1
        self.detail_input_mode = "single_a280" if single_a280 else ("complex_a280" if is_a280 else "a214")
        self.absorbance.setReadOnly(single_a280)
        self.absorbance_label.setText("Complex A280" if is_a280 and len(indices) > 1 else "Absorbance")
        record_a280 = self.proteins[indices[0]].absorbance_280 if single_a280 and indices else None
        if single_a280:
            input_text = f"{record_a280:.6g}" if record_a280 is not None else ""
        else:
            input_text = self.saved_complex_a280_input if is_a280 else self.saved_a214_input
        self.absorbance.blockSignals(True)
        self.absorbance.setText(input_text)
        self.absorbance.blockSignals(False)
        self.absorbance.setPlaceholderText("Use table A280" if single_a280 else "e.g. 0.85")
        if not indices:
            self.detail_label.setText("Select one or more proteins to calculate concentration.")
            self.concentration.setText("—")
            self.update_analysis(None)
            return
        components = [protein_properties(self.proteins[index].sequence) for index in indices]
        copies = [self.stoichiometry_values.get(id(self.proteins[index]), (None, 1))[1] for index in indices] if len(indices) > 1 else [1]
        props = {
            key: sum(component[key] * count for component, count in zip(components, copies))
            for key in ("length", "mw", "e280", "e214")
        }
        if len(indices) > 1:
            for index, component, count in zip(indices, components, copies):
                self.stoichiometry_contributions[id(self.proteins[index])].setText(
                    f"{component['mw'] / 1000:.2f} kDa × {count} = {component['mw'] * count / 1000:.2f} kDa"
                )
            self.stoichiometry_total.setText(f"Combined molecular weight\n{props['mw'] / 1000:.2f} kDa")
        label = self.proteins[indices[0]].name if len(indices) == 1 else f"Protein complex ({len(indices)} components; {sum(copies)} total copies)"
        self.detail_label.setText(f"{label}  ·  {props['length']} aa  ·  {props['mw'] / 1000:.2f} kDa")
        self.update_analysis(components[0] if len(components) == 1 else None)
        for row in range(self.table.rowCount()):
            self.table.item(row, 7).setText("—")
        try:
            absorbance = record_a280 if single_a280 else float(self.absorbance.text())
            if absorbance is None or not math.isfinite(absorbance) or absorbance < 0:
                raise ValueError
            epsilon = props["e280"] if self.wavelength.currentText() == "A280" else props["e214"]
            if epsilon == 0:
                self.concentration.setText("Concentration unavailable: zero extinction coefficient")
                return
            molar = absorbance / epsilon
            self.concentration.setText(f"{molar * 1e6:.2f} µM  ·  {molar * props['mw']:.3f} mg/mL")
            if not is_a280:
                a214 = (absorbance / props["e214"]) * props["mw"]
                for row in self.table.selectionModel().selectedRows():
                    self.table.item(row.row(), 7).setText(f"{a214:.3f} mg/mL")
        except (ValueError, TypeError):
            self.concentration.setText("Enter A280 in this protein's table row" if single_a280 else "Enter a finite, non-negative absorbance value")

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
                "Instability index", "Amino-acid counts", "Amino-acid percentages", "Sequence", "Notes", "A280",
            ])
            for protein in proteins:
                props = protein_properties(protein.sequence)
                counts = "; ".join(f"{aa}:{count}" for aa, count in props["aa_counts"].items())
                percentages = "; ".join(f"{aa}:{percentage:.2f}%" for aa, percentage in props["aa_percentages"].items())
                writer.writerow([
                    protein.name, protein.group, props["length"], f"{props['mw']:.2f}", props["e280"], props["e214"],
                    f"{props['pi']:.2f}", f"{props['aromaticity']:.4f}", f"{props['gravy']:.2f}",
                    f"{props['instability_index']:.2f}", counts, percentages, protein.sequence, protein.notes, protein.absorbance_280,
                ])
        self.statusBar().showMessage(f"Exported {len(proteins)} protein(s)", 3000)

    def export_fasta(self, proteins: list[Protein], suggested_name: str) -> None:
        """Export a caller-selected subset of the library in FASTA format."""
        if not proteins:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export proteins to FASTA", suggested_name, "FASTA files (*.fasta *.fa *.faa)",
        )
        if not path:
            return
        output = []
        for protein in proteins:
            output.append(f">{protein.name}")
            output.append(protein.sequence)
        Path(path).write_text("\n".join(output) + "\n")
        self.statusBar().showMessage(f"Exported {len(proteins)} protein(s) to FASTA", 3000)

    def import_fasta(self, destination_folder: str | None = None) -> None:
        """Import one or more protein sequences from a FASTA file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import protein FASTA", "", "FASTA files (*.fasta *.fa *.faa);;All files (*)",
        )
        if not path:
            return
        try:
            records = self.parse_fasta(Path(path).read_text())
            for name, sequence in records:
                try:
                    protein_properties(sequence)
                except ValueError as exc:
                    raise ValueError(f'{name}: {exc}') from exc
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, "Import FASTA", str(exc))
            return
        folder = destination_folder
        if folder is None:
            folder, accepted = QInputDialog.getText(
                self, "Import FASTA", "Folder for imported proteins:", text=self.last_used_folder,
            )
            folder = folder.strip()
            if not accepted:
                return
            folder = folder or "My proteins"
        self.proteins.extend(Protein(name, sequence, folder) for name, sequence in records)
        self.last_used_folder = folder
        self.save()
        self.refresh(folder)
        self.statusBar().showMessage(f"Imported {len(records)} protein(s) from FASTA", 3000)

    @staticmethod
    def parse_fasta(text: str) -> list[tuple[str, str]]:
        """Parse FASTA text into validated record boundaries."""
        records: list[tuple[str, str]] = []
        name: str | None = None
        sequence_lines: list[str] = []
        for line_number, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    if not sequence_lines:
                        raise ValueError(f'FASTA record "{name}" has no sequence.')
                    records.append((name, normalise_sequence("".join(sequence_lines))))
                name = line[1:].strip() or f"Untitled protein {len(records) + 1}"
                sequence_lines = []
            elif name is None:
                raise ValueError(f"Expected a FASTA header beginning with '>' on line {line_number}.")
            else:
                sequence_lines.append(line)
        if name is not None:
            if not sequence_lines:
                raise ValueError(f'FASTA record "{name}" has no sequence.')
            records.append((name, normalise_sequence("".join(sequence_lines))))
        if not records:
            raise ValueError("The selected file contains no FASTA records.")
        return records
