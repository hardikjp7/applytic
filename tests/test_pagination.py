"""
Tests for shared/pagination.py - v3.2.1
Run: python -m pytest tests/test_pagination.py -v
"""
from unittest.mock import MagicMock

from shared.pagination import paginate_query, paginate_scan


class TestPaginateQuery:

    def test_single_page_returns_items_and_calls_once(self):
        table = MagicMock()
        table.query.return_value = {"Items": [{"a": 1}, {"a": 2}]}
        assert paginate_query(table, KeyConditionExpression="x") == [{"a": 1}, {"a": 2}]
        table.query.assert_called_once_with(KeyConditionExpression="x")

    def test_follows_last_evaluated_key_across_pages(self):
        table = MagicMock()
        table.query.side_effect = [
            {"Items": [{"n": 1}], "LastEvaluatedKey": {"PK": "k1"}},
            {"Items": [{"n": 2}], "LastEvaluatedKey": {"PK": "k2"}},
            {"Items": [{"n": 3}]},
        ]
        items = paginate_query(table, IndexName="GSI1")
        assert [i["n"] for i in items] == [1, 2, 3]
        assert table.query.call_count == 3

    def test_passes_exclusive_start_key_on_later_pages_only(self):
        table = MagicMock()
        table.query.side_effect = [
            {"Items": [], "LastEvaluatedKey": {"PK": "k1"}},
            {"Items": []},
        ]
        paginate_query(table, IndexName="GSI1")
        first, second = table.query.call_args_list
        assert "ExclusiveStartKey" not in first[1]
        assert second[1]["ExclusiveStartKey"] == {"PK": "k1"}
        assert second[1]["IndexName"] == "GSI1"

    def test_missing_items_key_is_treated_as_empty(self):
        table = MagicMock()
        table.query.return_value = {}
        assert paginate_query(table) == []


class TestPaginateScan:

    def test_follows_last_evaluated_key(self):
        table = MagicMock()
        table.scan.side_effect = [
            {"Items": [{"n": 1}], "LastEvaluatedKey": {"PK": "k1"}},
            {"Items": [{"n": 2}]},
        ]
        items = paginate_scan(table, FilterExpression="f")
        assert [i["n"] for i in items] == [1, 2]
        assert table.scan.call_args_list[1][1]["ExclusiveStartKey"] == {"PK": "k1"}
        assert table.scan.call_args_list[1][1]["FilterExpression"] == "f"

    def test_single_page(self):
        table = MagicMock()
        table.scan.return_value = {"Items": [{"n": 1}]}
        assert paginate_scan(table) == [{"n": 1}]
        table.scan.assert_called_once_with()
