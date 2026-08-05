import uuid
from unittest import IsolatedAsyncioTestCase

from db import Database
from models import NewsItem


class _Result:
    def __iter__(self):
        return iter(())


class _Session:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result()


class TenantQueryTests(IsolatedAsyncioTestCase):
    async def test_filter_new_always_contains_tenant_predicate(self):
        session = _Session()
        tenant_id = uuid.uuid4()
        database = Database(session, tenant_id)
        await database.filter_new([
            NewsItem(id="one", title="One", url="", source="", source_type="rss")
        ])

        where_sql = " ".join(str(item) for item in session.statement._where_criteria)
        self.assertIn("news.tenant_id", where_sql)
        params = session.statement.compile().params
        self.assertIn(tenant_id, params.values())

