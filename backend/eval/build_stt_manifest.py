from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = REPO_ROOT / "backend/eval/data/stt/metadata/samples_metadata.xlsx"
DEFAULT_AUDIO_DIR = REPO_ROOT / "backend/eval/data/stt/audio_samples"
DEFAULT_OUTPUT = REPO_ROOT / "backend/eval/results/stt_manifest.csv"


def build_manifest(metadata_path: Path, audio_dir: Path) -> pd.DataFrame:
    metadata = pd.read_excel(metadata_path)
    rows = []

    for _, row in metadata.iterrows():
        file_name = row.get("nazwa pliku")
        reference = row.get("tekst referencyjny")
        if pd.isna(file_name) or pd.isna(reference):
            continue

        audio_path = audio_dir / str(file_name)
        rows.append({
            "sample_id": row.get("id", ""),
            "audio_file": str(file_name),
            "audio_path": str(audio_path),
            "ref_transcript": str(reference),
            "source": "local_stt_dataset",
            "speaker": row.get("twórca", ""),
            "format": row.get("format", ""),
            "audio_exists": audio_path.exists(),
        })

    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local STT sample list from metadata XLSX.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_manifest(args.metadata, args.audio_dir)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(args.output, index=False)

    total = len(manifest)
    found = int(manifest["audio_exists"].sum()) if total else 0
    print(f"Wrote STT sample list: {args.output}")
    print(f"Rows: {total}, audio found: {found}, missing: {total - found}")


if __name__ == "__main__":
    main()
