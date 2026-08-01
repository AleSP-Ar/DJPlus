try:
    from .database import SessionLocal
    from .database.models import Track
except ImportError:  # pragma: no cover - fallback for direct execution
    from app.database import SessionLocal
    from app.database.models import Track

from sqlalchemy import or_


def _get_session(session=None):
    if session is not None:
        return session, False
    return SessionLocal(), True


def get_track_rows(limit=20, session=None):
    session_obj, should_close = _get_session(session)

    try:
        return session_obj.query(Track).limit(limit).all()
    finally:
        if should_close:
            session_obj.close()


def search_track_rows(query: str, session=None):
    session_obj, should_close = _get_session(session)

    try:
        return (
            session_obj.query(Track)
            .filter(
                or_(
                    Track.artist.ilike(f"%{query}%"),
                    Track.title.ilike(f"%{query}%"),
                )
            )
            .all()
        )
    finally:
        if should_close:
            session_obj.close()


def list_tracks(limit=20):
    tracks = get_track_rows(limit=limit)

    for track in tracks:
        print(f"{track.artist} - {track.title}")
        print(f"Ruta: {track.filepath}")
        print(f"Duración: {track.duration:.2f} segundos")
        print("-" * 40)


def search_tracks(query: str):
    results = search_track_rows(query)

    print(f"\nResultados: {len(results)}\n")

    for track in results:
        print(f"{track.artist} - {track.title}")
        print(f"Duración: {track.duration:.2f}s")
        print(f"Archivo: {track.filepath}")
        print("-" * 40)


def count_tracks():
    session = SessionLocal()

    try:
        total = session.query(Track).count()
        print(f"Total de pistas: {total}")
    finally:
        session.close()


if __name__ == "__main__":
    count_tracks()
    search_tracks("16 BIT LOLITAS")
