import io
import zipfile

import pytest

from app.security.safe_zip import UnsafeZipError, open_zip
from tests.conftest import make_zip


def test_valid_zip_opens():
    zf = open_zip(make_zip({"sleep-export.csv": b"Id,Tz,From,To,Sched\n"}))
    assert "sleep-export.csv" in zf.namelist()


def test_path_traversal_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", b"x")
    with pytest.raises(UnsafeZipError, match="traversal"):
        open_zip(buf.getvalue())


def test_absolute_path_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("/etc/passwd", b"x")
    with pytest.raises(UnsafeZipError, match="traversal"):
        open_zip(buf.getvalue())


def test_zip_bomb_ratio_rejected():
    # 50 MB of zeros compresses extremely well -> suspicious ratio
    with pytest.raises(UnsafeZipError, match="ratio|size"):
        open_zip(make_zip({"a.csv": b"\0" * (50 * 1024 * 1024)}))


def test_not_a_zip_rejected():
    with pytest.raises(UnsafeZipError, match="valid ZIP"):
        open_zip(b"this is not a zip file")
