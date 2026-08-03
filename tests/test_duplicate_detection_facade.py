import tempfile,unittest,time
from pathlib import Path
from types import SimpleNamespace
from app.services.duplicate_detection_service import DuplicateDetectionService,DuplicateScanQueryDTO
from app.services.duplicate_detection_facade import *
class L:
 def __init__(self,r):self.r=r
 def query(self,text=""):return self.r,False
class DuplicateFacadeTests(unittest.TestCase):
 def test_cache_hit_does_not_delegate_a_second_hash(self):
  class S:
   def __init__(self,base): self.base,self.calls=base,0
   def scan(self,q): self.calls+=1; return self.base.scan(q)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"a";p.write_bytes(b"same");l=L((SimpleNamespace(id=1,filepath=str(p)),));s=S(DuplicateDetectionService(l));f=DuplicateDetectionFacade(l,s)
   f.scan(DuplicateScanQueryDTO());f.scan(DuplicateScanQueryDTO());self.assertEqual(s.calls,1)
 def test_mtime_only_change_invalidates_and_delegates(self):
  class S:
   def __init__(self,base): self.base,self.calls=base,0
   def scan(self,q): self.calls+=1; return self.base.scan(q)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"a";p.write_bytes(b"same");l=L((SimpleNamespace(id=1,filepath=str(p)),));s=S(DuplicateDetectionService(l));f=DuplicateDetectionFacade(l,s)
   f.scan(DuplicateScanQueryDTO());stat=p.stat();import os;os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns+1_000_000));f.scan(DuplicateScanQueryDTO());self.assertEqual(s.calls,2)
 def test_cache_hit_invalidation_progress_and_error(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"a";p.write_bytes(b"x");bad=Path(d)/"bad"; f=DuplicateDetectionFacade(L((SimpleNamespace(id=1,filepath=str(p)),SimpleNamespace(id=2,filepath=str(bad)))),DuplicateDetectionService(L((SimpleNamespace(id=1,filepath=str(p)),SimpleNamespace(id=2,filepath=str(bad)))))); events=[];r=f.scan(DuplicateScanQueryDTO(),events.append);self.assertIsNotNone(f.cache.get(p));p.write_bytes(b"xx");self.assertIsNone(f.cache.get(p));self.assertEqual(len(events),2);self.assertIsNotNone(r.fingerprints[1].error)
 def test_worker_cancellation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"a";p.write_bytes(b"x"*100);l=L((SimpleNamespace(id=1,filepath=str(p)),));w=DuplicateDetectionWorker(DuplicateDetectionFacade(l,DuplicateDetectionService(l)));w.cancel();w.start(DuplicateScanQueryDTO());self.assertTrue(w.wait(2).cancelled)
