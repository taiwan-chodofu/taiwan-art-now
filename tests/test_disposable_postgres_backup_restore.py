"""Disposable PostgreSQL exhibition state restore drill; synthetic data only.

Requires explicit CI flag and exact localhost database identity. Never targets
production. Restores into a separate synthetic owner, not over live records.
"""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from versioned_subscriber_sync import validate_state

@unittest.skipUnless(os.environ.get('TAN_CI_DISPOSABLE_POSTGRES') == '1',
                     'Disposable PostgreSQL only')
class DisposableExhibitionRestoreTests(unittest.TestCase):
 def test_independent_backup_replay_into_separate_owner(self):
  import psycopg
  from psycopg.types.json import Jsonb
  from scripts.verify_exhibition_state_backup import verify
  url=os.environ['TAN_CI_DATABASE_URL']
  parsed=urlsplit(url)
  if parsed.hostname not in ('127.0.0.1','localhost') or parsed.path!='/tan_ci_disposable':
   raise RuntimeError('Refusing non-disposable PostgreSQL target')
  if os.environ.get('TAN_DATABASE_URL')==url:
   raise RuntimeError('Production URL matches test database')
  state={'revision':4,
         'favs':{'both':{'revision':2,'deleted':False,'value':{'title':'Art','museum':'Museum'}},
                 'removed':{'revision':4,'deleted':True,'value':None}},
         'visited':{'both':{'revision':3,'deleted':False,'value':'2026-11-23T00:00:00Z'}}}
  validate_state(state)
  with tempfile.TemporaryDirectory() as tmp:
   snapshot=Path(tmp)/'snapshot.json';manifest=Path(tmp)/'manifest.json'
   snapshot.write_text(json.dumps(state),encoding='utf-8')
   manifest.write_text(json.dumps({'sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest()}))
   self.assertEqual(verify(snapshot,manifest)['status'],'offline_exhibition_replay_verified')
   restored=json.loads(snapshot.read_text(encoding='utf-8'))
   with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
     cur.execute('SELECT current_database()')
     self.assertEqual(cur.fetchone()[0],'tan_ci_disposable')
     cur.execute('CREATE SCHEMA IF NOT EXISTS tan_private')
     cur.execute('CREATE TABLE IF NOT EXISTS tan_private.messenger_subscribers (sender_id text primary key)')
     cur.execute('CREATE TABLE IF NOT EXISTS tan_private.subscriber_sync_states (sender_id text primary key REFERENCES tan_private.messenger_subscribers(sender_id), state jsonb not null, updated_at timestamptz default now())')
     cur.execute('INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)',('synthetic-backup-restore-source',))
     cur.execute('INSERT INTO tan_private.messenger_subscribers(sender_id) VALUES (%s)',('synthetic-backup-restore-destination',))
     cur.execute('INSERT INTO tan_private.subscriber_sync_states(sender_id,state) VALUES (%s,%s)',('synthetic-backup-restore-source',Jsonb(state)))
     cur.execute('INSERT INTO tan_private.subscriber_sync_states(sender_id,state) VALUES (%s,%s)',('synthetic-backup-restore-destination',Jsonb(restored)))
     cur.execute('SELECT state FROM tan_private.subscriber_sync_states WHERE sender_id=%s',('synthetic-backup-restore-destination',))
     replayed=cur.fetchone()[0]
     validate_state(replayed)
     self.assertEqual(replayed,state)
     self.assertTrue(replayed['favs']['removed']['deleted'])
     self.assertIn('both',replayed['favs'])
     self.assertIn('both',replayed['visited'])
     cur.execute('SELECT state FROM tan_private.subscriber_sync_states WHERE sender_id=%s',('synthetic-backup-restore-source',))
     self.assertEqual(cur.fetchone()[0],state)
    conn.rollback()  # Drill must not persist even within disposable database.

if __name__=='__main__':unittest.main()
