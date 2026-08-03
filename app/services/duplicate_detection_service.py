"""Read-only deterministic content-hash duplicate detection via LibraryService."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

@dataclass(frozen=True)
class DuplicateFingerprintDTO:
 track_id:int; filepath:str; content_hash:str|None; size_bytes:int; error:str|None=None
@dataclass(frozen=True)
class DuplicateGroupDTO:
 content_hash:str; track_ids:tuple[int,...]; filepaths:tuple[str,...]; recoverable_bytes:int
@dataclass(frozen=True)
class DuplicateScanQueryDTO:
 track_ids:tuple[int,...]=(); cancellation_token:object|None=None
@dataclass(frozen=True)
class DuplicateDetectionResultDTO:
 fingerprints:tuple[DuplicateFingerprintDTO,...]; groups:tuple[DuplicateGroupDTO,...]; cancelled:bool
class DuplicateDetectionService:
 block_size=65536
 def __init__(self,library_service):
  if not callable(getattr(library_service,"query",None)): raise TypeError("DuplicateDetectionService requiere LibraryService.")
  self.library_service=library_service
 def scan(self,query):
  if not isinstance(query,DuplicateScanQueryDTO): raise TypeError("query invalida")
  rows,_=self.library_service.query(text=""); out=[]
  for track in sorted(rows,key=lambda item:getattr(item,"id",0)):
   if query.track_ids and getattr(track,"id",None) not in query.track_ids: continue
   if query.cancellation_token and query.cancellation_token.is_cancelled(): return DuplicateDetectionResultDTO(tuple(out),(),True)
   path=str(getattr(track,"filepath", ""))
   try:
    h=sha256(); size=0
    with open(path,"rb") as f:
     while block:=f.read(self.block_size):
      if query.cancellation_token and query.cancellation_token.is_cancelled(): return DuplicateDetectionResultDTO(tuple(out),(),True)
      h.update(block); size+=len(block)
    out.append(DuplicateFingerprintDTO(track.id,path,h.hexdigest(),size))
   except Exception as e: out.append(DuplicateFingerprintDTO(track.id,path,None,0,str(e)))
  buckets={}
  for f in out:
   if f.content_hash: buckets.setdefault(f.content_hash,[]).append(f)
  groups=tuple(DuplicateGroupDTO(h,tuple(x.track_id for x in xs),tuple(x.filepath for x in xs),sum(x.size_bytes for x in xs)-xs[0].size_bytes) for h,xs in sorted(buckets.items()) if len(xs)>1)
  return DuplicateDetectionResultDTO(tuple(out),groups,False)
