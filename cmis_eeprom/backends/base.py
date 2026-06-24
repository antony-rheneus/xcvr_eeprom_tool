"""Abstract EEPROM backend."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EepromBackend(ABC):
    """Read/write raw module EEPROM bytes."""

    @abstractmethod
    def read(self, offset: int, size: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, offset: int, data: bytes) -> None:
        raise NotImplementedError

    def read_byte(self, offset: int) -> int:
        return self.read(offset, 1)[0]

    def write_byte(self, offset: int, value: int) -> None:
        self.write(offset, bytes([value & 0xFF]))

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError
