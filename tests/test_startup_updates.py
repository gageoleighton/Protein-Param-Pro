import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

import main_window as m
from update_checker import Release


class StartupUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [patch.object(m, 'load_proteins', return_value=[]),
                        patch.object(m, 'load_folders', return_value=set()),
                        patch.object(m, 'load_collapsed_folders', return_value=set()),
                        patch.object(m, 'save_folders')]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.window = m.MainWindow()
        self.window.update_checker.check = Mock()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.startup_update_timer.stop)

    def test_startup_runs_once_without_progress_or_no_update_dialog(self):
        self.app.processEvents()
        self.app.processEvents()
        self.window.update_checker.check.assert_called_once()
        self.assertTrue(self.window.silent_update_check)
        self.window.update_checker.busy_changed.emit(True)
        self.assertEqual(self.window.statusBar().currentMessage(), 'Ready')
        self.assertTrue(self.window.check_updates_button.isEnabled())
        with patch.object(m.QMessageBox, 'warning') as warning, patch.object(m.QMessageBox, 'information') as info:
            self.window.update_checker.failed.emit('Network error')
            self.window.update_checker.completed.emit(Release('0.1.0', '', False))
            warning.assert_not_called()
            info.assert_not_called()

    def test_startup_new_version_notifies(self):
        self.app.processEvents()
        with patch.object(m, 'QMessageBox') as box:
            box.return_value.clickedButton.return_value = None
            self.window.update_checker.completed.emit(Release('9.0.0', '', True))
            box.return_value.exec.assert_called_once()

    def test_manual_check_reuses_startup_request_and_reports_results(self):
        self.app.processEvents()
        self.window.update_checker.reply = object()
        self.window.check_updates_button.click()
        self.assertFalse(self.window.silent_update_check)
        self.window.update_checker.check.assert_called_once()
        self.assertFalse(self.window.check_updates_button.isEnabled())
        self.window.update_checker.busy_changed.emit(False)
        self.assertTrue(self.window.check_updates_button.isEnabled())
        with patch.object(m.QMessageBox, 'information') as info, patch.object(m.QMessageBox, 'warning') as warning:
            self.window.show_update_result(Release('0.1.0', '', False))
            self.window.show_update_error('Network error')
            info.assert_called_once()
            warning.assert_called_once()
        self.window.update_checker.reply = None

    def test_manual_check_before_startup_cancels_scheduled_check(self):
        self.window.check_updates_action.trigger()
        self.app.processEvents()
        self.window.update_checker.check.assert_called_once()
        self.assertFalse(self.window.silent_update_check)
