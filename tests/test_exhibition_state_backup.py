"""Synthetic exhibition state backup tests; no production data."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_exhibition_state_backup import verify

class ExhibitionBackupTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  root=Path(self.temp.name);self.path=root/'snapshot.json';self.man=root/'manifest.json'
  self.state={'revision':4,'favs':{'a':{'revision':2,'deleted':False,'value':{'title':'A','museum':'M'}},'b':{'revision':4,'deleted':True,'value':None}},'visited':{'a':{'revision':3,'deleted':False,'value':'2026-11-23T00:00:00Z'}}}
  self.refresh()
 def refresh(self):
  self.path.write_text(json.dumps(self.state))
  self.man.write_text(json.dumps({'sha256':hashlib.sha256(self.path.read_bytes()).hexdigest()}))
 def test_independent_want_seen_and_tombstone_survive_replay(self):
  result=verify(self.path,self.man)
  self.assertEqual(result['revision'],4)
  self.assertEqual(result['want_entries'],2)
  self.assertEqual(result['seen_entries'],1)
  self.assertFalse(result['database_restore_verified'])
 def test_modified_backup_rejected(self):
  self.path.write_text(self.path.read_text()+' ')
  with self.assertRaises(ValueError):verify(self.path,self.man)
 def test_invalid_state_rejected_even_with_valid_manifest(self):
  self.state['revision']=-1;self.refresh()
  with self.assertRaises((ValueError,TypeError)):verify(self.path,self.man)
 def test_manifest_must_be_separate(self):
  with self.assertRaises(ValueError):verify(self.path,self.path)

if __name__=='__main__':unittest.main()
