"""Core logic: parse, validate and split Luca journal voucher import files."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from itertools import groupby
from typing import Iterable, Iterator, List, Sequence

COLUMNS = [
    "Fiş No",
    "Fiş Tarihi",
    "Fiş Açıklama",
    "Hesap Kodu",
    "Evrak No",
    "Evrak Tarihi",
    "Detay Açıklama",
    "Borç",
    "Alacak",
    "Miktar",
    "Belge Türü",
    "Para Birimi",
    "Kur",
    "Döviz Tutar",
]

IDX_FIS_NO = 0
IDX_FIS_TARIHI = 1
IDX_HESAP = 3
IDX_EVRAK_NO = 4
IDX_EVRAK_TARIHI = 5
IDX_BORC = 7
IDX_ALACAK = 8

# Limits observed for Luca voucher imports. Both are configurable because they
# may change between Luca versions.
DEFAULT_MAX_VOUCHERS = 50
DEFAULT_MAX_ROWS = 10_000

_DATE_FORMATS = ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d")
_ACCOUNT_RE = re.compile(r"^\d+(\.\d+)*$")


@dataclass
class Issue:
    """A single validation problem. ``row`` is 1-based and counts the header."""

    row: int
    column: str
    message: str

    def __str__(self) -> str:
        return f"row {self.row} [{self.column}]: {self.message}"


@dataclass
class Voucher:
    number: str
    rows: List[List[str]] = field(default_factory=list)
    first_row: int = 0


def parse_amount(value: str) -> Decimal:
    """Parse an amount written in Turkish (1.234,56) or plain (1234.56) style.

    An empty string is treated as zero. Raises ValueError for anything else
    that is not a number.
    """
    text = (value or "").strip().replace(" ", "")
    if text == "":
        return Decimal("0")
    if "," in text and "." in text:
        # The last separator is the decimal one.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def parse_date(value: str) -> datetime:
    """Parse dd.mm.yyyy, dd/mm/yyyy or yyyy-mm-dd. Raises ValueError otherwise."""
    text = (value or "").strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"unsupported date: {value!r}")


def read_rows(
    path: str,
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
    has_header: bool = True,
) -> tuple[List[str] | None, List[List[str]]]:
    """Read a CSV file and return ``(header, rows)``."""
    with open(path, newline="", encoding=encoding) as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if has_header and all_rows:
        return all_rows[0], all_rows[1:]
    return None, all_rows


def group_vouchers(rows: Iterable[Sequence[str]], first_row: int = 2) -> Iterator[Voucher]:
    """Group consecutive rows that share a voucher number."""
    indexed = ((first_row + i, list(row)) for i, row in enumerate(rows))
    key = lambda item: (item[1][IDX_FIS_NO].strip() if item[1] else "")
    for number, items in groupby(indexed, key=key):
        items = list(items)
        yield Voucher(number=number, rows=[r for _, r in items], first_row=items[0][0])


def validate(
    rows: Sequence[Sequence[str]],
    max_vouchers: int = DEFAULT_MAX_VOUCHERS,
    max_rows: int = DEFAULT_MAX_ROWS,
    first_row: int = 2,
) -> List[Issue]:
    """Validate data rows (without header) and return every problem found."""
    issues: List[Issue] = []

    if len(rows) > max_rows:
        issues.append(Issue(0, "file", f"{len(rows)} rows exceed the limit of {max_rows}"))

    seen_numbers: dict[str, int] = {}
    vouchers = list(group_vouchers(rows, first_row))
    if len(vouchers) > max_vouchers:
        issues.append(
            Issue(0, "file", f"{len(vouchers)} vouchers exceed the limit of {max_vouchers}")
        )

    for index, row in enumerate(rows):
        line = first_row + index
        if len(row) != len(COLUMNS):
            issues.append(Issue(line, "columns", f"expected {len(COLUMNS)} columns, got {len(row)}"))
            continue

        for idx in (IDX_FIS_NO, IDX_HESAP, IDX_EVRAK_NO):
            if not row[idx].strip():
                issues.append(Issue(line, COLUMNS[idx], "must not be empty"))

        for idx in (IDX_FIS_TARIHI, IDX_EVRAK_TARIHI):
            if not row[idx].strip():
                issues.append(Issue(line, COLUMNS[idx], "must not be empty"))
            else:
                try:
                    parse_date(row[idx])
                except ValueError as exc:
                    issues.append(Issue(line, COLUMNS[idx], str(exc)))

        account = row[IDX_HESAP].strip()
        if account and not _ACCOUNT_RE.match(account):
            hint = " (trailing dot?)" if account.endswith(".") else ""
            issues.append(Issue(line, COLUMNS[IDX_HESAP], f"invalid account code {account!r}{hint}"))

        debit = credit = Decimal("0")
        for idx in (IDX_BORC, IDX_ALACAK):
            try:
                amount = parse_amount(row[idx])
            except ValueError as exc:
                issues.append(Issue(line, COLUMNS[idx], str(exc)))
                continue
            if amount < 0:
                issues.append(Issue(line, COLUMNS[idx], "must not be negative"))
            if idx == IDX_BORC:
                debit = amount
            else:
                credit = amount
        if debit > 0 and credit > 0:
            issues.append(Issue(line, "Borç/Alacak", "a row cannot have both debit and credit"))

    for voucher in vouchers:
        if voucher.number in seen_numbers:
            issues.append(
                Issue(
                    voucher.first_row,
                    COLUMNS[IDX_FIS_NO],
                    f"voucher {voucher.number} appears in separate blocks "
                    f"(first at row {seen_numbers[voucher.number]})",
                )
            )
        seen_numbers.setdefault(voucher.number, voucher.first_row)

        total_debit = total_credit = Decimal("0")
        for row in voucher.rows:
            if len(row) != len(COLUMNS):
                break
            try:
                total_debit += parse_amount(row[IDX_BORC])
                total_credit += parse_amount(row[IDX_ALACAK])
            except ValueError:
                break
        else:
            if total_debit != total_credit:
                issues.append(
                    Issue(
                        voucher.first_row,
                        "Borç/Alacak",
                        f"voucher {voucher.number} is unbalanced: "
                        f"debit {total_debit} != credit {total_credit}",
                    )
                )

    return issues


def split_vouchers(
    rows: Sequence[Sequence[str]],
    max_vouchers: int = DEFAULT_MAX_VOUCHERS,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> List[List[List[str]]]:
    """Split rows into chunks without ever breaking a voucher apart.

    Each chunk has at most ``max_vouchers`` vouchers and ``max_rows`` rows.
    A single voucher larger than ``max_rows`` raises ValueError.
    """
    chunks: List[List[List[str]]] = []
    current: List[List[str]] = []
    current_vouchers = 0

    for voucher in group_vouchers(rows):
        size = len(voucher.rows)
        if size > max_rows:
            raise ValueError(
                f"voucher {voucher.number} has {size} rows, more than the limit of {max_rows}"
            )
        if current and (current_vouchers + 1 > max_vouchers or len(current) + size > max_rows):
            chunks.append(current)
            current, current_vouchers = [], 0
        current.extend(voucher.rows)
        current_vouchers += 1

    if current:
        chunks.append(current)
    return chunks


def write_rows(
    path: str,
    rows: Iterable[Sequence[str]],
    header: Sequence[str] | None = None,
    delimiter: str = ";",
    encoding: str = "utf-8-sig",
) -> None:
    """Write rows to a CSV file."""
    with open(path, "w", newline="", encoding=encoding) as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        if header:
            writer.writerow(header)
        writer.writerows(rows)
