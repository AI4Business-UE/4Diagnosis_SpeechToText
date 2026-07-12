# STT Evaluation Dataset

This folder documents the local STT evaluation dataset used for the 4Diagnosis SpeechToText experiments.

## Local Source

The source dataset is stored outside the repository: [Google Drive folder](https://drive.google.com/drive/folders/1J5VXlJVQQC9Qi66E2UWqxaaoEeCy17uU).

## Audio Files

Audio files are copied locally to:

```text
backend/eval/data/stt/audio_samples
```

They are intentionally ignored by Git.

## Metadata

The metadata spreadsheet can be copied locally to:

```text
backend/eval/data/stt/metadata/samples_metadata.xlsx
```

They are intentionally ignored by Git.

## Intended Evaluation Flow

1. Download or copy `samples_metadata.xlsx` from the source dataset.
2. Resolve audio paths against `backend/eval/data/stt/audio_samples`.
3. Run the current STT pipeline on selected configurations.
4. Compare new outputs against the reference transcripts.
5. Compare current results with the historical baseline CSV files.

## Commands

Build the local STT sample list:

```bash
python3 backend/eval/build_stt_manifest.py
```

This creates an ignored local file:

```text
backend/eval/results/stt_manifest.csv
```

Run a small smoke evaluation:

```bash
python3 backend/eval/run_stt_eval.py \
  --limit 1 \
  --models whisper-small \
  --preprocessing baseline
```

Run selected models/configurations:

```bash
python3 backend/eval/run_stt_eval.py \
  --models whisper-small whisper-medical-pl \
  --preprocessing baseline vad noise_reduction
```

Summarize evaluation results:

```bash
python3 backend/eval/summarize_stt_results.py \
  --input backend/eval/results/stt_eval_results.csv \
  --output backend/eval/results/stt_eval_summary.csv
```
