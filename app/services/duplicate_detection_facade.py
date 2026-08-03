"""Read-only cached duplicate scans around DuplicateDetectionService."""
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from .duplicate_detection_service import DuplicateScanQueryDTO, DuplicateDetectionResultDTO, DuplicateGroupDTO

@dataclass(frozen=True)
class DuplicateProgressDTO:
 completed:int; total:int; track_id:int|None; status:str

class FingerprintCache:
 def __init__(self): self._items={}
 def get(self,path):
  try: s=Path(path).stat(); key=(str(path),s.st_size,s.st_mtime_ns)
  except OSError: return None
  return self._items.get(key)
 def put(self,path,value):
  s=Path(path).stat(); key=(str(path),s.st_size,s.st_mtime_ns); self._items={k:v for k,v in self._items.items() if k[0]!=str(path)};self._items[key]=value

class DuplicateDetectionFacade:
 def __init__(self,library_service,service,cache=None): self.library_service,self.service,self.cache=library_service,service,cache or FingerprintCache()
 def scan(self,query,on_progress=None):
  rows,_=self.library_service.query(text=""); total=len(rows); done=0
  selected=[row for row in rows if not query.track_ids or getattr(row,"id",None) in query.track_ids]
  cached=[self.cache.get(getattr(row,"filepath", "")) for row in selected]
  if selected and all(cached):
   buckets={}
   for item in cached:buckets.setdefault(item.content_hash,[]).append(item)
   groups=tuple(DuplicateGroupDTO(key,tuple(x.track_id for x in values),tuple(x.filepath for x in values),sum(x.size_bytes for x in values)-values[0].size_bytes) for key,values in sorted(buckets.items()) if len(values)>1)
   result=DuplicateDetectionResultDTO(tuple(cached),groups,False)
  else:
   # delegate canonical hashing/grouping when any current snapshot is absent
   result=self.service.scan(query)
   for item in result.fingerprints:
    done+=1
    if item.content_hash:
     try:self.cache.put(item.filepath,item)
     except OSError:pass
    if on_progress:on_progress(DuplicateProgressDTO(done,total,item.track_id,item.error or "completed"))
   return result

 def export_text(self,result):
  """Render a deterministic, read-only report from the public result DTOs."""
  lines=[f"cancelled={result.cancelled}; fingerprints={len(result.fingerprints)}"]
  lines.extend(
   f"hash={group.content_hash}; tracks={group.track_ids}; files={group.filepaths}; recoverable={group.recoverable_bytes}"
   for group in result.groups
  )
  return "\n".join(lines)

class DuplicateDetectionWorker:
 def __init__(self,facade): self.facade=facade;self._cancel=Event();self._done=Event();self.result=None;self.error=None;self.events=[]
 def is_cancelled(self): return self._cancel.is_set()
 def cancel(self): self._cancel.set()
 def start(self,query):
  self._done.clear(); self._thread=Thread(target=self._run,args=(query,),daemon=True);self._thread.start();return self._thread
 def wait(self,timeout=None): self._done.wait(timeout);return self.result
 def _run(self,q):
  try:self.result=self.facade.scan(DuplicateScanQueryDTO(q.track_ids,self),self.events.append)
  except Exception as e:self.error=e
  finally:self._done.set()
