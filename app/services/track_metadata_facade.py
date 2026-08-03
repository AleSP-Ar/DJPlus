"""LibraryService-facing track metadata preview and apply boundary."""
from .track_metadata_editor import BulkMetadataEditQueryDTO

class TrackMetadataFacade:
 def __init__(self,library_service,editor): self.library_service,self.editor=library_service,editor
 def preview(self,query):
  if not isinstance(query,BulkMetadataEditQueryDTO): raise TypeError("query invalida")
  rows,_=self.library_service.query(text="")
  allowed={getattr(x,"id",None) for x in rows}
  if not set(query.track_ids).issubset(allowed): raise ValueError("Las pistas no estan en la consulta actual.")
  return self.editor.preview(query)
 def export_preview(self,result): return result.preview
 def export_result(self,result): return result.preview + "\nbackups=" + str(len(result.backups))
