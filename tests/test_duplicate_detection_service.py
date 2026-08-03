import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from app.services.duplicate_detection_service import *
class L:
 def __init__(self,r):self.r=r
 def query(self,text=""):return self.r,False
class DuplicateTests(unittest.TestCase):
 def test_groups_hashes_and_isolates_errors(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/"a";b=Path(d)/"b";a.write_bytes(b"same");b.write_bytes(b"same")
   r=DuplicateDetectionService(L((SimpleNamespace(id=1,filepath=str(a)),SimpleNamespace(id=2,filepath=str(b)),SimpleNamespace(id=3,filepath="missing")))).scan(DuplicateScanQueryDTO())
  self.assertEqual(r.groups[0].track_ids,(1,2));self.assertEqual(r.groups[0].recoverable_bytes,4);self.assertIsNotNone(r.fingerprints[2].error)
 def test_different_names_cancel_and_multiple_groups_are_deterministic(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for name,data in (("same.mp3",b"a"),("other.mp3",b"b"),("renamed.flac",b"a"),("third",b"c"),("fourth",b"c")):
    p=Path(d)/name;p.write_bytes(data);paths.append(p)
   rows=tuple(SimpleNamespace(id=i+1,filepath=str(p)) for i,p in reversed(list(enumerate(paths))))
   r=DuplicateDetectionService(L(rows)).scan(DuplicateScanQueryDTO())
  self.assertEqual(tuple(sorted(g.track_ids for g in r.groups)),((1,3),(4,5)))
  self.assertEqual(r.fingerprints[0].track_id,1)
 def test_cooperative_cancellation_does_not_change_files(self):
  class T:
   def is_cancelled(self): return True
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x";p.write_bytes(b"content"); before=p.read_bytes()
   r=DuplicateDetectionService(L((SimpleNamespace(id=1,filepath=str(p)),))).scan(DuplicateScanQueryDTO(cancellation_token=T()))
   self.assertTrue(r.cancelled);self.assertEqual(p.read_bytes(),before)
