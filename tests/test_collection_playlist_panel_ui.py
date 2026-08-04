import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox

from app.ui.collection_panel import CollectionPanel
from app.ui.playlist_panel import PlaylistPanel
from qt_test_helpers import ensure_qapplication


class _Collections:
    def __init__(self): self.items = []; self.next_id = 1
    def list_collections(self): return list(self.items)
    def create_collection(self, name): return self._create(name, "manual")
    def rename_collection(self, ident, name):
        item = self.get_collection(ident); item.name = name; return item
    def delete_collection(self, ident): self.items = [item for item in self.items if item.id != ident]
    def get_collection(self, ident): return next(item for item in self.items if item.id == ident)
    def count_tracks(self, _ident): return 0
    def _create(self, name, kind):
        if not name.strip(): raise ValueError("Nombre requerido")
        item = SimpleNamespace(id=self.next_id, name=name, type=kind); self.next_id += 1; self.items.append(item); return item
    def close(self): pass
class _Smart:
    def __init__(self, collections): self.collections = collections
    def create_smart_collection(self, name): return self.collections._create(name, "smart")
    def list_rules(self, _ident): return ()
    def close(self): pass
class _Playlists:
    def __init__(self): self.items=[]; self.next_id=1
    def list_playlists(self): return list(self.items)
    def create_playlist(self, name):
        if not name.strip(): raise ValueError("Nombre requerido")
        item=SimpleNamespace(id=self.next_id,name=name); self.next_id+=1; self.items.append(item); return item
    def rename_playlist(self, ident,name): item=next(item for item in self.items if item.id==ident); item.name=name; return item
    def delete_playlist(self,ident): self.items=[item for item in self.items if item.id!=ident]
    def count_tracks(self,_ident): return 0
    def close(self): pass

class CollectionPlaylistPanelUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = ensure_qapplication()
    def test_collections_separate_types_search_and_actions(self):
        service=_Collections(); panel=CollectionPanel(service,_Smart(service))
        try:
            panel.name_input.setText("Warmup"); panel.create_collection(); panel.name_input.setText("BPM alto"); panel.create_smart_collection()
            self.assertEqual((panel.collection_list.count(),panel.smart_collection_list.count()),(1,1))
            panel.search_input.setText("bpm"); self.assertEqual((panel.collection_list.count(),panel.smart_collection_list.count()),(0,1))
            panel.search_input.clear(); panel.collection_list.setCurrentRow(0); panel.name_input.setText("Opening"); panel.rename_collection(); self.assertEqual(service.items[0].name,"Opening")
            with patch("app.ui.collection_panel.confirm_destructive", return_value=True): panel.delete_collection()
            self.assertEqual(len(service.items),1)
        finally: panel.close()
    def test_playlists_search_create_rename_delete_and_empty_state(self):
        service=_Playlists(); panel=PlaylistPanel(service)
        try:
            panel.name_input.setText("Set"); panel.create_playlist(); panel.playlist_list.setCurrentRow(0); panel.name_input.setText("Opening"); panel.rename_playlist()
            panel.search_input.setText("missing"); self.assertTrue(panel.empty_label.isHidden() is False)
            panel.search_input.clear(); panel.playlist_list.setCurrentRow(0)
            with patch("app.ui.playlist_panel.confirm_destructive", return_value=True): panel.delete_playlist()
            self.assertEqual(panel.playlist_list.count(),0)
        finally: panel.close()
