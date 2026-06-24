"""Access EEPROM through the Linux optoe driver sysfs interface."""

from __future__ import annotations

import os
from pathlib import Path

from ..constants import PAGE_OFFSET, PAGE_SELECT_OFFSET, PAGE_SIZE
from .base import EepromBackend


class OptoeSysfsBackend(EepromBackend):
    """
    Read/write via optoe ``eeprom`` sysfs file.

    Mirrors sonic-platform-common ``OptoeEepromReadWriteMixin``.
    """

    def __init__(
        self,
        eeprom_path: str | os.PathLike[str],
        *,
        write_max: int | None = None,
        write_timeout_ms: int | None = None,
        max_bank_size: int | None = None,
    ) -> None:
        self.eeprom_path = Path(eeprom_path)
        if not self.eeprom_path.is_file():
            raise FileNotFoundError(f"EEPROM sysfs node not found: {self.eeprom_path}")

        if write_max is not None:
            self._write_sysfs_sibling("write_max", write_max)
        if write_timeout_ms is not None:
            self._write_sysfs_sibling("write_timeout", write_timeout_ms)
        if max_bank_size is not None:
            self._write_sysfs_sibling("max_bank_size", max_bank_size)

    def _sibling_path(self, name: str) -> Path:
        return self.eeprom_path.with_name(name)

    def _write_sysfs_sibling(self, name: str, value: int) -> None:
        path = self._sibling_path(name)
        if not path.exists():
            return
        try:
            current = int(path.read_text().strip())
            if current == value:
                return
        except (OSError, ValueError):
            pass
        path.write_text(str(value))

    def _get_current_page(self) -> int:
        data = self._read_raw(PAGE_SELECT_OFFSET, 1)
        return data[0]

    def _set_page0(self) -> None:
        self._write_raw(PAGE_SELECT_OFFSET, bytes([0x00]))

    def _read_raw(self, offset: int, size: int) -> bytes:
        with self.eeprom_path.open("rb", buffering=0) as handle:
            if (
                PAGE_OFFSET <= offset < PAGE_OFFSET + PAGE_SIZE
                and self._get_current_page() != 0
            ):
                self._set_page0()
            handle.seek(offset)
            data = handle.read(size)
        if len(data) != size:
            raise OSError(
                f"Short read from {self.eeprom_path}: requested {size}, got {len(data)}"
            )
        return data

    def _write_raw(self, offset: int, data: bytes) -> None:
        with self.eeprom_path.open("r+b", buffering=0) as handle:
            handle.seek(offset)
            handle.write(data)

    def read(self, offset: int, size: int) -> bytes:
        return self._read_raw(offset, size)

    def write(self, offset: int, data: bytes) -> None:
        self._write_raw(offset, data)

    def describe(self) -> str:
        return f"optoe sysfs {self.eeprom_path}"
