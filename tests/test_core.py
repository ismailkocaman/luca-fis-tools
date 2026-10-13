import os
import tempfile
import unittest
from decimal import Decimal

from luca_fis_tools import core
from luca_fis_tools.cli import main


def row(fis="1", tarih="02.01.2026", hesap="100.01", evrak="A1", borc="", alacak="", evrak_tarihi=None):
    return [
        fis,
        tarih,
        "Test fisi",
        hesap,
        evrak,
        evrak_tarihi if evrak_tarihi is not None else tarih,
        "Detay",
        borc,
        alacak,
        "",
        "MF",
        "TL",
        "1",
        "",
    ]


def balanced_voucher(number):
    return [
        row(fis=str(number), hesap="100.01", borc="100,00"),
        row(fis=str(number), hesap="320.01", alacak="100,00"),
    ]


class ParseTests(unittest.TestCase):
    def test_amount_formats(self):
        self.assertEqual(core.parse_amount("1.234,56"), Decimal("1234.56"))
        self.assertEqual(core.parse_amount("1,234.56"), Decimal("1234.56"))
        self.assertEqual(core.parse_amount("1234,5"), Decimal("1234.5"))
        self.assertEqual(core.parse_amount("1234.56"), Decimal("1234.56"))
        self.assertEqual(core.parse_amount(""), Decimal("0"))

    def test_amount_invalid(self):
        with self.assertRaises(ValueError):
            core.parse_amount("abc")

    def test_date_formats(self):
        for text in ("31.12.2026", "31/12/2026", "2026-12-31"):
            self.assertEqual(core.parse_date(text).day, 31)
        with self.assertRaises(ValueError):
            core.parse_date("31-12-2026")


class ValidateTests(unittest.TestCase):
    def test_clean_file_has_no_issues(self):
        rows = balanced_voucher(1) + balanced_voucher(2)
        self.assertEqual(core.validate(rows), [])

    def test_unbalanced_voucher(self):
        rows = [row(borc="100,00"), row(hesap="320.01", alacak="90,00")]
        messages = [i.message for i in core.validate(rows)]
        self.assertTrue(any("unbalanced" in m for m in messages))

    def test_missing_evrak_fields(self):
        rows = [
            row(evrak="", evrak_tarihi="", borc="10,00"),
            row(hesap="320.01", alacak="10,00"),
        ]
        columns = {i.column for i in core.validate(rows)}
        self.assertIn("Evrak No", columns)
        self.assertIn("Evrak Tarihi", columns)

    def test_trailing_dot_account(self):
        rows = [row(hesap="180.02.", borc="10,00"), row(hesap="320.01", alacak="10,00")]
        issues = core.validate(rows)
        self.assertTrue(any("trailing dot" in i.message for i in issues))

    def test_wrong_column_count(self):
        issues = core.validate([["1", "02.01.2026"]])
        self.assertEqual(issues[0].column, "columns")

    def test_debit_and_credit_on_same_row(self):
        rows = [row(borc="10,00", alacak="10,00")]
        self.assertTrue(any("both" in i.message for i in core.validate(rows)))

    def test_voucher_limit(self):
        rows = []
        for n in range(1, 52):
            rows += balanced_voucher(n)
        issues = core.validate(rows)
        self.assertTrue(any("exceed the limit of 50" in i.message for i in issues))

    def test_row_limit(self):
        rows = balanced_voucher(1) + balanced_voucher(2)
        issues = core.validate(rows, max_rows=3)
        self.assertTrue(any("rows exceed" in i.message for i in issues))

    def test_voucher_split_into_two_blocks(self):
        rows = balanced_voucher(1) + balanced_voucher(2) + balanced_voucher(1)
        issues = core.validate(rows)
        self.assertTrue(any("separate blocks" in i.message for i in issues))


class SplitTests(unittest.TestCase):
    def test_splits_by_voucher_count(self):
        rows = []
        for n in range(1, 121):
            rows += balanced_voucher(n)
        chunks = core.split_vouchers(rows)
        self.assertEqual([len({r[0] for r in c}) for c in chunks], [50, 50, 20])

    def test_splits_by_row_count_without_breaking_vouchers(self):
        rows = []
        for n in range(1, 6):
            rows += balanced_voucher(n)  # 10 rows
        chunks = core.split_vouchers(rows, max_vouchers=50, max_rows=5)
        self.assertEqual([len(c) for c in chunks], [4, 4, 2])
        for chunk in chunks:
            numbers = [r[0] for r in chunk]
            for number in set(numbers):
                self.assertEqual(numbers.count(number), 2)

    def test_oversized_voucher(self):
        rows = [row(borc="1,00")] * 3
        with self.assertRaises(ValueError):
            core.split_vouchers(rows, max_rows=2)


class CliTests(unittest.TestCase):
    def test_validate_and_split_round_trip(self):
        rows = []
        for n in range(1, 61):
            rows += balanced_voucher(n)
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "fisler.csv")
            core.write_rows(source, rows, header=core.COLUMNS)

            self.assertEqual(main(["validate", source, "--max-vouchers", "100"]), 0)
            self.assertEqual(main(["validate", source]), 1)

            out = os.path.join(tmp, "out")
            self.assertEqual(main(["split", source, "--out-dir", out]), 0)
            parts = sorted(os.listdir(out))
            self.assertEqual(parts, ["fisler_part01.csv", "fisler_part02.csv"])
            for part in parts:
                self.assertEqual(main(["validate", os.path.join(out, part)]), 0)


if __name__ == "__main__":
    unittest.main()
