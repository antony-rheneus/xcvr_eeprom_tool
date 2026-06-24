"""Tests for CMIS paging translation."""

import pytest

from cmis_eeprom.paging import (
    PagingError,
    flat_to_i2c_location,
    flat_to_page_offset,
    page_offset_to_flat,
    parse_page,
)


class TestParsePage:
    def test_decimal(self):
        assert parse_page("16") == 16

    def test_hex(self):
        assert parse_page("0x10") == 16

    def test_octal(self):
        assert parse_page("0o20") == 16


class TestPageOffsetToFlat:
    def test_page0_lower(self):
        assert page_offset_to_flat(0, 0, 1) == 0
        assert page_offset_to_flat(0, 127, 1) == 127

    def test_page0_upper(self):
        assert page_offset_to_flat(0, 128, 16) == 128

    def test_page1_upper(self):
        assert page_offset_to_flat(1, 128, 16) == 256

    def test_nonzero_page_requires_high_offset(self):
        with pytest.raises(PagingError):
            page_offset_to_flat(1, 0, 1)

    def test_size_overflow(self):
        with pytest.raises(PagingError):
            page_offset_to_flat(0, 250, 10)

    def test_flat_memory_only_page0(self):
        with pytest.raises(PagingError):
            page_offset_to_flat(1, 128, 1, flat_memory=True)


class TestFlatToI2cLocation:
    def test_lower_page(self):
        assert flat_to_i2c_location(0) == (0, 0)
        assert flat_to_i2c_location(127) == (0, 127)

    def test_page0_upper(self):
        assert flat_to_i2c_location(128) == (0, 128)
        assert flat_to_i2c_location(255) == (0, 255)

    def test_page1_upper(self):
        assert flat_to_i2c_location(256) == (1, 128)
        assert flat_to_i2c_location(383) == (1, 255)


class TestFlatToPageOffset:
    def test_roundtrip(self):
        for page, offset in [(0, 0), (0, 128), (1, 128), (0x10, 200)]:
            flat = page_offset_to_flat(page, offset, 1)
            assert flat_to_page_offset(flat) == (page, offset)
