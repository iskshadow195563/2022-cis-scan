import unittest

from core.cis_selection import apply_bulk_selection, row_matches_query


class TestCisSelection(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "code": "1.1.1",
                "number": "1.1.1",
                "level": "L1",
                "name": "enforce password history >=24",
                "assessment": "Automated",
            },
            {
                "code": "1.1.2",
                "number": "1.1.2",
                "level": "L1",
                "name": "something manual",
                "assessment": "Manual",
            },
            {
                "code": "2.2.1",
                "number": "2.2.1",
                "level": "L2",
                "name": "ms only rule",
                "assessment": "MS only, Automated",
            },
        ]

    def test_row_matches_empty_query(self):
        self.assertTrue(row_matches_query(self.rows[0], ""))
        self.assertTrue(row_matches_query(self.rows[0], None))

    def test_row_matches_typo_query_returns_true(self):
        self.assertTrue(row_matches_query(self.rows[0], "autimated"))

    def test_row_matches_subsequence_query_returns_true(self):
        self.assertTrue(row_matches_query(self.rows[0], "enf pwd hist"))

    def test_select_all_applies_only_to_matching_query(self):
        selected = apply_bulk_selection(
            rows=self.rows,
            selected_codes=set(),
            query="automated",
            select_state=True,
        )
        self.assertEqual(selected, {"1.1.1", "2.2.1"})

    def test_deselect_all_applies_only_to_matching_query(self):
        selected = {"1.1.1", "1.1.2", "2.2.1"}
        selected = apply_bulk_selection(
            rows=self.rows,
            selected_codes=selected,
            query="manual",
            select_state=False,
        )
        self.assertEqual(selected, {"1.1.1", "2.2.1"})

    def test_select_with_no_matches_changes_nothing(self):
        selected = {"1.1.2"}
        selected2 = apply_bulk_selection(
            rows=self.rows,
            selected_codes=selected,
            query="zzzz-not-found",
            select_state=True,
        )
        self.assertEqual(selected2, selected)

    def test_level_filter_is_respected(self):
        selected = apply_bulk_selection(
            rows=self.rows,
            selected_codes=set(),
            query="",
            select_state=True,
            level_filter={"L1"},
        )
        self.assertEqual(selected, {"1.1.1", "1.1.2"})


if __name__ == "__main__":
    unittest.main()
