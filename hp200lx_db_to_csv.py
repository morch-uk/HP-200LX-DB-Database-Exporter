#!/usr/bin/env python3
"""Read HP 100LX/200LX GDB/PDB/NDB databases and export to CSV or text.

Pure Python 3 (standard library only); read-only access to the database.

Based on OGASA's DB2CSV.C (1999) and Gerhard Gonter's HP200LX::DB (2001):
https://github.com/laurentd75/hp200lx-db-1

The HP200LX::DB decrypt_data implementation credits Curtis Cameron's dbcheck.
The legacy algorithm recovers a session key directly from the on-disk
password record. Password input is not required to read supported databases.

This is a *read-only exporter*, not an implementation of the original HP
database API. Supports unencrypted and password-protected generic
GDB/PDB/NDB databases, including linked Note fields. Other application
databases and exotic field types are not yet supported.
"""

from __future__ import annotations

import argparse
import csv
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


# HP record types. 0 = database header; 6 = field definition;
# 9 = Note text; 11 = data item; 31 = record lookup table.
RECORD_HEADER = struct.Struct("<BBHH")  # type, status, length, index
FILE_HEADER = struct.Struct("<HBBHHIBBBHH")
LOOKUP_ENTRY = struct.Struct("<HHBBH")
FIELD_HEADER = struct.Struct("<BBHBH")  # type, ID, offset, flags, reserved
SUPPORTED_FILE_TYPES = {0x44: "GDB/PDB", 0x4E: "NDB"}

# Types 11, 12, 14 and 15 describe GUI elements, not user data fields.
NON_DATA_FIELD_TYPES = {11, 12, 14, 15}


# Legacy HP 100LX/200LX record scrambling constants, from Gerhard Gonter's
# HP200LX::DB / Curtis Cameron's dbcheck implementation. These are not
# user data and are common to the original file format. This is XOR-based
# obfuscation, not modern cryptographic protection.
CRYPT_A = bytes([
    0xe8, 0xa3, 0xfe, 0x1b, 0x02, 0xce, 0x40, 0x35,
    0xa4, 0x7b, 0xf2, 0xa1, 0x70, 0xd5, 0x40, 0x65,
    0x09, 0x42, 0x23, 0xff, 0xaa, 0xed, 0xf0, 0x2a,
    0xa2, 0xa9, 0x38, 0xd7, 0xe5, 0x95, 0xea, 0x8c,
    0x46, 0xdd, 0x90, 0x94, 0x5e, 0x6b, 0x5d, 0xa4,
    0x7b, 0x8c, 0xea, 0x24, 0xa1, 0x7c, 0xaf, 0x30,
    0x62, 0x2a, 0xa5, 0x8e, 0xad, 0x67, 0xde, 0x3f,
    0xb3, 0xe3, 0x53, 0xde, 0x19, 0x42, 0xf8, 0x40,
    0x96, 0xe8, 0x15, 0x75, 0x43, 0x08, 0x2f, 0xe9,
    0xb1, 0x4f, 0x1d, 0xd5, 0xa9, 0x16, 0x2c, 0xfb,
    0x9f, 0x0f, 0xb2, 0xcc, 0xe4, 0x27, 0xbc, 0x1b,
    0x49, 0xa6, 0x90, 0x79, 0x03, 0x9a, 0xa6, 0x1a,
    0x70, 0x89, 0x9d, 0x35, 0x81, 0xad, 0x80, 0xb0,
    0x79, 0x45, 0x21, 0x5f, 0x94, 0x1c, 0xd1, 0x3f,
    0xdf, 0xa8, 0xa3, 0x40, 0x31, 0x34, 0x66, 0x84,
    0x85, 0x28, 0xf1, 0x8d, 0x82, 0x04, 0xa4,
])
CRYPT_B = bytes([
    0x09, 0x0b, 0x09, 0x0f, 0x09, 0x0b, 0x09, 0x77,
    0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08,
    0x78,
])
assert len(CRYPT_A) == 127 and len(CRYPT_B) == 17


class GDBError(ValueError):
    """File was invalid or uses a feature this tool cannot safely read."""


@dataclass(frozen=True)
class Record:
    type: int
    index: int
    status: int
    payload: bytes
    position: int


@dataclass(frozen=True)
class Field:
    name: str
    type: int
    offset: int
    index: int


def u16(buffer: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(buffer):
        raise GDBError(f"16-bit value at offset {offset} is out of bounds")
    return struct.unpack_from("<H", buffer, offset)[0]


def read_string(buffer: bytes, offset: int, encoding: str) -> str:
    if offset < 0 or offset >= len(buffer):
        raise GDBError(f"String offset {offset} outside data record")
    end = buffer.find(b"\x00", offset)
    if end < 0:
        raise GDBError("Unterminated string in database record")
    return buffer[offset:end].decode(encoding, errors="strict")


def decrypt_payload(payload: bytes, session_key: bytes) -> bytes:
    """Decrypt one HP database record payload (record header is NOT scrambled).

    The stream resets at the start of every record. The extra 127-byte
    rounds must be applied to long Note records; omitting them appears to
    work for short fields, but corrupts long records.
    """
    if len(session_key) != 17:
        raise GDBError("Invalid legacy session key length")
    result = bytearray(len(payload))
    # Accumulate the 17-byte correction table at every 127-byte boundary.
    extra = bytearray(len(payload))
    for i, value in enumerate(payload):
        if i >= 127:
            extra[i] = CRYPT_B[(i - 127) % 17] ^ extra[i - 127]
        result[i] = value ^ session_key[i % 17] ^ CRYPT_A[i % 127] ^ extra[i]
    return bytes(result)


def decrypt_records(records_by_type: dict[int, list[Record]]) -> None:
    """Decrypt supported protected database records in memory, never on disk."""
    passwords = records_by_type.get(1, [])
    if not passwords:
        return
    if len(passwords) != 1 or len(passwords[0].payload) != 17:
        raise GDBError("Unsupported HP password record layout")
    key = bytes(
        value ^ index ^ CRYPT_A[index]
        for index, value in enumerate(passwords[0].payload)
    )
    # HP System Manager scrambles only record payloads with type > 1.
    # Type 0 is the file header and type 1 stores the obfuscated session key.
    for kind, records in records_by_type.items():
        if kind <= 1:
            continue
        records_by_type[kind] = [
            Record(r.type, r.index, r.status, decrypt_payload(r.payload, key), r.position)
            for r in records
        ]


def parse_file(raw: bytes, encoding: str) -> tuple[list[Field], list[dict[str, str]], str, int]:
    """Return fields, data rows, HP file type and number of Note records."""
    if len(raw) < 29 or raw[:4] != b"hcD\x00":
        raise GDBError("Not an HP 100LX/200LX database (missing hcD header)")

    header_type, _, header_size, header_index = RECORD_HEADER.unpack_from(raw, 4)
    if (header_type, header_size, header_index) != (0, 25, 0):
        raise GDBError("Unexpected HP database header layout")

    (
        _version, file_type, _file_status, _viewpoint, record_count,
        table_offset, _year, _month, _day, _minute, _hash,
    ) = FILE_HEADER.unpack_from(raw, 10)
    if file_type not in SUPPORTED_FILE_TYPES:
        raise GDBError(f"Unsupported HP application database type: 0x{file_type:02X}")
    if not 29 <= table_offset <= len(raw) - 6:
        raise GDBError("Invalid database lookup-table location")
    if record_count > (len(raw) - table_offset - 6) // LOOKUP_ENTRY.size:
        raise GDBError("Record lookup table is truncated")

    table_type, _, table_size, _ = RECORD_HEADER.unpack_from(raw, table_offset)
    if table_type != 31 or table_size != 6 + 8 * record_count:
        raise GDBError("Unexpected database lookup-table layout")
    if table_offset + table_size + 64 > len(raw):
        raise GDBError("Database type-first lookup table is truncated")

    by_type: dict[int, list[Record]] = {}
    seen: set[tuple[int, int]] = set()
    for i in range(record_count):
        item_offset = table_offset + 6 + i * LOOKUP_ENTRY.size
        stored_size, _filters, _flags, offset_low, offset_high = LOOKUP_ENTRY.unpack_from(
            raw, item_offset
        )
        offset = offset_high * 256 + offset_low
        if stored_size == 0 and offset == 0:
            continue  # unused entry, e.g. a deleted or absent note
        if stored_size < 6 or offset < 4 or offset + stored_size > table_offset:
            raise GDBError(f"Record lookup entry {i} has an invalid location/size")

        typ, status, length, idx = RECORD_HEADER.unpack_from(raw, offset)
        if length != stored_size:
            raise GDBError(f"Record {i} length disagrees with lookup table")
        if (typ, idx) in seen:
            raise GDBError(f"Duplicate record type={typ}, index={idx}")
        seen.add((typ, idx))
        by_type.setdefault(typ, []).append(
            Record(typ, idx, status, raw[offset + 6:offset + length], offset)
        )

    decrypt_records(by_type)

    fields: list[Field] = []
    for rec in sorted(by_type.get(6, []), key=lambda r: r.index):
        data = rec.payload
        if len(data) < 7:
            raise GDBError("Truncated field definition")
        kind, _field_id, position, _flags, _reserved = FIELD_HEADER.unpack_from(data)
        if kind in NON_DATA_FIELD_TYPES:
            continue
        if kind not in {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 13}:
            raise GDBError(f"Unsupported field type {kind} in field #{rec.index}")
        name_raw = data[7:].split(b"\x00", 1)[0].replace(b"&", b"")
        name = name_raw.decode(encoding, "strict").strip()
        if not name:
            raise GDBError(f"Field definition #{rec.index} has no name")
        fields.append(Field(name, kind, position, rec.index))

    if not fields:
        raise GDBError("No readable user-defined fields found")
    names = [field.name for field in fields]
    if len(names) != len(set(names)):
        raise GDBError("Duplicate field names need manual disambiguation")

    notes = {r.index: r.payload for r in by_type.get(9, [])}
    rows: list[dict[str, str]] = []

    for record in sorted(by_type.get(11, []), key=lambda r: r.index):
        data = record.payload
        values: dict[str, str] = {}
        radio_counts: Counter[int] = Counter()
        for field in fields:
            kind, pos = field.type, field.offset
            if kind == 13:
                # Multiline text (rare): stored via a 16-bit offset like STRING.
                kind = 2
            if kind == 0:
                if pos >= len(data):
                    raise GDBError(f"Truncated boolean in data record {record.index}")
                value = "1" if data[pos] else "0"
            elif kind == 1:
                value = "1" if u16(data, pos) else "0"
            elif kind in {2, 3, 4, 5, 6}:
                string_pos = u16(data, pos)
                value = read_string(data, string_pos, encoding)
            elif kind == 7:
                minutes = u16(data, pos)
                value = "" if minutes in {32768, 65535} else f"{minutes // 60}:{minutes % 60:02d}"
            elif kind == 8:
                if pos + 3 > len(data):
                    raise GDBError(f"Truncated date in data record {record.index}")
                year, month, day = data[pos:pos + 3]
                value = "" if (year, month, day) == (255, 255, 255) else (
                    f"{1900 + year:04d}-{month + 1:02d}-{day + 1:02d}"
                )
            elif kind == 9:
                # Radio controls sharing a byte are numbered in field order.
                radio_counts[pos] += 1
                value = "1" if data[pos] == radio_counts[pos] else "0"
            elif kind == 10:
                note_number = u16(data, pos)
                if note_number == 0xFFFF:
                    value = ""
                elif note_number not in notes:
                    raise GDBError(
                        f"Data record {record.index} points to absent Note #{note_number}"
                    )
                else:
                    value = notes[note_number].decode(encoding, "strict")
            else:
                raise GDBError(f"Unimplemented field type: {kind}")
            values[field.name] = value
        rows.append(values)

    return fields, rows, SUPPORTED_FILE_TYPES[file_type], len(notes)


def text_export(fields: list[Field], rows: list[dict[str, str]], output: Path) -> None:
    """Write labelled, readable records without changing field content."""
    with output.open("w", encoding="utf-8-sig", newline="\n") as stream:
        for number, record in enumerate(rows, start=1):
            stream.write(f"Record {number} of {len(rows)}\n")
            stream.write("=" * 48 + "\n")
            for field in fields:
                value = record[field.name]
                # Keep the original field names and preserve all note line breaks.
                value = value.replace("\r\n", "\n").replace("\r", "\n")
                if "\n" in value or field.type == 10:
                    stream.write(f"{field.name}:\n")
                    if value:
                        stream.write(value)
                        if not value.endswith("\n"):
                            stream.write("\n")
                else:
                    stream.write(f"{field.name}: {value}\n")
            stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export an HP 100LX/200LX GDB/PDB/NDB database (including password-protected files) to UTF-8 CSV or TXT"
    )
    parser.add_argument("database", type=Path, help="Input .GDB, .PDB or .NDB file")
    parser.add_argument(
        "output", type=Path, nargs="?",
        help="Output path (e.g. notes.csv or notes.txt); default: input.csv",
    )
    parser.add_argument(
        "--format", choices=("csv", "txt"),
        help="Export format (normally detected from output extension; defaults to csv)",
    )
    parser.add_argument(
        "--encoding", default="cp437",
        help="DOS text codepage in input (default: cp437; try cp850 if accented characters look wrong)",
    )
    parser.add_argument(
        "--note-newlines", choices=("keep", "space", "dollar"), default="keep",
        help="Keep actual Note newlines, replace with spaces, or replace with $! (default: keep)",
    )
    parser.add_argument(
        "--excel-safe", action="store_true",
        help="In CSV output, protect cells beginning with =, +, -, @ from Excel formula execution",
    )
    args = parser.parse_args()
    source: Path = args.database
    output_format = args.format or ("txt" if args.output and args.output.suffix.lower() == ".txt" else "csv")
    output: Path = args.output or source.with_suffix("." + output_format)
    if source.resolve() == output.resolve():
        parser.error("Input and output must be different files")
    try:
        fields, rows, app_type, note_count = parse_file(source.read_bytes(), args.encoding)
        for row in rows:
            for field in fields:
                value = row[field.name]
                if field.type == 10:
                    if args.note_newlines == "space":
                        value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
                    elif args.note_newlines == "dollar":
                        value = value.replace("\r\n", "$!").replace("\r", "$!").replace("\n", "$!")
                    else:
                        value = value.replace("\r\n", "\n").replace("\r", "\n")
                if output_format == "csv" and args.excel_safe and value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                row[field.name] = value

        if output_format == "txt":
            text_export(fields, rows, output)
        else:
            with output.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[f.name for f in fields], lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(rows)
    except (OSError, LookupError, UnicodeError, GDBError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Input:   {source} ({app_type} structure)")
    print(f"Output:  {output} ({output_format.upper()})")
    print(f"Records: {len(rows)}")
    print(f"Notes:   {note_count}")
    print(f"Fields:  {', '.join(f.name for f in fields)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
