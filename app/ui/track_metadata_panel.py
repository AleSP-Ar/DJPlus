"""Small confirmed metadata edit panel; no audio-file mutation."""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QPushButton,QTextEdit,QLabel
from app.services.track_metadata_editor import TrackMetadataPatchDTO,BulkMetadataEditQueryDTO

class TrackMetadataPanel(QWidget):
 def __init__(self,facade,parent=None):
  super().__init__(parent); self.facade=facade; self.preview_result=None; self.proposal=None
  l=QVBoxLayout(self); l.addWidget(QLabel("Editar metadata (ids separados por coma)")); self.ids=QLineEdit(); self.title=QLineEdit(); self.preview_button=QPushButton("Vista previa"); self.apply_button=QPushButton("Confirmar y aplicar"); self.output=QTextEdit(); self.output.setReadOnly(True); self.apply_button.setEnabled(False)
  for w in (self.ids,self.title,self.preview_button,self.apply_button,self.output): l.addWidget(w)
  self.preview_button.clicked.connect(self.preview); self.apply_button.clicked.connect(self.apply)
 def preview(self):
  try:
   ids=tuple(int(x.strip()) for x in self.ids.text().split(",") if x.strip()); q=BulkMetadataEditQueryDTO(ids,TrackMetadataPatchDTO.from_mapping({"title":self.title.text()})); self.preview_result=self.facade.preview(q); self.proposal=self.facade.editor.propose(self.preview_result); self.output.setPlainText(self.facade.export_preview(self.preview_result)); self.apply_button.setEnabled(True)
  except Exception as e: self.output.setPlainText(str(e)); self.apply_button.setEnabled(False)
 def apply(self):
  from app.services.confirmation_manager import ConfirmationRequestDTO
  from datetime import datetime,timezone
  r=self.facade.editor.apply(self.preview_result,self.proposal,ConfirmationRequestDTO(self.proposal.action_id,datetime.now(timezone.utc))); self.output.setPlainText(self.facade.export_result(r)); self.apply_button.setEnabled(False)
