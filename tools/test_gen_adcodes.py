#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_gen_adcodes.py -- stdlib-only negative tests for the six self-checks.

Canonical invocation (from the repository root):

    python tools/test_gen_adcodes.py

Equivalently: `python -m unittest discover -s tools -p "test_gen_adcodes.py"`.
NOTE: `python -m unittest tools.test_gen_adcodes` does NOT work on this
machine -- an unrelated `tools` package installed in site-packages shadows
the repository's `tools/` directory, so the module is imported by PATH here
and must be started as a script (or via discover, which puts `tools/` on
sys.path itself).

Why these tests exist (final whole-branch review I-3): the plan's two
declared negative scenarios never reached the six self-checks' `failed`
branch --
  (a) the adcode-suffix tamper is intercepted one layer EARLIER by the input
      schema (`ADCODE_RE` in `load_records`), so the checks are recorded as
      `not_run` and `product_value` is the constant "rejected"; and
  (b) a CSV-side rename is unreachable by construction: the product is
      derived from the same tampered copy, so both sides of the comparison
      move together (run exits 0 with `self-check: 6/6 passed`).
The only way to exercise `field_match` / `dup_names` / `row_order` failure
reporting is to hand `run_six_checks` a product/records pair that disagrees
in exactly one field, which is what this module does.

`MalformedCsvCleanPathTest` is the regression test for review I-1: a
`csv.Error` (field larger than the parser limit) used to escape `load_records`
and `main` as a Python traceback with exit 1; it must now exit 2 through the
clean error path with stderr naming the offending CSV and no traceback.

Standard library only (no third-party imports). Every fixture lives in a
temp dir; the vendored CSV is never read, written or touched.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent


def load_generator():
    """Import tools/gen_adcodes.py by path (`tools/` is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "gen_adcodes_under_test", TOOLS_DIR / "gen_adcodes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = load_generator()

# Mirrors the real data shape: a duplicated name (朝阳区 exists twice in the
# upstream CSV) plus unique names; levels follow the adcode[:6] suffix rule.
RECORDS = [
    ("110000000000", "北京市", "Province"),
    ("110105000000", "朝阳区", "Area"),
    ("220104000000", "朝阳区", "Area"),
    ("500233000000", "忠县", "Area"),
]
RAW_SHA = "0" * 64
ARRAY_OPEN = "pub let adcodes : Array[Rec] = ["


def product_text(records=RECORDS):
    return gen.build_product_text(list(records), "adcodes.csv", RAW_SHA)


class SixCheckFailureBranchTest(unittest.TestCase):
    """`run_six_checks` must REPORT failure, not merely be able to."""

    def test_clean_pair_passes_all_six(self):
        # Positive control: without this, a check stuck on `failed` would
        # make the negative cases below pass vacuously.
        checks = gen.run_six_checks(product_text(), list(RECORDS))
        failed = [cid for cid in gen.CHECK_IDS if not checks[cid]["pass"]]
        self.assertEqual(failed, [])
        self.assertTrue(all(checks[cid]["status"] == "passed" for cid in gen.CHECK_IDS))

    def test_field_match_reports_the_tampered_field(self):
        text = product_text()
        tampered = text.replace('name: "忠县"', 'name: "忠州"')
        self.assertNotEqual(text, tampered, "fixture tamper must apply")
        checks = gen.run_six_checks(tampered, list(RECORDS))
        c = checks["field_match"]
        self.assertIs(c["pass"], False)
        self.assertEqual(c["status"], "failed")
        self.assertEqual(
            c["details"],
            [
                {
                    "line": 5,  # header comment line 1; record 4 sits on line 5
                    "csv_value": "500233000000,忠县",
                    "product_value": "500233000000,忠州",
                }
            ],
        )
        # The tamper is confined to one row, so the aggregates stay clean:
        # this is what distinguishes the six-check failure branch from a
        # wholesale product/CSV divergence.
        self.assertTrue(checks["record_count"]["pass"])
        self.assertTrue(checks["level_counts"]["pass"])
        self.assertTrue(checks["dup_names"]["pass"])
        self.assertTrue(checks["no_lonlat"]["pass"])

    def test_dup_names_reports_the_duplicate_count_drift(self):
        text = product_text()
        # Rename the FIRST 朝阳区: the CSV still holds two entries, the
        # product now holds one -> the duplicate-name statistics disagree.
        tampered = text.replace('name: "朝阳区"', 'name: "朝阳门外"', 1)
        self.assertNotEqual(text, tampered, "fixture tamper must apply")
        checks = gen.run_six_checks(tampered, list(RECORDS))
        c = checks["dup_names"]
        self.assertIs(c["pass"], False)
        self.assertEqual(c["status"], "failed")
        self.assertEqual(
            c["details"],
            [{"name": "朝阳区", "line": 3, "csv_value": 2, "product_value": 0}],
        )
        self.assertEqual(c["csv"]["duplicate_names"], 1)
        self.assertEqual(c["csv"]["unique_names"], 3)
        self.assertEqual(c["product"]["duplicate_names"], 0)
        self.assertEqual(c["product"]["unique_names"], 4)

    def test_row_order_reports_the_first_offset(self):
        lines = product_text().split("\n")
        open_idx = lines.index(ARRAY_OPEN)
        first, second = open_idx + 1, open_idx + 2
        self.assertTrue(lines[first].startswith('  { adcode: "110000000000"'))
        self.assertTrue(lines[second].startswith('  { adcode: "110105000000"'))
        # Swap two adjacent rows: the level multiset (and therefore the
        # level counts and the duplicate-name statistics) is unchanged, so
        # only the ordering is wrong.
        lines[first], lines[second] = lines[second], lines[first]
        checks = gen.run_six_checks("\n".join(lines), list(RECORDS))
        c = checks["row_order"]
        self.assertIs(c["pass"], False)
        self.assertEqual(c["status"], "failed")
        self.assertEqual(len(c["details"]), 1)
        d = c["details"][0]
        self.assertEqual(d["line"], 2)
        self.assertEqual(d["csv_value"], "110000000000,北京市,Province")
        self.assertEqual(d["product_value"], "110105000000,朝阳区,Area")
        self.assertTrue(checks["record_count"]["pass"])
        self.assertTrue(checks["level_counts"]["pass"])
        self.assertTrue(checks["dup_names"]["pass"])

    def test_short_product_reports_record_count_drift(self):
        # Truncation: the product carries one row less than the CSV.
        checks = gen.run_six_checks(product_text(RECORDS[:-1]), list(RECORDS))
        c = checks["record_count"]
        self.assertIs(c["pass"], False)
        self.assertEqual(c["status"], "failed")
        self.assertEqual(c["csv_count"], 4)
        self.assertEqual(c["product_count"], 3)
        self.assertIs(checks["row_order"]["pass"], False)


class MalformedCsvCleanPathTest(unittest.TestCase):
    """I-1 regression: `csv.Error` must use the clean error path."""

    def _write_huge_field_csv(self, path):
        # A single 200 000-byte field exceeds the csv parser's default
        # 131072-byte field limit -> csv.Error while iterating the reader.
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("adcode,name,longitude,latitude\n")
            f.write("A" * 200000 + "\n")

    def test_load_records_translates_csv_error_to_value_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "huge_field.csv"
            self._write_huge_field_csv(bad)
            with self.assertRaises(ValueError) as raised:
                gen.load_records(bad)
            message = str(raised.exception)
            self.assertIn("malformed CSV", message)
            self.assertIn(str(bad), message)

    def test_cli_exits_2_without_traceback_and_names_the_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            bad = tmpdir / "huge_field.csv"
            self._write_huge_field_csv(bad)
            out = tmpdir / "out" / "adcodes.mbt"
            err = io.StringIO()
            original_repo_root = gen.repo_root
            # Redirect the repo root so the run's diagnostic report lands in
            # the temp dir instead of the repository's `_build/`.
            gen.repo_root = lambda: tmpdir
            try:
                with contextlib.redirect_stderr(err):
                    with self.assertRaises(SystemExit) as raised:
                        gen.main(["--csv", str(bad), "--out", str(out)])
            finally:
                gen.repo_root = original_repo_root

            self.assertEqual(raised.exception.code, 2)
            stderr = err.getvalue()
            self.assertNotIn("Traceback", stderr)
            self.assertIn("gen_adcodes: error:", stderr)
            self.assertIn("malformed CSV", stderr)
            self.assertIn(str(bad), stderr)
            self.assertFalse(out.exists(), "a failed run must not write the product")

            report = tmpdir / "_build" / "gen_report.json"
            self.assertTrue(report.is_file(), "a failed run must still report")
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(
                [cid for cid in gen.CHECK_IDS if payload["checks"][cid]["status"] != "not_run"],
                [],
            )
            self.assertIn(str(bad), payload["csv"]["path"])


if __name__ == "__main__":
    unittest.main()
