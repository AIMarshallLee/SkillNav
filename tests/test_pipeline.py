import csv
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

FIXTURES = Path(__file__).resolve().parent / "fixtures/skills"
NORMALIZER = FIXTURES / "normalize-ledger/scripts/normalize.py"
REPORTER = FIXTURES / "ledger-report/scripts/report.py"


class PipelineTests(unittest.TestCase):
    def test_two_real_scripts_handoff_three_formats_and_input_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "input.csv"
            source.write_text("item,quantity,unit_price\n  red cards  ,7,3.25\nblue pens,4,2.40\n")
            original = source.read_bytes()
            normalized = root / "normalized.csv"
            subprocess.run([sys.executable, str(NORMALIZER), str(source), str(normalized)], check=True, capture_output=True)
            with normalized.open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["item"], "red cards")
            expected = sum(Decimal(r["quantity"]) * Decimal(r["unit_price"]) for r in rows)
            self.assertEqual(expected, Decimal("32.35"))
            for format in ("markdown", "html", "json"):
                target = root / ("report." + format)
                subprocess.run([sys.executable, str(REPORTER), str(normalized), str(target), "--format", format], check=True, capture_output=True)
                self.assertIn("32.35", target.read_text())
                if format == "json":
                    self.assertEqual(json.loads(target.read_text())["item_count"], 2)
            self.assertEqual(source.read_bytes(), original)

    def test_invalid_line_totals_fail_instead_of_generating_success(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "wrong.csv"
            source.write_text("item,quantity,unit_price,line_total\na,2,3.00,100.00\n")
            target = root / "report.md"
            result = subprocess.run([sys.executable, str(REPORTER), str(source), str(target)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
