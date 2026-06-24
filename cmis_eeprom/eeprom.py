"""High-level CMIS EEPROM read/write API."""

from __future__ import annotations

from .backends.base import EepromBackend
from .constants import (
    CMIS_IDENTIFIER,
    PAGE_SIZE,
    QSFP_DD_IDENTIFIER,
    SFF8472_IDENTIFIER,
    SFF8636_IDENTIFIER,
)
from .paging import page_offset_to_flat


class CmisEeprom:
    """Page-oriented CMIS EEPROM accessor."""

    def __init__(self, backend: EepromBackend, *, flat_memory: bool = False) -> None:
        self.backend = backend
        self.flat_memory = flat_memory

    def read_page(self, page: int, offset: int, size: int) -> bytes:
        flat = page_offset_to_flat(page, offset, size, flat_memory=self.flat_memory)
        return self.backend.read(flat, size)

    def write_page(self, page: int, offset: int, data: bytes) -> None:
        flat = page_offset_to_flat(page, offset, len(data), flat_memory=self.flat_memory)
        self.backend.write(flat, data)

    def read_flat(self, offset: int, size: int) -> bytes:
        return self.backend.read(offset, size)

    def write_flat(self, offset: int, data: bytes) -> None:
        self.backend.write(offset, data)

    def get_identifier(self) -> int:
        return self.backend.read_byte(0)

    def get_module_type(self) -> str:
        ident = self.get_identifier()
        mapping = {
            CMIS_IDENTIFIER: "CMIS",
            QSFP_DD_IDENTIFIER: "QSFP-DD (CMIS)",
            SFF8636_IDENTIFIER: "SFF-8636",
            SFF8472_IDENTIFIER: "SFF-8472",
        }
        return mapping.get(ident, f"unknown (0x{ident:02x})")

    def get_cmis_revision(self) -> str | None:
        if self.get_identifier() not in (CMIS_IDENTIFIER, QSFP_DD_IDENTIFIER):
            return None
        rev = self.backend.read_byte(1)
        major = (rev >> 4) & 0xF
        minor = rev & 0xF
        return f"{major}.{minor}"

    def get_vendor_name(self) -> str:
        data = self.read_page(0, 129, 16)
        return data.decode("ascii", errors="ignore").strip()

    def get_vendor_pn(self) -> str:
        data = self.read_page(0, 148, 16)
        return data.decode("ascii", errors="ignore").strip()

    def get_vendor_sn(self) -> str:
        data = self.read_page(0, 166, 16)
        return data.decode("ascii", errors="ignore").strip()

    def dump_page(self, page: int) -> bytes:
        if page == 0:
            lower = self.read_page(0, 0, PAGE_SIZE)
            upper = self.read_page(0, PAGE_SIZE, PAGE_SIZE)
            return lower + upper
        return self.read_page(page, PAGE_SIZE, PAGE_SIZE)

    def describe(self) -> str:
        return self.backend.describe()
