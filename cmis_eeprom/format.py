"""Hex dump formatting (compatible with sfputil output style)."""

from __future__ import annotations


def _ascii_char(byte: int) -> str:
    if 32 <= byte <= 126:
        return chr(byte)
    return "."


def hexdump(data: bytes, base_offset: int = 0, indent: str = "        ") -> str:
    """Format bytes as an sfputil-style hexdump."""
    lines: list[str] = []
    offset = 0
    size = len(data)
    mem_address = base_offset

    while size > 0:
        line_addr = f"{indent}{mem_address:08x}"
        if size >= 16:
            first = " ".join(f"{b:02x}" for b in data[offset : offset + 8])
            second = " ".join(f"{b:02x}" for b in data[offset + 8 : offset + 16])
            ascii_part = "".join(_ascii_char(b) for b in data[offset : offset + 16])
            lines.append(f"{line_addr} {first}  {second} |{ascii_part}|")
            size -= 16
            offset += 16
            mem_address += 16
            continue

        if size > 8:
            first = " ".join(f"{b:02x}" for b in data[offset : offset + 8])
            second = " ".join(f"{b:02x}" for b in data[offset + 8 : offset + size])
            padding = "   " * (16 - size)
            ascii_part = "".join(_ascii_char(b) for b in data[offset : offset + size])
            lines.append(f"{line_addr} {first}  {second}{padding} |{ascii_part}|")
        else:
            hex_part = " ".join(f"{b:02x}" for b in data[offset : offset + size])
            padding = "   " * (16 - size)
            ascii_part = "".join(_ascii_char(b) for b in data[offset : offset + size])
            lines.append(f"{line_addr} {hex_part}{padding} |{ascii_part}|")
        break

    return "\n".join(lines)


def hex_string(data: bytes) -> str:
    return "".join(f"{b:02x}" for b in data)
