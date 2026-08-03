import unittest
from types import SimpleNamespace
from app.services.track_metadata_facade import TrackMetadataFacade
from app.services.track_metadata_editor import BulkMetadataEditQueryDTO, TrackMetadataPatchDTO
class _Library:
 def query(self,text=""): return (SimpleNamespace(id=1),),False
class _Editor:
 def preview(self,q): return SimpleNamespace(preview="1:title=new",backups=())
class TrackMetadataFacadeTests(unittest.TestCase):
 def test_preview_uses_library_boundary_and_exports_text(self):
  f=TrackMetadataFacade(_Library(),_Editor()); r=f.preview(BulkMetadataEditQueryDTO((1,),TrackMetadataPatchDTO.from_mapping({"title":"N"})))
  self.assertEqual(f.export_preview(r),"1:title=new")
