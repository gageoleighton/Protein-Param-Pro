"""Non-blocking, manual checks for the latest public GitHub release."""

import json
from dataclasses import dataclass
from urllib.parse import quote

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from app_info import APP_VERSION, APP_WEBSITE

RELEASE_API = 'https://api.github.com/repos/gageoleighton/Protein-Param-Pro/releases/latest'


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    newer: bool


def parse_release(payload: bytes, current: str = APP_VERSION) -> Release:
    try:
        data = json.loads(payload)
        if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
            raise ValueError
        tag = data['tag_name']
        if not isinstance(tag, str):
            raise ValueError
        version = Version(tag)
        if version.is_prerelease or version.is_devrelease:
            raise ValueError
        return Release(str(version), f'{APP_WEBSITE}/releases/tag/{quote(tag, safe="")}',
                       version > Version(current))
    except (ValueError, TypeError, KeyError, InvalidVersion) as exc:
        raise ValueError('GitHub returned an unrecognized release. Please check the releases page.') from exc


class UpdateChecker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.reply = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.timeout)
        self.timed_out = False

    def check(self):
        if self.reply is not None:
            return
        request = QNetworkRequest(QUrl(RELEASE_API))
        request.setRawHeader(b'Accept', b'application/vnd.github+json')
        request.setRawHeader(b'User-Agent', f'ProteinParamPro/{APP_VERSION}'.encode())
        request.setRawHeader(b'X-GitHub-Api-Version', b'2022-11-28')
        request.setTransferTimeout(15000)
        self.timed_out = False
        self.reply = self.manager.get(request)
        self.reply.finished.connect(self.finish)
        self.busy_changed.emit(True)
        self.timer.start()

    def timeout(self):
        if self.reply is not None:
            self.timed_out = True
            self.reply.abort()

    def finish(self):
        reply = self.reply
        self.reply = None
        self.timer.stop()
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if self.timed_out:
                raise ValueError('The update check timed out. Please try again later.')
            if status == 404:
                raise ValueError('No published release was found on GitHub.')
            if status in (403, 429):
                raise ValueError('GitHub limited or denied the update request. Please try again later.')
            if reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
                raise ValueError('Could not reach GitHub. Check your internet connection and try again.')
            result = parse_release(bytes(reply.readAll()))
        except ValueError as exc:
            self.busy_changed.emit(False)
            self.failed.emit(str(exc))
        else:
            self.busy_changed.emit(False)
            self.completed.emit(result)
        finally:
            reply.deleteLater()
