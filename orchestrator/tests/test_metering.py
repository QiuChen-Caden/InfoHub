from unittest import TestCase

from metering import FREE_LIMITS, _limits_for_tenant
from models_db import Tenant


class MeteringTests(TestCase):
    def test_token_limits_override_free_limits(self):
        tenant = Tenant(
            name="Test",
            email="test@example.com",
            password_hash="unused",
            quota_limits={"ai_filter": 9000, "push_email": 0},
        )
        limits = _limits_for_tenant(tenant)
        self.assertEqual(limits["ai_filter"], 9000)
        self.assertEqual(limits["push_email"], 0)
        self.assertEqual(limits["ai_summary"], FREE_LIMITS["ai_summary"])

    def test_unknown_quota_keys_are_ignored(self):
        tenant = Tenant(
            name="Test",
            email="test@example.com",
            password_hash="unused",
            quota_limits={"unknown": 123},
        )
        self.assertNotIn("unknown", _limits_for_tenant(tenant))

