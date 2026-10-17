"""Run with QT_QPA_PLATFORM=offscreen for headless UI checks."""
import unittest

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from protein import Protein
from protein_dialog import ProteinDialog
from protein_analysis_dialog import ProteinAnalysisDialog
from sequence_feature_view import FeatureLegend, LegendItem


class LegendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def items(self, dialog):
        legend = dialog.findChild(FeatureLegend)
        return [legend.entries.itemAt(i).widget() for i in range(legend.entries.count())
                if isinstance(legend.entries.itemAt(i).widget(), LegendItem)]

    def underlined_ranges(self, dialog):
        ranges = []
        block = dialog.sequence.document().begin()
        while block.isValid():
            for span in block.layout().formats():
                if span.format.fontUnderline():
                    ranges.append((block.position() + span.start, span.length))
            block = block.next()
        return ranges

    def test_detected_only_and_hover_all_occurrences(self):
        sequence = 'DYKDDDDKAAADYKDDDDK'
        for cls in [ProteinDialog, ProteinAnalysisDialog]:
            with self.subTest(dialog=cls.__name__):
                dialog = cls(protein=Protein('Test', sequence))
                items = self.items(dialog)
                self.assertEqual([item.text() for item in items], ['FLAG', 'Enterokinase'])
                cursor_before = dialog.sequence.textCursor().position()
                self.app.sendEvent(items[0], QEnterEvent(QPointF(), QPointF(), QPointF()))
                self.assertEqual(self.underlined_ranges(dialog), [(0, 8), (11, 8)])
                self.app.sendEvent(items[0], QEvent(QEvent.Type.Leave))
                self.assertEqual(self.underlined_ranges(dialog), [])
                self.assertEqual(dialog.sequence.toPlainText(), sequence)
                self.assertEqual(dialog.sequence.textCursor().position(), cursor_before)
                self.assertFalse(dialog.sequence.document().isUndoAvailable())
                dialog.close()

    def test_live_legend_and_hover_reset(self):
        dialog = ProteinDialog(protein=Protein('Test', 'HHHHHH'))
        item = self.items(dialog)[0]
        self.app.sendEvent(item, QEnterEvent(QPointF(), QPointF(), QPointF()))
        dialog.sequence.setPlainText('YPYDVPDYA')
        self.assertEqual([item.text() for item in self.items(dialog)], ['HA'])
        self.assertIsNone(dialog.features.hovered_feature)
        dialog.sequence.clear()
        self.assertEqual(self.items(dialog), [])
        self.assertEqual(dialog.sequence.extraSelections(), [])
        dialog.close()

    def test_multiline_hover_is_rendered_and_restored(self):
        dialog = ProteinDialog(protein=Protein('Test', 'AAADYKDDDDKAAA'))
        dialog.sequence.setPlainText('AAADYK\nDDDDKAAA')
        dialog.show()
        self.app.processEvents()
        before = dialog.sequence.grab().toImage()
        def line_widths():
            block = dialog.sequence.document().begin()
            widths = []
            while block.isValid():
                layout = block.layout()
                widths.extend(layout.lineAt(i).naturalTextWidth() for i in range(layout.lineCount()))
                block = block.next()
            return widths
        widths_before = line_widths()
        item = self.items(dialog)[0]
        self.app.sendEvent(item, QEnterEvent(QPointF(), QPointF(), QPointF()))
        self.app.processEvents()
        self.assertEqual(self.underlined_ranges(dialog), [(3, 3), (7, 5)])
        self.assertEqual(line_widths(), widths_before)
        hovered = dialog.sequence.grab().toImage()
        self.assertNotEqual(before, hovered)
        self.app.sendEvent(item, QEvent(QEvent.Type.Leave))
        self.app.processEvents()
        self.assertEqual(self.underlined_ranges(dialog), [])
        self.assertEqual(before, dialog.sequence.grab().toImage())
        dialog.close()

    def test_selected_text_is_underlined_without_hover(self):
        dialog = ProteinDialog(protein=Protein('Test', 'AAADYKDDDDKAAA'))
        self.assertEqual(self.underlined_ranges(dialog), [])
        dialog.features.table.selectRow(0)
        self.assertEqual(self.underlined_ranges(dialog), [(3, 8)])
        cursor = dialog.sequence.textCursor()
        cursor.clearSelection()
        dialog.sequence.setTextCursor(cursor)
        self.assertEqual(self.underlined_ranges(dialog), [])
        cursor.setPosition(0)
        cursor.setPosition(3, QTextCursor.MoveMode.KeepAnchor)
        dialog.sequence.setTextCursor(cursor)
        self.assertEqual(self.underlined_ranges(dialog), [(0, 3)])
        dialog.close()

    def test_new_tag_legend_and_hover(self):
        sequence = 'GLNDIFEAQKIEWHEAAAWSHPQFEK'
        for cls in [ProteinDialog, ProteinAnalysisDialog]:
            dialog = cls(protein=Protein('New tags', sequence))
            items = self.items(dialog)
            self.assertEqual([item.text() for item in items], ['AviTag', 'Strep-tag II'])
            self.app.sendEvent(items[0], QEnterEvent(QPointF(), QPointF(), QPointF()))
            self.assertEqual(self.underlined_ranges(dialog), [(0, 15)])
            self.app.sendEvent(items[0], QEvent(QEvent.Type.Leave))
            self.assertEqual(self.underlined_ranges(dialog), [])
            dialog.close()

    def test_variant_table_and_hover(self):
        from sequence_features import GST_SEQUENCE
        sequence = 'A' + GST_SEQUENCE[1:]
        dialog = ProteinDialog(protein=Protein('Variant', sequence))
        row = next(i for i, f in enumerate(dialog.features.features) if f.name == 'GST')
        self.assertEqual(dialog.features.table.item(row, 6).text(), '99.5%')
        self.assertEqual(dialog.features.table.item(row, 7).text(), '1')
        item = next(item for item in self.items(dialog) if item.text() == 'GST')
        self.app.sendEvent(item, QEnterEvent(QPointF(), QPointF(), QPointF()))
        self.assertEqual(self.underlined_ranges(dialog), [(0, len(sequence))])
        self.assertEqual(dialog.sequence.toPlainText(), sequence)
        dialog.close()
