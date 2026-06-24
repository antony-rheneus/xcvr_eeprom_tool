"""Command-line interface."""

from __future__ import annotations

import sys

import click

from .backends.linux_i2c import LinuxI2cBackend
from .backends.optoe_sysfs import OptoeSysfsBackend
from .constants import CMIS_MODULE_PAGES, PAGE_SIZE
from .eeprom import CmisEeprom
from .format import hex_string, hexdump
from .paging import PagingError, parse_page


def _parse_addr(value: str) -> int:
    text = value.strip().lower()
    if text.startswith("0x"):
        return int(text, 16)
    return int(text, 16 if any(c in text for c in "abcdef") else 10)


def _build_eeprom(
    eeprom: str | None,
    device: str | None,
    bus: int | None,
    addr: str,
    flat_memory: bool,
    page_delay_ms: float,
) -> CmisEeprom:
    if eeprom:
        backend = OptoeSysfsBackend(eeprom)
    elif device or bus is not None:
        bus_path = device if device else f"/dev/i2c-{bus}"
        backend = LinuxI2cBackend(bus_path, _parse_addr(addr), page_delay_ms=page_delay_ms)
    else:
        raise click.UsageError(
            "Specify --eeprom for optoe sysfs, or --device / --bus for raw I2C access."
        )
    return CmisEeprom(backend, flat_memory=flat_memory)


def _device_options(func):
    options = [
        click.option(
            "--eeprom",
            type=click.Path(exists=True, dir_okay=False),
            help="Path to optoe sysfs eeprom node (e.g. /sys/.../eeprom)",
        ),
        click.option(
            "--device",
            "device",
            type=click.Path(exists=True, dir_okay=False),
            help="I2C bus device path (e.g. /dev/i2c-1)",
        ),
        click.option("--bus", type=int, help="I2C bus number (alternative to --device)"),
        click.option(
            "--addr",
            default="0x50",
            show_default=True,
            help="Module I2C address (default 0x50 / A0h)",
        ),
        click.option(
            "--flat-memory",
            is_flag=True,
            help="Module uses flat memory (only page 0 permitted)",
        ),
        click.option(
            "--page-delay-ms",
            default=5.0,
            show_default=True,
            help="Delay after page select on raw I2C (ms)",
        ),
    ]
    for opt in reversed(options):
        func = opt(func)
    return func


@click.group()
@click.version_option(package_name="cmis-eeprom-tool")
def main() -> None:
    """Standalone CMIS module EEPROM tool for Linux (no SONiC required)."""


@main.command("read")
@_device_options
@click.option(
    "-n",
    "--page",
    required=True,
    help="EEPROM page number (decimal, 0x hex, or 0o octal)",
)
@click.option(
    "-o",
    "--offset",
    type=click.IntRange(0, 255),
    required=True,
    help="Byte offset within the page",
)
@click.option(
    "-s",
    "--size",
    type=click.IntRange(1, 256),
    required=True,
    help="Number of bytes to read",
)
@click.option("--no-format", is_flag=True, help="Print raw hex string without hexdump")
def read_cmd(
    eeprom,
    device,
    bus,
    addr,
    flat_memory,
    page_delay_ms,
    page,
    offset,
    size,
    no_format,
) -> None:
    """Read CMIS EEPROM data (sfputil read-eeprom equivalent)."""
    try:
        api = _build_eeprom(eeprom, device, bus, addr, flat_memory, page_delay_ms)
        page_num = parse_page(page)
        data = api.read_page(page_num, offset, size)
    except (PagingError, OSError, RuntimeError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if no_format:
        click.echo(hex_string(data))
    else:
        click.echo(
            hexdump(data, base_offset=offset)
        )


@main.command("write")
@_device_options
@click.option("-n", "--page", required=True, help="EEPROM page number")
@click.option(
    "-o",
    "--offset",
    type=click.IntRange(0, 255),
    required=True,
    help="Byte offset within the page",
)
@click.option(
    "-d",
    "--data",
    required=True,
    help="Hex string to write (even number of digits)",
)
@click.option("--verify", is_flag=True, help="Read back and compare after write")
def write_cmd(
    eeprom,
    device,
    bus,
    addr,
    flat_memory,
    page_delay_ms,
    page,
    offset,
    data,
    verify,
) -> None:
    """Write CMIS EEPROM data."""
    try:
        payload = bytes.fromhex(data)
    except ValueError:
        click.echo("Error: --data must be an even-length hex string", err=True)
        sys.exit(1)

    try:
        api = _build_eeprom(eeprom, device, bus, addr, flat_memory, page_delay_ms)
        page_num = parse_page(page)
        api.write_page(page_num, offset, payload)
        if verify:
            readback = api.read_page(page_num, offset, len(payload))
            if readback != payload:
                click.echo(
                    "Error: verify failed\n"
                    f"  wrote: {hex_string(payload)}\n"
                    f"  read:  {hex_string(readback)}",
                    err=True,
                )
                sys.exit(1)
            click.echo("Write OK (verified)")
        else:
            click.echo("Write OK")
    except (PagingError, OSError, RuntimeError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.command("dump")
@_device_options
@click.option("-n", "--page", default=None, help="Dump one page only (default: common CMIS pages)")
def dump_cmd(eeprom, device, bus, addr, flat_memory, page_delay_ms, page) -> None:
    """Hexdump lower/upper pages (similar to sfputil eeprom hexdump)."""
    try:
        api = _build_eeprom(eeprom, device, bus, addr, flat_memory, page_delay_ms)
        pages = [parse_page(page)] if page is not None else CMIS_MODULE_PAGES

        for page_num in pages:
            if page_num == 0:
                click.echo("        Lower page 00h")
                lower = api.read_page(0, 0, PAGE_SIZE)
                click.echo(hexdump(lower, base_offset=0))
                click.echo("\n        Upper page 00h")
                upper = api.read_page(0, PAGE_SIZE, PAGE_SIZE)
                click.echo(hexdump(upper, base_offset=PAGE_SIZE))
            else:
                click.echo(f"\n        Upper page {page_num:02x}h")
                data = api.read_page(page_num, PAGE_SIZE, PAGE_SIZE)
                click.echo(hexdump(data, base_offset=PAGE_SIZE))
    except (PagingError, OSError, RuntimeError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.command("info")
@_device_options
def info_cmd(eeprom, device, bus, addr, flat_memory, page_delay_ms) -> None:
    """Print basic module identification from lower page."""
    try:
        api = _build_eeprom(eeprom, device, bus, addr, flat_memory, page_delay_ms)
        click.echo(f"Backend:      {api.describe()}")
        click.echo(f"Identifier:   0x{api.get_identifier():02x} ({api.get_module_type()})")
        rev = api.get_cmis_revision()
        if rev:
            click.echo(f"CMIS rev:     {rev}")
        click.echo(f"Vendor:       {api.get_vendor_name()}")
        click.echo(f"Part number:  {api.get_vendor_pn()}")
        click.echo(f"Serial:       {api.get_vendor_sn()}")
    except (PagingError, OSError, RuntimeError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
