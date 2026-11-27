"""Synthetic-only offline backup rehearsal tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from rehearse_private_backup_restore import rehearse
from verify_private_backup import verify_files

class RehearsalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  root=Path(self.tmp.name)
  self.m=root/'messenger.json';self.p=root/'push.json';self.man=root/'manifest.json'
  self.m.write_text(json.dumps({'users':{'s':{'favs':{'a':True}}},'refs':{'r':'s'}}))
  self.p.write_text(json.dumps({'subscriptions':{'https://example.invalid/p':{'endpoint':'https://example.invalid/p'}}}))
  hashes,_=verify_files(self.m,self.p)
  self.man.write_text(json.dumps(hashes))
 def test_verified_disposable_restore(self):
  result=rehearse(self.m,self.p,self.man)
  self.assertEqual(result['status'],'offline_rehearsal_passed')
  self.assertEqual(result['counts'],{'users':1,'refs':1,'push':1})
  self.assertFalse(result['database_restore_verified'])
  self.assertFalse(result['exhibition_history_verified'])
 def test_missing_manifest_rejected(self):
  with self.assertRaises(ValueError):rehearse(self.m,self.p,None)
 def test_tampered_backup_rejected(self):
  self.m.write_text(self.m.read_text()+' ')
  with self.assertRaises(ValueError):rehearse(self.m,self.p,self.man)
 def test_manifest_cannot_be_backup(self):
  with self.assertRaises(ValueError):rehearse(self.m,self.p,self.m)
 def test_orphan_reference_rejected(self):
  self.m.write_text(json.dumps({'users':{},'refs':{'r':'missing'}}))
  hashes,_=None,None
  from verify_private_backup import file_digest
  self.man.write_text(json.dumps({'messenger_sha256':file_digest(self.m),'push_sha256':file_digest(self.p)}))
  with self.assertRaises(ValueError):rehearse(self.m,self.p,self.man)

if __name__=='__main__':unittest.main()
