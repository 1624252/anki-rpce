# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Full-sync direction rule for cross-device RPCE sync.

Regression guard for the bug where a freshly installed desktop (MSI) seeds its
own deck, then on first sync into an account that already holds another device's
data UPLOADED over it — wiping the account. A device must ADOPT (download) an
existing account on a first-join conflict, and only UPLOAD on a conflict once it
already owns the account (so content re-seeds still propagate)."""

from anki.sync_pb2 import SyncCollectionResponse as R
from aqt.rpce import _full_sync_direction


def test_download_when_server_ahead():
    # Server strictly newer / this device empty -> take the account.
    assert _full_sync_direction(R.FULL_DOWNLOAD, adopted=False) == "download"
    assert _full_sync_direction(R.FULL_DOWNLOAD, adopted=True) == "download"


def test_upload_when_server_empty():
    # Empty account -> seed it from this device (first ever upload).
    assert _full_sync_direction(R.FULL_UPLOAD, adopted=False) == "upload"
    assert _full_sync_direction(R.FULL_UPLOAD, adopted=True) == "upload"


def test_conflict_fresh_device_adopts_account():
    # THE BUG: both sides hold data. A device that has not adopted this account
    # yet must download (adopt) so it never clobbers the other device's data.
    assert _full_sync_direction(R.FULL_SYNC, adopted=False) == "download"


def test_conflict_owner_uploads_content():
    # A device that already owns the account uploads its (re-seeded) content.
    assert _full_sync_direction(R.FULL_SYNC, adopted=True) == "upload"
