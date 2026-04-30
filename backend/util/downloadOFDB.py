"""
downloadOFDB.py

Downloads Open*Facts product databases (Food, Cosmetics, Pet Food, All Products),
merges them into a single SQLite table with aligned columns, and writes the result
to barcodes.sqlite.

The default pipeline is fully streaming: only one CSV chunk (~200k rows) is held
in RAM at any time, regardless of total dataset size.

Public API
----------
download_file(url, dest)                Download one .csv.gz with a progress bar.
download_all(out_dir)                   Download all four datasets.
get_all_columns(paths)                  Read only headers to get the union of columns.
iter_csv_gz(path, all_columns, label)   Yield aligned DataFrame chunks (low RAM).
load_csv_gz(path, label)                Load an entire file into one DataFrame (high RAM).
load_all(paths)                         Load all files into a list of DataFrames (high RAM).
merge_dataframes(dfs)                   Concat a list of DataFrames (high RAM).
write_sqlite(df, db_path, table)        Write a DataFrame to SQLite in chunks.
stream_to_sqlite(paths, db_path, table) Stream all files into SQLite without accumulating (low RAM).
run(out_dir, db_path, paths)            Full pipeline — uses streaming by default.
"""

import gzip
import sqlite3
import sys
from pathlib import Path
from typing import Generator, Optional

import requests
from tqdm import tqdm
import pandas as pd

# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------

DATASETS = [
    {
        "name": "Food",
        "url": "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz",
        "filename": "en.openfoodfacts.org.products.csv.gz",
    },
    {
        "name": "Cosmetics",
        "url": "https://static.openbeautyfacts.org/data/en.openbeautyfacts.org.products.csv.gz",
        "filename": "en.openbeautyfacts.org.products.csv.gz",
    },
    {
        "name": "Pet Food",
        "url": "https://static.openpetfoodfacts.org/data/en.openpetfoodfacts.org.products.csv.gz",
        "filename": "en.openpetfoodfacts.org.products.csv.gz",
    },
    {
        "name": "All Products",
        "url": "https://static.openproductsfacts.org/data/en.openproductsfacts.org.products.csv.gz",
        "filename": "en.openproductsfacts.org.products.csv.gz",
    },
]

DEFAULT_OUT_DIR = Path(__file__).parent / "ofdb_data"
DEFAULT_DB_PATH = Path(__file__).parent / "barcodes.sqlite"
TABLE_NAME = "products"
DOWNLOAD_CHUNK = 8 * 1024 * 1024   # 8 MiB per HTTP read
CSV_CHUNK_ROWS = 100_000            # rows per CSV chunk (tune down if still OOM)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, label: str = "") -> Path:
    """
    Stream-download *url* to *dest* with a per-file progress bar.
    Skips silently if *dest* already exists.
    """
    dest = Path(dest)
    if dest.exists():
        print(f"  [skip] {dest.name} already exists.")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    label = label or dest.name

    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0)) or None

    with (
        open(dest, "wb") as fh,
        tqdm(
            desc=f"  {label}",
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=True,
        ) as bar,
    ):
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
            fh.write(chunk)
            bar.update(len(chunk))

    return dest


def download_all(out_dir: Path) -> dict[str, Path]:
    """
    Download every dataset not already present in *out_dir*.
    Returns {name: local_path}.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    overall = tqdm(DATASETS, desc="Overall", unit="file", leave=True)
    for ds in overall:
        overall.set_postfix(file=ds["name"])
        dest = out_dir / ds["filename"]
        paths[ds["name"]] = download_file(ds["url"], dest, label=ds["name"])

    return paths


# ---------------------------------------------------------------------------
# Column discovery
# ---------------------------------------------------------------------------

def get_all_columns(paths: dict[str, Path]) -> list[str]:
    """
    Read only the first (header) line of each gzip file and return the ordered
    union of all column names across all files. O(1) memory — no data rows read.
    """
    seen: set[str] = set()
    all_cols: list[str] = []
    for name, path in paths.items():
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            header = fh.readline().rstrip("\n\r")
        for col in header.split("\t"):
            if col not in seen:
                all_cols.append(col)
                seen.add(col)
        print(f"  {name}: {len([c for c in header.split(chr(9))])} columns")
    print(f"  Union: {len(all_cols)} columns total")
    return all_cols


# ---------------------------------------------------------------------------
# Streaming load (low RAM)
# ---------------------------------------------------------------------------

def iter_csv_gz(
    path: Path,
    all_columns: list[str],
    label: str = "",
) -> Generator[pd.DataFrame, None, None]:
    """
    Yield DataFrame chunks from a gzip-compressed TSV, reindexed to *all_columns*
    so columns are aligned across different source files (missing cols → NaN).

    Peak RAM = one chunk at a time (~CSV_CHUNK_ROWS rows).
    """
    path = Path(path)
    label = label or path.name

    compressed_size = path.stat().st_size
    with (
        open(path, "rb") as raw,
        tqdm(
            desc=f"  {label}",
            total=compressed_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=True,
        ) as bar,
    ):
        reader = pd.read_csv(
            raw,
            compression="gzip",
            sep="\t",
            low_memory=False,
            on_bad_lines="skip",
            chunksize=CSV_CHUNK_ROWS,
        )
        prev = 0
        for chunk in reader:
            cur = raw.tell()
            bar.update(cur - prev)
            prev = cur
            yield chunk.reindex(columns=all_columns)


# ---------------------------------------------------------------------------
# In-memory load helpers (kept for small datasets / modular use)
# ---------------------------------------------------------------------------

def load_csv_gz(path: Path, label: str = "") -> pd.DataFrame:
    """
    Load an entire gzip-compressed TSV into one DataFrame.

    WARNING: loads the whole file into RAM. Use iter_csv_gz for large files.
    """
    path = Path(path)
    label = label or path.name

    compressed_size = path.stat().st_size
    chunks = []
    with (
        open(path, "rb") as raw,
        tqdm(
            desc=f"  Loading {label}",
            total=compressed_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=True,
        ) as bar,
    ):
        reader = pd.read_csv(
            raw,
            compression="gzip",
            sep="\t",
            low_memory=False,
            on_bad_lines="skip",
            chunksize=CSV_CHUNK_ROWS,
        )
        prev = 0
        for chunk in reader:
            cur = raw.tell()
            bar.update(cur - prev)
            prev = cur
            chunks.append(chunk)

    return pd.concat(chunks, ignore_index=True)


def load_all(paths: dict[str, Path]) -> list[pd.DataFrame]:
    """Load all files into memory. WARNING: very high RAM usage."""
    dfs = []
    for name, path in paths.items():
        print(f"\nLoading {name} …")
        dfs.append(load_csv_gz(path, label=name))
    return dfs


def merge_dataframes(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Concatenate DataFrames with aligned columns.
    WARNING: holds all data in RAM simultaneously.
    """
    print("\nMerging datasets …")
    merged = pd.concat(dfs, ignore_index=True, sort=False)
    print(f"  Total rows: {len(merged):,}   Columns: {len(merged.columns)}")
    return merged


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _coerce_for_sqlite(chunk: pd.DataFrame) -> pd.DataFrame:
    """
    SQLite INTEGER is 64-bit signed. Pandas can read mixed or oversized columns
    as Python object dtype containing arbitrary-precision ints, which overflow
    SQLite. Convert every object-dtype column to str (preserving NaN as NULL)
    so to_sql never sees a value outside SQLite's integer range.
    Numpy int64/float64 columns are unaffected.
    """
    for col in chunk.select_dtypes(include=["object", "str"]).columns:
        chunk[col] = chunk[col].where(chunk[col].isna(), chunk[col].astype(str))
    return chunk


# ---------------------------------------------------------------------------
# SQLite write
# ---------------------------------------------------------------------------

def write_sqlite(
    df: pd.DataFrame,
    db_path: Path,
    table: str = TABLE_NAME,
    if_exists: str = "replace",
) -> None:
    """Write a DataFrame to SQLite in chunks with a progress bar."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = len(df)
    print(f"\nWriting {total_rows:,} rows to {db_path} …")

    con = sqlite3.connect(db_path)
    try:
        with tqdm(
            total=total_rows,
            desc="  Writing SQLite",
            unit="rows",
            unit_scale=True,
            leave=True,
        ) as bar:
            for start in range(0, total_rows, CSV_CHUNK_ROWS):
                end = min(start + CSV_CHUNK_ROWS, total_rows)
                _coerce_for_sqlite(df.iloc[start:end]).to_sql(
                    table,
                    con,
                    if_exists="replace" if start == 0 else "append",
                    index=False,
                )
                bar.update(end - start)

        _create_index(con, table)
    finally:
        con.close()

    print(f"  Done — {db_path}")


# ---------------------------------------------------------------------------
# Streaming pipeline (low RAM) — preferred path
# ---------------------------------------------------------------------------

def stream_to_sqlite(
    paths: dict[str, Path],
    db_path: Path,
    table: str = TABLE_NAME,
) -> None:
    """
    Stream all files from *paths* directly into *table* in *db_path* without
    ever accumulating more than one chunk (~CSV_CHUNK_ROWS rows) in RAM.

    Steps:
      1. Read only headers from all files → union of columns.
      2. For each file, yield chunks → reindex to full column set → write.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print("Scanning headers …")
    all_columns = get_all_columns(paths)

    con = sqlite3.connect(db_path)
    # Increase cache and disable fsync for bulk insert performance
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute(f"PRAGMA cache_size = -{256 * 1024}")  # 256 MiB page cache

    # Drop upfront so pandas never issues DROP TABLE inside a live transaction
    con.execute(f'DROP TABLE IF EXISTS "{table}"')
    con.commit()

    total_written = 0

    try:
        for name, path in paths.items():
            print(f"\nStreaming {name} → SQLite …")
            for chunk in iter_csv_gz(path, all_columns, label=name):
                _coerce_for_sqlite(chunk).to_sql(
                    table,
                    con,
                    if_exists="append",
                    index=False,
                )
                total_written += len(chunk)

        print(f"\n  Total rows written: {total_written:,}")
        print("  Creating index …")
        _create_index(con, table)
        con.commit()
    finally:
        con.close()

    print(f"  Done — {db_path}")


def _create_index(con: sqlite3.Connection, table: str) -> None:
    """Create an index on 'code' or 'barcode' if the column exists."""
    cursor = con.cursor()
    existing = {r[1] for r in cursor.execute(f"PRAGMA table_info({table})")}
    for col in ("code", "barcode"):
        if col in existing:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})"
            )
            con.commit()
            print(f"  Indexed column '{col}'.")
            break


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run(
    out_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    paths: Optional[dict[str, Path]] = None,
) -> None:
    """
    Full pipeline: download → stream into SQLite (one chunk in RAM at a time).

    Parameters
    ----------
    out_dir : directory for .csv.gz files (default: ./ofdb_data/)
    db_path : output SQLite file          (default: ./barcodes.sqlite)
    paths   : {name: path} map; if given, download step is skipped
    """
    out_dir = Path(out_dir) if out_dir else DEFAULT_OUT_DIR
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    print("=" * 60)
    print("  Open*Facts Database downloader")
    print("=" * 60)

    if paths is None:
        print("\nStep 1 — Download\n")
        paths = download_all(out_dir)
    else:
        print("\nStep 1 — Download skipped (paths provided)\n")

    print("\nStep 2 — Stream into SQLite\n")
    stream_to_sqlite(paths, db_path)

    print("\nAll done.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download Open*Facts databases and write them to a SQLite file."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory for downloaded .csv.gz files (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Output SQLite path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading; assume files are already in --out-dir",
    )
    parser.add_argument(
        "--chunk-rows",
        type=int,
        default=CSV_CHUNK_ROWS,
        help=f"Rows per processing chunk (default: {CSV_CHUNK_ROWS}). Lower = less RAM.",
    )
    args = parser.parse_args()

    CSV_CHUNK_ROWS = args.chunk_rows

    pre_paths: Optional[dict[str, Path]] = None
    if args.skip_download:
        pre_paths = {ds["name"]: args.out_dir / ds["filename"] for ds in DATASETS}
        missing = [str(p) for p in pre_paths.values() if not p.exists()]
        if missing:
            print("Error: --skip-download specified but files are missing:")
            for m in missing:
                print(f"  {m}")
            sys.exit(1)

    run(out_dir=args.out_dir, db_path=args.db, paths=pre_paths)
