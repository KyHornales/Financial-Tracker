import unittest
from decimal import Decimal

from services.calculations import (
    fixed_expense_status,
    format_iso_week_dates,
    iso_monday,
    iso_week_dates,
    projected_close,
    summarize,
)


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.incomes = [{"amount": "1000.00"}]
        self.transactions = [
            {"amount": "250.00", "category_group": "Need", "is_sink": False},
            {"amount": "100.00", "category_group": "Savings", "is_sink": False},
            {"amount": "650.00", "category_group": "Sink", "is_sink": True},
        ]

    def test_summary_excludes_sink_and_separates_savings(self):
        result = summarize(self.incomes, self.transactions)
        self.assertEqual(result["income"], Decimal("1000.00"))
        self.assertEqual(result["expenses"], Decimal("250.00"))
        self.assertEqual(result["savings_contributions"], Decimal("100.00"))
        self.assertEqual(result["unallocated"], Decimal("650.00"))

    def test_add_to_savings_uses_existing_savings_not_cash(self):
        period = {"starting_cash": "400.00", "total_savings": "900.00"}
        summary = summarize(self.incomes, self.transactions)
        result = projected_close(period, summary, "Add to Savings")
        self.assertEqual(result["ending_cash"], Decimal("400.00"))
        self.assertEqual(result["total_savings"], Decimal("1650.00"))

    def test_keep_as_cash(self):
        period = {"starting_cash": "400.00", "total_savings": "900.00"}
        summary = summarize(self.incomes, self.transactions)
        result = projected_close(period, summary, "Keep as Cash")
        self.assertEqual(result["ending_cash"], Decimal("1050.00"))
        self.assertEqual(result["total_savings"], Decimal("1000.00"))

    def test_iso_week_starts_on_monday(self):
        self.assertEqual(iso_monday(2026, 36).isoformat(), "2026-08-31")

    def test_iso_week_date_range_ends_on_sunday(self):
        start, end = iso_week_dates(2026, 36)
        self.assertEqual(start.isoformat(), "2026-08-31")
        self.assertEqual(end.isoformat(), "2026-09-06")

    def test_iso_week_date_range_has_plain_language_label(self):
        self.assertEqual(
            format_iso_week_dates(2026, 36),
            "Aug 31 – Sep 6, 2026",
        )

    def test_piggy_bank_does_not_change_carried_balances(self):
        period = {"starting_cash": "400.00", "total_savings": "900.00"}
        summary = summarize(self.incomes, self.transactions)
        result = projected_close(period, summary, "Piggy Bank")
        self.assertEqual(result["ending_cash"], Decimal("400.00"))
        self.assertEqual(result["total_savings"], Decimal("1000.00"))

    def test_deficit_cannot_close(self):
        summary = summarize(
            [{"amount": "100.00"}],
            [{"amount": "125.00", "category_group": "Need", "is_sink": False}],
        )
        with self.assertRaises(ValueError):
            projected_close(
                {"starting_cash": "0.00", "total_savings": "0.00"},
                summary,
                "Keep as Cash",
            )

    def test_fixed_expense_status(self):
        self.assertEqual(fixed_expense_status("500", "0"), "Not logged")
        self.assertEqual(fixed_expense_status("500", "450"), "Logged")
        self.assertEqual(fixed_expense_status("500", "550"), "Over plan")


if __name__ == "__main__":
    unittest.main()
