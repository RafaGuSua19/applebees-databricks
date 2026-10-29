import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "jobs"))
from quality_rules import ZERO_REQUIRED, qualified_schema, quality_errors


class QualityRulesTests(unittest.TestCase):
    def setUp(self):
        self.row = dict.fromkeys(ZERO_REQUIRED, 0)
        self.row.update(tickets=100, pct_tickets_conciliados=Decimal("0.99"),
                        min_pct_conciliado_diario=Decimal("0.95"))

    def test_valid_and_threshold_boundary(self):
        self.assertEqual(quality_errors([self.row]), [])

    def test_each_critical_counter_blocks(self):
        for metric in ZERO_REQUIRED:
            with self.subTest(metric=metric):
                self.assertTrue(quality_errors([{**self.row, metric: 1}]))

    def test_no_rows_or_multiple_rows(self):
        self.assertTrue(quality_errors([]))
        self.assertTrue(quality_errors([self.row, self.row]))

    def test_missing_invalid_and_nonfinite_metrics(self):
        for metric in self.row:
            for value in (None, float("nan"), float("inf"), -1, "0", True):
                with self.subTest(metric=metric, value=value):
                    self.assertTrue(quality_errors([{**self.row, metric: value}]))
            row = {key: value for key, value in self.row.items() if key != metric}
            self.assertTrue(quality_errors([row]))

    def test_empty_data_has_explicit_diagnostic(self):
        errors = quality_errors([{**self.row, "tickets": 0, "pct_tickets_conciliados": None}])
        self.assertIn("no hay tickets", ";".join(errors))

    def test_daily_failure_cannot_hide_in_global_average(self):
        self.assertTrue(quality_errors([{**self.row, "min_pct_conciliado_diario": 0.94}]))

    def test_ratios_cannot_exceed_one(self):
        self.assertTrue(quality_errors([{**self.row, "pct_tickets_conciliados": 1.01}]))

    def test_fractional_counter_rejected(self):
        self.assertTrue(quality_errors([{**self.row, "tickets": 0.5}]))

    def test_identifiers_cannot_inject_sql(self):
        self.assertEqual(qualified_schema("workspace", "applebees_qa"), "workspace.applebees_qa")
        for invalid in ("", "a.b", "a;DROP TABLE x", "a`", "../", "x y"):
            with self.assertRaises(ValueError):
                qualified_schema("workspace", invalid)


if __name__ == "__main__":
    unittest.main()
