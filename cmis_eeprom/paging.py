"""Page/offset translation compatible with SONiC sfputil get_overall_offset_general()."""

from __future__ import annotations

from .constants import (
    MAX_EEPROM_OFFSET,
    MIN_OFFSET_FOR_NON_PAGE0,
    PAGE_SIZE,
)


class PagingError(ValueError):
    """Invalid page, offset, or size."""


def parse_page(value: str | int) -> int:
    """Accept decimal, 0x hex, or 0o octal page numbers."""
    if isinstance(value, int):
        page = value
    else:
        text = value.strip().lower()
        if text.startswith("0x"):
            page = int(text, 16)
        elif text.startswith("0o"):
            page = int(text, 8)
        else:
            page = int(text, 10)
    if page < 0 or page > 255:
        raise PagingError(f"Invalid page number {page:#x}, valid range [0, 0xff]")
    return page


def page_offset_to_flat(page: int, offset: int, size: int, *, flat_memory: bool = False) -> int:
    """
    Convert CMIS page + in-page offset to linear EEPROM offset.

    Matches sonic-utilities sfputil ``get_overall_offset_general()``.
    """
    if flat_memory and page != 0:
        raise PagingError(f"Invalid page number {page:#x}, flat-memory modules only support page 0")

    if page != 0 and offset < MIN_OFFSET_FOR_NON_PAGE0:
        raise PagingError(
            f"Invalid offset {offset} for page {page:#x}, valid range: [0x80, 0xff]"
        )

    if size + offset - 1 > MAX_EEPROM_OFFSET:
        raise PagingError(
            f"Invalid size {size}, valid range: [1, {MAX_EEPROM_OFFSET - offset + 1}]"
        )

    return page * PAGE_SIZE + offset


def flat_to_page_offset(flat_offset: int) -> tuple[int, int]:
    """Inverse of page_offset_to_flat for CMIS paged address space."""
    if flat_offset < PAGE_SIZE:
        return 0, flat_offset
    if flat_offset < PAGE_SIZE * 2:
        return 0, flat_offset
    page = (flat_offset - PAGE_SIZE) // PAGE_SIZE
    offset = PAGE_SIZE + (flat_offset % PAGE_SIZE)
    return page, offset


def flat_to_i2c_location(flat_offset: int) -> tuple[int, int]:
    """
    Map linear offset (optoe-style) to CMIS (page_select, i2c_register).

    Lower 128 bytes (flat 0-127) are always lower page 0.
    Upper regions use page select at register 127 and data at 128-255.
    """
    if flat_offset < PAGE_SIZE:
        return 0, flat_offset

    page = (flat_offset - PAGE_SIZE) // PAGE_SIZE
    reg = PAGE_SIZE + (flat_offset % PAGE_SIZE)
    return page, reg
