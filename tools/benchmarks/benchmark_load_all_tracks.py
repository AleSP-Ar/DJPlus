"""Benchmark temporal de carga completa y controles de la biblioteca."""

from pathlib import Path
import sys
from time import perf_counter
import ctypes
from ctypes import wintypes

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.library_view import LibraryView
from app.ui.main_window import MainWindow
from app.database import init_database


class ProcessMemoryCountersEx(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
psapi.GetProcessMemoryInfo.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(ProcessMemoryCountersEx),
    wintypes.DWORD,
]
psapi.GetProcessMemoryInfo.restype = wintypes.BOOL


def process_events(application: QApplication) -> None:
    application.processEvents()


def process_memory_bytes() -> int:
    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    process = kernel32.GetCurrentProcess()
    success = psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    if not success:
        raise ctypes.WinError()
    return counters.WorkingSetSize


def main() -> None:
    init_database()
    application = QApplication.instance() or QApplication([])

    memory_before = process_memory_bytes()
    start = perf_counter()
    window = MainWindow()
    window.show()
    process_events(application)
    open_elapsed = perf_counter() - start
    memory_after_open = process_memory_bytes()

    library = window.findChild(LibraryView)
    if library is None:
        raise RuntimeError("No se encontró LibraryView en la ventana principal.")

    total_tracks = library.library_service.count_results()
    initial_tracks = library.model.rowCount()
    if initial_tracks == 0:
        raise RuntimeError("La biblioteca no cargó pistas.")

    track = library.model.track_at(0)
    query = (track.artist or track.title).strip()
    start = perf_counter()
    library.search.setText(query)
    process_events(application)
    filter_elapsed = perf_counter() - start
    filtered_tracks = library.model.rowCount()
    filter_ok = 0 < filtered_tracks <= total_tracks

    start = perf_counter()
    library.search.clear()
    process_events(application)
    library.sort_tracks(0)
    process_events(application)
    sorting_elapsed = perf_counter() - start
    sorting_ok = library.model.rowCount() == min(initial_tracks, total_tracks)

    rows_before_fetch = library.model.rowCount()
    start = perf_counter()
    if library.model.canFetchMore():
        library.model.fetchMore()
    process_events(application)
    fetch_elapsed = perf_counter() - start
    incremental_ok = library.model.rowCount() > rows_before_fetch or not library.model.canFetchMore()

    start = perf_counter()
    library.table.selectRow(0)
    process_events(application)
    selection_elapsed = perf_counter() - start
    selection_ok = library.info_label.text() != "Selecciona una pista"

    window.close()

    print(f"Tiempo de apertura: {open_elapsed:.3f} s")
    print(f"Pistas totales: {total_tracks}")
    print(f"Pistas cargadas en la primera pagina: {initial_tracks}")
    print(f"Memoria del proceso tras apertura: {memory_after_open / 1024 / 1024:.2f} MiB")
    print(
        "Incremento de memoria durante la apertura: "
        f"{(memory_after_open - memory_before) / 1024 / 1024:.2f} MiB"
    )
    print(
        f"Filtro ({query!r}): {'OK' if filter_ok else 'ERROR'} "
        f"({filtered_tracks} resultados, {filter_elapsed:.3f} s)"
    )
    print(f"Ordenamiento: {'OK' if sorting_ok else 'ERROR'} ({sorting_elapsed:.3f} s)")
    print(f"Carga incremental: {'OK' if incremental_ok else 'ERROR'} ({fetch_elapsed:.3f} s)")
    print(f"Selección de pista: {'OK' if selection_ok else 'ERROR'} ({selection_elapsed:.3f} s)")
    if not (filter_ok and sorting_ok and incremental_ok and selection_ok):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
