# DJPlus v0.22.0 — Backend Freeze & Hardening

Final closure validation: the Qt test fixture creates or reuses one real `QApplication` and rejects an incompatible `QCoreApplication`. Lazy `app.services` exports preserve the public API while removing the TrackRepository -> filepath normalization -> services package -> LibraryService import cycle. The full suite completed with 381 tests OK in 139.470 s, with no `0xC0000409` and no import cycles.

This local release formalizes the frozen backend API. It includes canonical/legacy compatibility documentation, migration-history guards, startup coordination, verified historical restore, deterministic fault injection coverage, isolated MainWindow composition and clean lifecycle validation.

Compatibility: schemas remain 0001–0005 and Settings remains schema 3. No scoring, external integration, UI redesign or FFmpeg distribution change is included. FFmpeg remains local, optional, ignored by Git and outside LFS.

Validation includes restore 0001/0003/0005, migration fault matrix, clean installation, subprocess imports, full unittest regression, compileall and diff checks. SQLite DDL rollback is not promised globally; recovery relies on truthful history and verified backups. Next phase: complete graphical work.
