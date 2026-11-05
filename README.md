# HP 100LX / 200LX Database to CSV and Text Converter

A standalone Python 3 utility for exporting supported **HP 100LX / HP 200LX** System Manager database files to modern, readable **CSV** or **plain-text (`.txt`)** files.

The script is named [`hp200lx_db_to_csv.py`](hp200lx_db_to_csv.py). Despite its name, it exports **both CSV and TXT**.

- Runs on Windows, macOS, and Linux with Python 3.
- Uses **only the Python standard library**; no packages to install.
- Reads the database **without modifying the original file**.
- Exports field names, data records, and linked **Note** text.
- Accepts supported **unencrypted and password-protected** `.GDB`, `.PDB`, and `.NDB` database structures.
- Outputs UTF-8 (with a BOM for compatibility with Microsoft Excel).

> **Important:** This is an independent, read-only exporter, not an HP System Manager emulator or a fully general-purpose HP database implementation. Not every HP palmtop application file is supported. Keep a copy of your original database.

## Requirements

- Python **3.9 or newer** is recommended. The script has no third-party dependencies.
- A supported database file (unencrypted or password-protected) copied from an HP 100LX / 200LX or its storage card.
- The file `hp200lx_db_to_csv.py` from this repository.

Check Python is installed:

```powershell
python --version
```

On systems where `python` is not available, try `py` (Windows) or `python3` (macOS/Linux).

## Quick start

1. Copy `hp200lx_db_to_csv.py` and the database file into the same directory.
2. Open a terminal/PowerShell window in that directory.
3. Run one of the commands below.

**Convert to CSV (the default):**

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB
```

Creates `CONTACTS.csv` in the same directory.

**Convert to readable plain text:**

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB CONTACTS.txt
```

Creates `CONTACTS.txt` with each record and field clearly labelled.

**On macOS/Linux**, substitute `python3` for `python` if needed:

```bash
python3 hp200lx_db_to_csv.py CONTACTS.GDB CONTACTS.txt
```

The input file is not altered. **Existing output files can be overwritten**, so choose a new output filename when appropriate.

### Password-protected databases

Password-protected HP 100LX/200LX generic database files are decrypted **automatically in memory** before export. No password entry or extra command-line option is needed for this historical scheme, because the original file stores enough information to recover its 17-byte session key. For example:

```powershell
python hp200lx_db_to_csv.py PROTECTED.NDB exported.txt
```

The exported text/CSV is **not encrypted**. Treat it as sensitive and never publish anyone else's personal data. The original protected file remains unchanged.

> This is compatibility with a weak, historical XOR-based record-scrambling scheme, not a general password cracker for modern formats. It does not mean other HP application formats, such as Lotus 1-2-3, Memo, Pocket Quicken, or arbitrary encrypted files, are supported.

## Command-line usage

```text
python hp200lx_db_to_csv.py [OPTIONS] DATABASE [OUTPUT]
```

| Argument / option | Description |
| --- | --- |
| `DATABASE` | Required input database filename or path (`.GDB`, `.PDB`, `.NDB`, or another name containing a supported HP database structure). |
| `OUTPUT` | Optional output filename/path. If omitted, uses the input name with a `.csv` extension (or `.txt` if `--format txt` is specified). |
| `--format csv` | Force CSV output. |
| `--format txt` | Force plain-text output. |
| `--encoding CODEPAGE` | Character encoding of text in the source database; default `cp437`. Try `cp850` for some Western European files. |
| `--note-newlines keep` | Preserve Note field line breaks (default). |
| `--note-newlines space` | Convert Note field line breaks to spaces. |
| `--note-newlines dollar` | Convert Note field line breaks to `$!`, matching a convention supported by the original DB2CSV utility. |
| `--excel-safe` | For CSV output only, prefix field values starting with `=`, `+`, `-`, or `@` (ignoring leading whitespace) with an apostrophe to reduce spreadsheet formula-injection risk. This changes the exported values, not the source database. |
| `-h`, `--help` | Display the built-in help message. |

Without `--format`, a filename ending in `.txt` selects text output; all other output names select CSV. An explicit `--format` takes precedence over the output extension. For clarity, keep the extension consistent with the format.

## More examples

### Choose a CSV output filename

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB exported_contacts.csv
```

### Force TXT output without specifying its filename

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB --format txt
```

Creates `CONTACTS.txt`.

### Export a `.NDB` file

```powershell
python hp200lx_db_to_csv.py NOTES.NDB NOTES.txt
```

The file's *internal type marker* matters more than its extension. Some `.GDB`-named files may actually contain an NDB-style structure. The converter recognises the supported internal markers and reports the structure it found.

### Use a different DOS character set

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB CONTACTS.csv --encoding cp850
```

For international text, compare results produced with `cp437` and `cp850` if accented letters appear incorrect. The source data is not changed.

### Replace Note line breaks with `$!`

```powershell
python hp200lx_db_to_csv.py NOTES.NDB NOTES.csv --note-newlines dollar
```

For example, a Note containing two lines is exported as `First line$!Second line` in the CSV cell. This option affects **Note fields only**.

### Reduce spreadsheet formula risks

```powershell
python hp200lx_db_to_csv.py CONTACTS.GDB CONTACTS.csv --excel-safe
```

Use this option if you intend to open CSV files from untrusted sources in Excel or another spreadsheet program. It is an export-time safety measure, not a guarantee against all spreadsheet risks.

## Output formats

### CSV

The CSV file has one column per supported database field and one row per exported data record. The first row contains the original field names. Note contents can occupy multiline quoted CSV cells when `--note-newlines keep` is used.

Illustrative example **using invented data**:

```csv
Title,Note,Category
Test entry,"First line
Second line",Example
```

CSV uses standard quoting and CRLF record terminators. Output text is encoded as UTF-8 with BOM so that Excel is more likely to detect Unicode correctly.

> Multiline CSV fields are valid CSV. Opening a CSV in a plain-text editor may therefore make one database record appear to span multiple lines.

### TXT

Plain-text output presents each record separately, followed by its field values. Note text is displayed on its own lines.

Illustrative example **using invented data**:

```text
Record 1 of 2
================================================
Title: Test entry
Note:
First line
Second line
Category: Example

Record 2 of 2
================================================
Title: Another entry
Note:
An additional note
Category: Example
```

The script uses whatever field names are defined in the input database; `Title`, `Note` and `Category` are just examples, **not fixed requirements**. TXT output is UTF-8 with BOM and LF line endings.

## Conversion summary

After a successful export, the program prints a report similar to:

```text
Input:   CONTACTS.GDB (GDB/PDB structure)
Output:  CONTACTS.csv (CSV)
Records: 42
Notes:   15
Fields:  Name, Address, Telephone, Note
```

*Numbers and field names above are illustrative, not expected values.* The `Notes` figure counts Note records stored in the file; it is not necessarily the number of data records with nonempty Note fields. A successful result is **not** a byte-for-byte backup or proof that every obscure database feature has been reproduced.

## Supported data and current limitations

The script recognises the HP `hcD` database signature and supported GDB/PDB (`0x44`) and NDB (`0x4E`) internal type markers. It reads field definitions, data records, and separately stored Note records using the database's internal lookup table. For password-protected files, it reconstructs the original HP session key from a type-1 password record and decodes each record payload with the legacy algorithm.

Supported field handling includes common text, numeric-text, checkbox/boolean, radio-button, time, date, and Note fields. Values are exported as text. The parser also skips known GUI-only field definitions.

**Not supported or not guaranteed:**

- Password schemes other than the supported legacy HP generic-database password record (type 1, 17-byte payload). Unsupported password layouts are rejected.
- Other application database types outside the supported internal markers.
- Every unusual/undocumented field representation or damaged/corrupt database; the converter raises an error for unsupported layouts instead of silently discarding data.
- Writing changes back to `.GDB`/`.PDB`/`.NDB` or reconstructing the original file from a CSV/TXT export.
- Preserving System Manager views, indexes, GUI layout, deleted entries, application-specific metadata, or the exact on-device display order. Exported data records are ordered by internal record index.
- Exact interpretation of every historical date/time or locale-specific field format. Check these values against the original application when accuracy matters.

**Text encoding:** Source strings are decoded using the selected DOS code page (`cp437` by default). A wrong code page may produce incorrect characters or a decoding error.

**Original safety:** The input is only read. However, the destination file is opened for writing and will be **replaced if it already exists**. Keep both the source and any existing exports backed up.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| `python` is not recognised | Install Python 3, then try `py` on Windows or `python3` on macOS/Linux. |
| `No such file or directory` / `FileNotFoundError` | Check the working directory and filenames. Use quoted paths if they contain spaces. |
| `Not an HP 100LX/200LX database (missing hcD header)` | The input is not in the expected database format, or it may be compressed/encapsulated/damaged. |
| `Unsupported HP application database type` | The file uses a different internal HP application format; a `.GDB` extension alone is not sufficient. |
| `Unsupported HP password record layout` | The file does not use the 17-byte legacy password record supported by this converter. Try exporting through original software. |
| `Record ...`, `lookup table ...`, `Truncated ...`, or `Unsupported field type ...` | This may be a damaged, variant, or unimplemented record/field layout. Preserve the original file and retain the full error message for investigation. |
| Accented characters look wrong | Try `--encoding cp850` instead of the default `cp437` (or another appropriate Python-supported code page). |
| Notes appear on several physical lines in the CSV | This is normal for quoted multiline CSV cells. Use `--note-newlines space` or `dollar` if needed. |
| Excel treats a cell as a formula | Re-export using `--excel-safe`, especially for untrusted data. |
| The output has unexpected field names | Field names come from the source database's own definitions. |

### Windows example using full paths

```powershell
python "C:\Tools\hp200lx_db_to_csv.py" "D:\Palmtop Backup\CONTACTS.GDB" "D:\Exports\contacts.txt"
```

The target output directory must already exist.

## How it works (technical notes)

The converter is a standalone reader implemented with Python's `struct`, `csv` and standard file APIs. It:

1. Validates the HP `hcD` signature and database header.
2. Locates and checks the internal record lookup table.
3. When a legacy type-1 password record is present, reconstructs its session key and reverses the original per-record XOR encoding.
4. Parses field definitions, skipping recognised non-data controls.
5. Resolves data record values, including references to separately stored Note records.
6. Decodes source text using the selected DOS code page.
7. Writes CSV or labelled TXT in UTF-8.

Corrupt/truncated record references, missing linked notes, duplicate field names, and unsupported field types generally produce explicit errors rather than incomplete exports.

### Background and references

The Python implementation was informed by:

- **OGASA, `DB2CSV.C` / `DB2CSV.DOC`**, *DB2CSV ver. 0.2* (1999): HP System Manager database-to-CSV utility and field-conversion behaviour.
- **Gerhard Gonter, `HP200LX::DB`** (2001): documentation/implementation of the binary record layout and the legacy `decrypt_password`/`decrypt_data` algorithm; a copy is available at <https://github.com/laurentd75/hp200lx-db-1>. The source credits **Curtis Cameron's `dbcheck`** for the decryption method.

The Python utility does **not** require the original HP `lxapi.h`/`dbapi.h` libraries or an HP 200LX to run. The decryption routine and constant tables were adapted from the historical Perl implementation, which states that it is available under the same terms as Perl itself. Check the original attribution and licensing terms before distributing derivative code. No original owner's data, passwords, or sample databases should be included in a public repository.

## Testing and contributing

Development testing included paired, private encrypted and unencrypted copies of an HP palmtop NDB database: **68 data records**, **53 stored Note records**, and **three fields**. Both versions produced **byte-identical** CSV and TXT exports using the same options, including multiline Note fields. The real test database is intentionally excluded from the public package. This is a useful smoke test, **not a complete compatibility test** for all variants or all field types.

If you encounter a database the tool cannot read, please open a GitHub issue with:

- The command used and complete error message.
- The palmtop model and originating application, if known.
- The filename extension and expected field types, if known.
- A **small synthetic or anonymised test file** if you can create one.

**Please do not upload unredacted personal databases or old storage-card contents to public issues.** Such files can contain private information belonging to previous owners.

## Licence

A licence for this repository should be decided and added by its maintainer. **Do not assume that third-party historical code or documentation is automatically covered by a licence chosen for the Python script.** Review any incorporated source and attribution requirements before publishing.
