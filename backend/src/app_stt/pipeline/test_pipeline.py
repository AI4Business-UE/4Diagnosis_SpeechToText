"""
Szybki test pipeline'u — uruchom z folderu backend/src/app_stt/pipeline:
    python test_pipeline.py

Lub z backend/src/:
    python -m app_stt.pipeline.test_pipeline

Wymagania:
    - OPENROUTER_API_KEY w pliku .env (lub zmiennej środowiskowej)
    - pip install openai python-dotenv pydantic

Opcjonalnie (do pełnego testu z audio):
    - pip install torch transformers librosa soundfile
    - pip install noisereduce  (jeśli use_noise_reduction=True)
"""

import json
import sys
from pathlib import Path

# ── dodaj pakiet do ścieżki jeśli uruchamiamy bezpośrednio ──────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


SAMPLE_TRANSCRIPT = (
    "Pacjentka Justyna Nowacka, numer PESEL 82050298239, lat 31. "
    "Materiał o wymiarach 5,5 x 4,5 x 3 cm. "
    "W tym guz o wymiarach 3,5 x 3,0 x 3,5 cm barwy żółtej z centralnymi wylewami krwawymi. "
    "Margines oznaczono tuszem czarnym."
)


def test_ner_split():
    print("\n=== TEST: NER Split ===")
    from app_stt.pipeline.stages.ner.split import SplitNERStrategy

    strategy = SplitNERStrategy()
    result = strategy.extract(SAMPLE_TRANSCRIPT)

    print(json.dumps(result.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    assert result.patient.last_name == "Nowacka", "Patient extraction failed"
    assert len(result.components) > 0, "Component extraction failed"
    assert len(result.lesions) > 0, "Lesion extraction failed"
    print("✓ Split NER passed")
    return result


def test_ner_chained():
    print("\n=== TEST: NER Chained ===")
    from app_stt.pipeline.stages.ner.chained import ChainedNERStrategy

    strategy = ChainedNERStrategy()
    result = strategy.extract(SAMPLE_TRANSCRIPT)

    print(json.dumps(result.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    assert result.patient.last_name == "Nowacka", "Patient extraction failed"
    assert len(result.lesions) > 0, "Lesion extraction failed"
    # W chained lesion powinien mieć component_index
    has_component_index = any(l.component_index is not None for l in result.lesions)
    print(f"  component_index assigned: {has_component_index}")
    print("✓ Chained NER passed")
    return result


def test_preprocessing(audio_path: str):
    print(f"\n=== TEST: Preprocessing ({audio_path}) ===")
    from app_stt.pipeline.config import PipelineConfig
    from app_stt.pipeline.stages.preprocessing import AudioPreprocessor

    cfg = PipelineConfig(use_volume_normalization=True, use_vad=False)
    preprocessor = AudioPreprocessor(cfg)
    result = preprocessor.process(audio_path)

    print(json.dumps(result, indent=2))
    assert result["status"] == "ok", f"Preprocessing failed: {result.get('error')}"
    print("✓ Preprocessing passed")
    return result


def test_full_pipeline(audio_path: str):
    print(f"\n=== TEST: Full Pipeline ({audio_path}) ===")
    from app_stt.pipeline import Pipeline, PipelineConfig

    cfg = PipelineConfig(ner_strategy="chained", use_vad=False)
    pipeline = Pipeline(cfg)
    result = pipeline.run(audio_path)

    print("Transcript:", result["transcript"][:200], "...")
    print("Entities:", json.dumps(result["entities"], indent=2, ensure_ascii=False))
    print("Retrieved Templates (max 5):", result["retrieved_templates"][:5])
    print("✓ Full pipeline passed")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline test runner")
    parser.add_argument("--audio", type=str, default=None, help="Path to audio file for full pipeline test")
    parser.add_argument("--test", choices=["ner", "split", "chained", "preprocessing", "full", "all"], default="ner")
    args = parser.parse_args()

    if args.test in ("ner", "split", "all"):
        test_ner_split()

    if args.test in ("ner", "chained", "all"):
        test_ner_chained()

    if args.test in ("preprocessing", "all") and args.audio:
        test_preprocessing(args.audio)

    if args.test == "full":
        if not args.audio:
            print("ERROR: --audio required for full pipeline test")
            sys.exit(1)
        test_full_pipeline(args.audio)

    print("\n✓ All requested tests passed")
