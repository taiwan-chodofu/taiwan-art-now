"""Static guard for draft DDL; not a substitute for applying in disposable PostgreSQL."""
from pathlib import Path
import unittest

SQL = Path(__file__).resolve().parents[1] / 'docs/security/VERSIONED_SUBSCRIBER_SCHEMA_DRAFT.sql'

class DraftSchemaTests(unittest.TestCase):
 def test_single_complete_revision_constraint_and_rls(self):
  sql=SQL.read_text()
  self.assertEqual(sql.count('create table if not exists tan_private.subscriber_sync_states'),1)
  self.assertEqual(sql.count('alter table tan_private.subscriber_sync_states enable row level security;'),1)
  self.assertEqual(sql.count('revoke all on tan_private.subscriber_sync_states'),1)
  self.assertIn("~ '^(0|[1-9][0-9]{0,18})$'",sql)
  self.assertIn('::numeric <= 9223372036854775807',sql)
  self.assertEqual(sql.count("'" ) % 2,0)
  self.assertIn('DO NOT APPLY TO PRODUCTION',sql)

if __name__=='__main__':unittest.main()
