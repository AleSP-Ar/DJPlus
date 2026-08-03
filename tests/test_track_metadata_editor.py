import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from app.services.action_pipeline import ActionPipeline
from app.services.confirmation_manager import ConfirmationManager, ConfirmationRequestDTO
from app.services.track_metadata_editor import TrackMetadataPatchDTO, BulkMetadataEditQueryDTO, TrackMetadataEditorService

class _Tracks:
 def __init__(self,t): self.t=t
 def get_by_id(self,i): return self.t if i==self.t.id else None
 def update_track_metadata(self,t,v,commit=True):
  for k,x in v.items(): setattr(t,k,x)
class _U:
 def __init__(self,t): self.tracks=_Tracks(t)
 def __enter__(self): return self
 def __exit__(self,*_): return False
class TrackMetadataEditorTests(unittest.TestCase):
 def test_preview_confirmed_apply_and_restore(self):
  t=SimpleNamespace(id=1,title="Old",artist="A",album=None,genre=None,rating=2,bpm=120,key="C",energy=20); p=ActionPipeline(); s=TrackMetadataEditorService(p,ConfirmationManager(p),lambda:_U(t))
  q=BulkMetadataEditQueryDTO((1,),TrackMetadataPatchDTO.from_mapping({"title":"New","album":None,"rating":5,"bpm":124}))
  preview=s.preview(q); self.assertIn("title=new",preview.preview); proposal=s.propose(preview); applied=s.apply(preview,proposal,ConfirmationRequestDTO(proposal.action_id,datetime.now(timezone.utc)))
  self.assertTrue(applied.success); self.assertEqual((t.title,t.rating,t.bpm),("New",5,124)); self.assertTrue(s.restore(1)); self.assertEqual((t.title,t.rating,t.bpm),("Old",2,120))
 def test_validates_ranges_and_isolates_missing_track(self):
  with self.assertRaises(ValueError): TrackMetadataPatchDTO.from_mapping({"rating":9})
