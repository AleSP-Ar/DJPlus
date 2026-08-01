from argparse import ArgumentParser

try:
    from .database import init_database
    from .scanner import scan_folder
    from .gui import launch_gui
except ImportError:  # pragma: no cover - fallback for direct execution
    from database import init_database
    from scanner import scan_folder
    from gui import launch_gui


def main():
    parser = ArgumentParser(description="DJPlus")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="escanea la carpeta de música y termina",
    )
    args = parser.parse_args()

    print("Iniciando DJPlus...")

    init_database()
    print("Base de datos lista")

    if args.scan:
        scan_folder(r"D:\Musica")
    else:
        launch_gui()


if __name__ == "__main__":
    main()
