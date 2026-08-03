"""Manual-only local preview check; never imported by the unittest suite."""

from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QVBoxLayout, QWidget

from app.services.preview_player import PreviewTrackDTO, create_preview_player_service
from app.ui.widgets.preview_player_bar import PreviewPlayerBar


def main():
    application = QApplication([])
    service = create_preview_player_service()
    window = QWidget(); window.setWindowTitle("DJPlus manual preview check")
    layout = QVBoxLayout(window)
    choose = QPushButton("Elegir archivo de audio")
    bar = PreviewPlayerBar(service)

    def choose_file():
        filepath, _ = QFileDialog.getOpenFileName(window, "Elegir audio", "", "Audio (*.mp3 *.flac *.aif *.aiff *.wav)")
        if filepath:
            bar.load_track(PreviewTrackDTO(filepath=filepath))

    choose.clicked.connect(choose_file)
    layout.addWidget(choose); layout.addWidget(bar)
    window.show()
    try:
        return application.exec()
    finally:
        bar.close(); service.close()


if __name__ == "__main__":
    raise SystemExit(main())
