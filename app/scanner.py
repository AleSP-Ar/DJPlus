import os
from mutagen import File

try:
    from .database import SessionLocal
    from .models import Track
except ImportError:  # pragma: no cover - fallback for direct execution
    from database import SessionLocal
    from models import Track

AUDIO_EXTENSIONS = (
    ".mp3",
    ".wav",
    ".flac",
    ".aiff",
    ".m4a"
)


def scan_folder(folder_path):

    session = SessionLocal()

    total = 0
    added = 0
    errors = []

    for root, _, files in os.walk(folder_path):

        for filename in files:

            if not filename.lower().endswith(AUDIO_EXTENSIONS):
                continue

            total += 1
            filepath = os.path.join(root, filename)

            print(f"[{total}] {filename}")

            existing = (
                session.query(Track)
                .filter_by(filepath=filepath)
                .first()
            )

            if existing:
                continue

            try:

                audio = File(filepath)

                title = filename
                artist = "Unknown"
                duration = 0

                if audio:

                    duration = getattr(
                        audio.info,
                        "length",
                        0
                    )

                    if audio.tags:

                        artist = str(
                            audio.tags.get(
                                "TPE1",
                                ["Unknown"]
                            )[0]
                        )

                        title = str(
                            audio.tags.get(
                                "TIT2",
                                [filename]
                            )[0]
                        )

                track = Track(
                    title=title,
                    artist=artist,
                    filepath=filepath,
                    duration=duration
                )

                session.add(track)
                added += 1

            except Exception as e:

                errors.append(
                    f"{filepath} -> {e}"
                )

            if total % 100 == 0:
                session.commit()
                print(
                    f"Guardado parcial: {total} archivos"
                )

    session.commit()
    session.close()

    print("\n--- RESULTADO ---")
    print(f"Archivos encontrados: {total}")
    print(f"Nuevas pistas agregadas: {added}")
    print(f"Errores: {len(errors)}")

    if errors:

        with open(
            "scan_errors.txt",
            "w",
            encoding="utf-8"
        ) as file:

            for error in errors:
                file.write(error + "\n")

        print(
            "Reporte creado: scan_errors.txt"
        )
