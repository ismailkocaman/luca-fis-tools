"""Command line interface: ``luca-fis validate`` and ``luca-fis split``."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import core


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("file", help="CSV file in the 14-column Luca voucher layout")
    parser.add_argument("--delimiter", default=";", help="CSV delimiter (default: ;)")
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="file encoding, e.g. utf-8-sig or cp1254 (default: utf-8-sig)",
    )
    parser.add_argument("--no-header", action="store_true", help="the file has no header row")
    parser.add_argument(
        "--max-vouchers",
        type=int,
        default=core.DEFAULT_MAX_VOUCHERS,
        help=f"max vouchers per file (default: {core.DEFAULT_MAX_VOUCHERS})",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=core.DEFAULT_MAX_ROWS,
        help=f"max rows per file (default: {core.DEFAULT_MAX_ROWS})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luca-fis",
        description="Validate and split journal voucher files for Luca imports.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="check a file and list every problem")
    _add_common(validate)

    split = sub.add_parser("split", help="split a file into import-sized parts")
    _add_common(split)
    split.add_argument(
        "--out-dir",
        default=None,
        help="directory for the parts (default: next to the input file)",
    )
    return parser


def _load(args: argparse.Namespace):
    header, rows = core.read_rows(
        args.file,
        delimiter=args.delimiter,
        encoding=args.encoding,
        has_header=not args.no_header,
    )
    return header, rows


def cmd_validate(args: argparse.Namespace) -> int:
    _, rows = _load(args)
    first_row = 1 if args.no_header else 2
    issues = core.validate(
        rows, max_vouchers=args.max_vouchers, max_rows=args.max_rows, first_row=first_row
    )
    for issue in issues:
        print(issue)
    vouchers = sum(1 for _ in core.group_vouchers(rows, first_row))
    print(f"{len(rows)} rows, {vouchers} vouchers, {len(issues)} problem(s)")
    return 1 if issues else 0


def cmd_split(args: argparse.Namespace) -> int:
    header, rows = _load(args)
    try:
        chunks = core.split_vouchers(rows, args.max_vouchers, args.max_rows)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.file))
    os.makedirs(out_dir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(args.file))
    for number, chunk in enumerate(chunks, start=1):
        target = os.path.join(out_dir, f"{stem}_part{number:02d}{ext or '.csv'}")
        core.write_rows(
            target, chunk, header=header, delimiter=args.delimiter, encoding=args.encoding
        )
        print(f"{target}: {len(chunk)} rows")
    print(f"{len(chunks)} file(s) written")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return cmd_validate(args)
    return cmd_split(args)


if __name__ == "__main__":
    sys.exit(main())
