from __future__ import annotations
import argparse
from pathlib import Path
from core.database import Database
from storage.json_backend import JsonStorageBackend


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini-DBMS desktop CLI stub")
    parser.add_argument("database", nargs="?", help="Path to JSON database file")
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter GUI instead of CLI")
    args = parser.parse_args()

    if args.gui:
        from .gui_app import launch_gui
        launch_gui()
        return

    if not args.database:
        print("Please provide path to database JSON or use --gui to open GUI")
        return

    path = Path(args.database)
    if path.exists():
        database = JsonStorageBackend.load(path)
    else:
        database = Database(name=path.stem)
        JsonStorageBackend.save(database, path)

    print(f"Loaded database '{database.name}' with tables: {', '.join(database.tables.keys()) or 'none'}")


if __name__ == "__main__":
    main()

