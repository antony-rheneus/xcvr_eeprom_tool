"""Direct CMIS paging over /dev/i2c-* without SONiC or optoe."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from ..constants import DEFAULT_I2C_ADDR, PAGE_SELECT_OFFSET, PAGE_SIZE
from ..paging import flat_to_i2c_location
from .base import EepromBackend


class LinuxI2cBackend(EepromBackend):
    """
    CMIS EEPROM access on a Linux I2C bus device.

    Uses smbus2 when installed, otherwise falls back to i2ctransfer(8).
    """

    def __init__(
        self,
        bus: int | str | os.PathLike[str],
        addr: int = DEFAULT_I2C_ADDR,
        *,
        page_delay_ms: float = 5.0,
        use_smbus2: bool = True,
    ) -> None:
        if isinstance(bus, int):
            self.bus_path = Path(f"/dev/i2c-{bus}")
            self.bus_num = bus
        else:
            self.bus_path = Path(bus)
            name = self.bus_path.name
            if not name.startswith("i2c-"):
                raise ValueError(f"Expected /dev/i2c-N path, got {self.bus_path}")
            self.bus_num = int(name.split("-", 1)[1])

        if not self.bus_path.exists():
            raise FileNotFoundError(f"I2C bus not found: {self.bus_path}")

        self.addr = addr
        self.page_delay_ms = page_delay_ms
        self._page_cache: int | None = None
        self._transport = self._select_transport(use_smbus2)

    def _select_transport(self, prefer_smbus2: bool) -> str:
        if prefer_smbus2:
            try:
                import smbus2  # noqa: F401

                return "smbus2"
            except ImportError:
                pass
        if _which("i2ctransfer"):
            return "i2ctransfer"
        raise RuntimeError(
            "No I2C transport available. Install smbus2 (pip install smbus2) "
            "or i2c-tools (i2ctransfer)."
        )

    def _set_page(self, page: int) -> None:
        if self._page_cache == page:
            return
        self._write_register(PAGE_SELECT_OFFSET, page)
        self._page_cache = page
        if self.page_delay_ms > 0:
            time.sleep(self.page_delay_ms / 1000.0)

    def _read_register(self, reg: int) -> int:
        return self._read_block(reg, 1)[0]

    def _write_register(self, reg: int, value: int) -> None:
        self._write_block(reg, bytes([value & 0xFF]))

    def _read_block(self, reg: int, size: int) -> bytes:
        if size <= 0:
            return b""

        if self._transport == "smbus2":
            import smbus2

            chunks: list[bytes] = []
            remaining = size
            cursor = reg
            with smbus2.SMBus(self.bus_num) as bus:
                while remaining > 0:
                    chunk = min(remaining, 32)
                    data = bus.read_i2c_block_data(self.addr, cursor, chunk)
                    chunks.append(bytes(data))
                    remaining -= chunk
                    cursor += chunk
            return b"".join(chunks)

        return self._i2ctransfer_read(reg, size)

    def _write_block(self, reg: int, data: bytes) -> None:
        if not data:
            return

        if self._transport == "smbus2":
            import smbus2

            cursor = reg
            offset = 0
            with smbus2.SMBus(self.bus_num) as bus:
                while offset < len(data):
                    chunk = data[offset : offset + 32]
                    bus.write_i2c_block_data(self.addr, cursor, list(chunk))
                    offset += len(chunk)
                    cursor += len(chunk)
            return

        self._i2ctransfer_write(reg, data)

    def _i2ctransfer_read(self, reg: int, size: int) -> bytes:
        addr_hex = f"0x{self.addr:02x}"
        chunks: list[bytes] = []
        remaining = size
        cursor = reg
        while remaining > 0:
            chunk = min(remaining, 32)
            cmd = [
                "i2ctransfer",
                "-y",
                str(self.bus_num),
                f"w1@{addr_hex}",
                f"0x{cursor:02x}",
                f"r{chunk}",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise OSError(
                    f"i2ctransfer read failed (reg={cursor:#x}, len={chunk}): "
                    f"{proc.stderr.strip() or proc.stdout.strip()}"
                )
            values = [int(x, 16) for x in proc.stdout.split()]
            if len(values) != chunk:
                raise OSError(
                    f"i2ctransfer short read at reg {cursor:#x}: expected {chunk}, got {len(values)}"
                )
            chunks.append(bytes(values))
            remaining -= chunk
            cursor += chunk
        return b"".join(chunks)

    def _i2ctransfer_write(self, reg: int, data: bytes) -> None:
        addr_hex = f"0x{self.addr:02x}"
        offset = 0
        cursor = reg
        while offset < len(data):
            chunk = data[offset : offset + 32]
            cmd = [
                "i2ctransfer",
                "-y",
                str(self.bus_num),
                f"w{1 + len(chunk)}@{addr_hex}",
                f"0x{cursor:02x}",
                *[f"0x{b:02x}" for b in chunk],
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode != 0:
                raise OSError(
                    f"i2ctransfer write failed (reg={cursor:#x}): "
                    f"{proc.stderr.strip() or proc.stdout.strip()}"
                )
            offset += len(chunk)
            cursor += len(chunk)

    def read(self, offset: int, size: int) -> bytes:
        if size <= 0:
            return b""

        out = bytearray()
        pos = offset
        remaining = size
        while remaining > 0:
            page, reg = flat_to_i2c_location(pos)
            if page == 0 and reg < PAGE_SIZE:
                chunk = min(remaining, PAGE_SIZE - reg)
            else:
                self._set_page(page)
                chunk = min(remaining, 256 - reg)

            out.extend(self._read_block(reg, chunk))
            pos += chunk
            remaining -= chunk
        return bytes(out)

    def write(self, offset: int, data: bytes) -> None:
        pos = offset
        remaining = len(data)
        data_offset = 0
        while remaining > 0:
            page, reg = flat_to_i2c_location(pos)
            if page == 0 and reg < PAGE_SIZE:
                chunk = min(remaining, PAGE_SIZE - reg)
            else:
                self._set_page(page)
                chunk = min(remaining, 256 - reg)

            self._write_block(reg, data[data_offset : data_offset + chunk])
            pos += chunk
            data_offset += chunk
            remaining -= chunk

    def describe(self) -> str:
        return f"I2C bus {self.bus_path} addr {self.addr:#04x} ({self._transport})"


def _which(cmd: str) -> str | None:
    for path in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path) / cmd
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None
