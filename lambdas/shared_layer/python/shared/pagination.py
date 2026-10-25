"""
Pagination helpers for DynamoDB (v3.2.1).

A single table.query() / table.scan() call returns at most 1 MB of data and
sets LastEvaluatedKey when there is more. Handlers that read only the first
page silently drop everything after it. These helpers follow
LastEvaluatedKey until the result set is complete.

Do NOT use them on calls that pass Limit=...; Limit means "stop after N
items" (e.g. fetch_recent_notes_for_app) and must not be paginated.

Note: lambdas ship this file inside the shared layer (python/shared/), and
tests/conftest.py registers it as `shared.pagination` because the test files
stub `shared.middleware` inline.
"""
from typing import Any


def paginate_query(table: Any, **kwargs: Any) -> list[dict]:
    """Run table.query(**kwargs) repeatedly and return all items."""
    items: list[dict] = []
    while True:
        result = table.query(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def paginate_scan(table: Any, **kwargs: Any) -> list[dict]:
    """Run table.scan(**kwargs) repeatedly and return all items."""
    items: list[dict] = []
    while True:
        result = table.scan(**kwargs)
        items.extend(result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key
