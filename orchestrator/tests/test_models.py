from unittest import TestCase

from models_db import NotificationOutbox, QuotaToken


class ModelConstraintTests(TestCase):
    def test_outbox_has_tenant_run_channel_unique_constraint(self):
        names = {constraint.name for constraint in NotificationOutbox.__table__.constraints}
        self.assertIn("uq_outbox_tenant_run_channel", names)

    def test_quota_token_hash_is_unique(self):
        columns = QuotaToken.__table__.c
        self.assertTrue(columns.token_hash.unique)
