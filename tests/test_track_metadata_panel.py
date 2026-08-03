import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from app.ui.track_metadata_panel import TrackMetadataPanel
from app.ui.main_window import MainWindow
from app.database import init_database
class _Editor:
 def propose(self,r): return SimpleNamespace(action_id="a")
 def apply(self,r,p,q): return SimpleNamespace(success=True,backups=((1,()),))
class _Facade:
 def __init__(self): self.editor=_Editor()
 def preview(self,q): return SimpleNamespace(preview="1:title=new",backups=())
 def export_preview(self,r): return r.preview
 def export_result(self,r): return "applied"
class _Preview:
 def __init__(self): self.closed=False
 def close(self): self.closed=True
class TrackMetadataPanelTests(unittest.TestCase):
 @classmethod
 def setUpClass(c): c.app=QApplication.instance() or QApplication([])
 def test_headless_preview_confirmation_apply_flow(self):
  p=TrackMetadataPanel(_Facade()); p.ids.setText("1"); p.title.setText("New"); p.preview(); self.assertTrue(p.apply_button.isEnabled()); p.apply(); self.assertEqual(p.output.toPlainText(),"applied"); p.close()
 def test_main_window_exposes_optional_metadata_panel(self):
  init_database(); window=MainWindow(); self.assertTrue(hasattr(window,"track_metadata_panel")); window.close()
 def test_main_window_closes_injected_optional_preview_player(self):
  init_database(); preview=_Preview(); window=MainWindow(preview_player_service=preview); window.close(); self.assertTrue(preview.closed)
