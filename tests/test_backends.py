"""Tests with mocked backends."""

from pathlib import Path

import pytest

from cmis_eeprom.backends.optoe_sysfs import OptoeSysfsBackend
from cmis_eeprom.eeprom import CmisEeprom


class TestOptoeSysfsBackend:
    def test_read_write_roundtrip(self, tmp_path: Path):
        eeprom = tmp_path / "eeprom"
        memory = bytearray(512)
        eeprom.write_bytes(bytes(memory))

        backend = OptoeSysfsBackend(eeprom)
        backend.write(0, b"\x1e\x00")
        backend.write(128, b"\xab\xcd")
        assert backend.read(0, 2) == b"\x1e\x00"
        assert backend.read(128, 2) == b"\xab\xcd"

    def test_cmis_api(self, tmp_path: Path):
        eeprom = tmp_path / "eeprom"
        memory = bytearray(512)
        memory[0] = 0x1E
        memory[1] = 0x50
        memory[129:145] = b"VENDOR NAME HERE"
        eeprom.write_bytes(bytes(memory))

        api = CmisEeprom(OptoeSysfsBackend(eeprom))
        assert api.get_module_type() == "CMIS"
        assert api.get_cmis_revision() == "5.0"
        assert api.get_vendor_name() == "VENDOR NAME HERE"
