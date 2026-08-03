# Epic 15 - Sprint 1: Duplicate Detection

`DuplicateDetectionService` reads rows only through `LibraryService`, hashes
file content with SHA-256 in fixed blocks, supports cooperative cancellation and
returns deterministic hash groups plus estimated recoverable bytes. It never
deletes, changes tracks or changes files; unreadable files become isolated
fingerprint errors.

Files are read in 64 KiB SHA-256 blocks. Track rows and groups are ordered by
track ID/hash for stable output. Cancellation stops before the next file/block
and returns partial fingerprints without any write. The estimate is total group
size minus one retained copy; no deletion policy is implied.
