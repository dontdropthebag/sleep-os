"""Safe ZIP inspection.

Guards against path traversal, zip bombs (per-entry size, total size,
compression ratio, entry count) and symlink entries. Entries are read
in-memory only; nothing is ever extracted to disk.
"""

import io
import zipfile

from ..config import settings


class UnsafeZipError(ValueError):
    pass


def _validate_name(name: str) -> None:
    if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"):
        raise UnsafeZipError(f"Path traversal attempt in zip entry: {name!r}")


def open_zip(data: bytes) -> zipfile.ZipFile:
    if len(data) > settings.max_upload_bytes:
        raise UnsafeZipError("Upload exceeds size limit")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UnsafeZipError(f"Not a valid ZIP file: {e}") from e

    infos = zf.infolist()
    if len(infos) > settings.max_zip_entries:
        raise UnsafeZipError(f"ZIP has too many entries ({len(infos)})")

    total_uncompressed = 0
    for info in infos:
        _validate_name(info.filename)
        # Reject symlinks (upper 16 bits of external_attr hold unix mode)
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise UnsafeZipError(f"Symlink entry rejected: {info.filename!r}")
        if info.file_size > settings.max_zip_entry_bytes:
            raise UnsafeZipError(f"Entry too large: {info.filename!r}")
        if info.compress_size > 0:
            ratio = info.file_size / info.compress_size
            if ratio > settings.max_zip_compression_ratio and info.file_size > 1024 * 1024:
                raise UnsafeZipError(f"Suspicious compression ratio for {info.filename!r}")
        total_uncompressed += info.file_size
    if total_uncompressed > settings.max_zip_total_bytes:
        raise UnsafeZipError("Total decompressed size exceeds limit")
    return zf


def read_entry(zf: zipfile.ZipFile, name: str, limit: int | None = None) -> bytes:
    """Read one entry with a hard byte cap enforced during streaming."""
    limit = limit or settings.max_zip_entry_bytes
    out = io.BytesIO()
    with zf.open(name) as fh:
        while True:
            chunk = fh.read(1 << 16)
            if not chunk:
                break
            if out.tell() + len(chunk) > limit:
                raise UnsafeZipError(f"Entry {name!r} exceeded read limit while streaming")
            out.write(chunk)
    return out.getvalue()
