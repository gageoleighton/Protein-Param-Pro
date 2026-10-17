import json
import unittest
from unittest.mock import Mock

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from update_checker import UpdateChecker, parse_release


def payload(version='v0.1.2', **extra):
    return json.dumps(dict(tag_name=version, draft=False, prerelease=False, **extra)).encode()


class Reply(QObject):
    finished = Signal()

    def __init__(self, status=200, data=None, error=QNetworkReply.NetworkError.NoError):
        super().__init__()
        self.status, self.data, self.network_error = status, data or payload(), error
        self.deleted = False

    def attribute(self, _):
        return self.status

    def error(self):
        return self.network_error

    def readAll(self):
        return self.data

    def abort(self):
        self.finished.emit()

    def deleteLater(self):
        self.deleted = True


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_versions(self):
        for latest, current, newer in [('v0.1.2', '0.1.1', True), ('v0.1.10', '0.1.9', True),
                                       ('v0.1.1', '0.1.1', False), ('v0.1.0', '0.1.1', False)]:
            self.assertEqual(parse_release(payload(latest), current).newer, newer)
        release = parse_release(payload(html_url='https://untrusted.example/'))
        self.assertTrue(release.url.startswith('https://github.com/gageoleighton/Protein-Param-Pro/releases/tag/'))

    def test_malformed_and_prerelease(self):
        for data in [b'not json', b'[]', b'{}', payload('banana'), payload('v1.0.0rc1'),
                     b'{"tag_name":"v2.0.0","draft":false,"prerelease":true}']:
            with self.assertRaises(ValueError):
                parse_release(data)

    def checker(self, reply):
        checker = UpdateChecker()
        checker.manager = Mock()
        checker.manager.get.return_value = reply
        checker.completed.connect(self.results.append)
        checker.failed.connect(self.errors.append)
        checker.busy_changed.connect(self.busy.append)
        return checker

    def setUp(self):
        self.results, self.errors, self.busy = [], [], []

    def test_success_and_duplicate_request(self):
        reply = Reply()
        checker = self.checker(reply)
        checker.check(); checker.check()
        checker.manager.get.assert_called_once()
        self.assertEqual(self.busy, [True])
        reply.finished.emit()
        self.assertEqual(self.busy, [True, False])
        self.assertTrue(self.results[0].newer)
        self.assertFalse(self.errors)
        self.assertIsNone(checker.reply)
        self.assertTrue(reply.deleted)
        self.assertFalse(checker.timer.isActive())

    def test_errors_allow_retry(self):
        for status in [404, 403, 429, 500, None]:
            self.setUp()
            reply = Reply(status=status)
            checker = self.checker(reply)
            checker.check(); reply.finished.emit()
            self.assertEqual(len(self.errors), 1)
            self.assertFalse(self.results)
            self.assertEqual(self.busy, [True, False])
            retry = Reply(status=status)
            checker.manager.get.return_value = retry
            checker.check(); retry.finished.emit()
            self.assertEqual(checker.manager.get.call_count, 2)

    def test_timeout(self):
        reply = Reply()
        checker = self.checker(reply)
        checker.check(); checker.timeout()
        self.assertIn('timed out', self.errors[0])
        self.assertIsNone(checker.reply)
