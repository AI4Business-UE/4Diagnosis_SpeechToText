"""
Szybki test pipeline'u — uruchom z folderu backend/src/app_stt/pipeline:
    python test_pipeline.py

Lub z backend/src/:
    python -m app_stt.pipeline.test_pipeline

Wymagania:
    - OPENROUTER_API_KEY w pliku .env (lub zmiennej środowiskowej)
    - pip install openai python-dotenv pydantic qdrant_client morfeusz2 transformers

Opcjonalnie (do pełnego testu z audio):
    - pip install torch librosa soundfile
    - pip install noisereduce  (jeśli use_noise_reduction=True)
"""

import json
import sys
import logging
from pathlib import Path


# ── dodaj pakiet do ścieżki jeśli uruchamiamy bezpośrednio ──────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


SAMPLE_TRANSCRIPT = (
    "Pacjentka Justyna Nowacka, numer PESEL 82050298239, lat 31. "
    "Materiał o wymiarach 5,5 x 4,5 x 3 cm. "
    "W tym guz o wymiarach 3,5 x 3,0 x 3,5 cm barwy żółtej z centralnymi wylewami krwawymi. "
    "Margines oznaczono tuszem czarnym."
)


def _setup_logging(): 
    logging.basicConfig(handlers=[logging.StreamHandler()], level=logging.INFO)


def test_ner_split(transcription = None):
    print("\n=== TEST: NER Split ===")
    from app_stt.pipeline.stages.ner.split import SplitNERStrategy

    strategy = SplitNERStrategy()
    result = strategy.extract(transcription or SAMPLE_TRANSCRIPT)

    print(json.dumps(result.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    assert result.patient.last_name and result.patient.first_name, "Patient extraction failed"
    assert len(result.components) > 0, "Component extraction failed"
    assert len(result.lesions) > 0, "Lesion extraction failed"
    print("✓ Split NER passed")
    return result


def test_ner_chained(transcription = None):
    print("\n=== TEST: NER Chained ===")
    from app_stt.pipeline.stages.ner.chained import ChainedNERStrategy

    strategy = ChainedNERStrategy()
    result = strategy.extract(transcription or SAMPLE_TRANSCRIPT)

    print(json.dumps(result.model_dump(exclude_none=True), indent=2, ensure_ascii=False))
    assert result.patient.last_name and result.patient.first_name, "Patient extraction failed"
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


def test_rag(ner_extraction_path: str):
    print(f"\n=== TEST: RAG ({ner_extraction_path}) ===")
    _setup_logging()
    
    from app_stt.pipeline import PipelineConfig
    from app_stt.pipeline.stages.ner import ExtractionResult
    from app_stt.pipeline.stages.rag.qdrant import QdrantClientMode, QdrantRetriever, index_database
    
    with open(ner_extraction_path, 'r') as f:
        ner_extraction = ExtractionResult(**json.load(f))
     
    cfg = PipelineConfig(qdrant_client_mode=QdrantClientMode.IN_MEMORY)
    
    index_database(cfg)
    retriever = QdrantRetriever(cfg)
    results = retriever.retrieve_fusion(components=ner_extraction.components, 
                                        lesions=ner_extraction.lesions,
                                        fluids=ner_extraction.fluid_samples,
                                        top_k=cfg.top_k_results,
                                        fusion_type=cfg.qdrant_fusion_type)
    assert len(results) > 0, "No results returned from RAG"
    print("Results:", results)
    print("✓ RAG passed")
    
    return results


def test_answerer():
    from app_stt.pipeline import PipelineConfig
    from app_stt.pipeline.stages.ner import ExtractionResult
    from app_stt.pipeline.stages.answerer import NoFillAnswerer
    _setup_logging()
    print(f"\n=== TEST: ANSWERER ===")

    cfg = PipelineConfig(answerer_llm_model = "openai/gpt-4o")
    answerer = NoFillAnswerer(cfg.answerer_llm_model)

    rag_templates = [
        'Trzon o wymiarach6x []x[] cm z szyjką długości [] cm, tarczą średnicy [] cm jajowodem prawy długości [] cm jajnikiem '
        'prawym []x[]x[] cm jajowodem lewym długości [] cm, jajnikiem lewym o wymiarach []x[]x[] cm endometrium wypełnione '
        'przez polipa o wymiarach []x[]x[] cm ponadto obecne guzki o morfologii mięśniaków, największy z nich o średnicy [] '
        'cm. polip endometrium przylega do lewego rogu, bez jawnego naciekania ściany.Polip pobrano w całości.',
        'Trzon macicy o wymiarach []x[]x[] cm wraz z jajowodem prawy o długości [] cm, lewym o długości [] cm, jajnikiem '
        'prawym o wymiarach []x[]x[] cm i lewym o wymiarach []x[]x[] cm. Materiał wielomiejscowo rozerwany-orientacja '
        'topograficzna utrudniona. ',
        'Jelito o długości [] cm, [mezorectum z płytkimi ubytkami] [mezorectum zachowane] [mezorectum z ubytkami sięgającymi '
        'błony mięśniowej] [obecności mezorectum nie stwierdza się]. Trzon o wymiarach []x[]x[] cm z szyjką o długości [] cm. '
        'Tarcza szyjki o średnicy [] cm. Jajowód prawy o długości [] cm.  Jajnik prawy o wymiarach []x[]x[] cm.  Jajowód lewy '
        'o długości []',
        'Jajowód o długości [] cm.',
        'Stożek szyjki macicy o wymiarach []x[] cm, długości [] cm. Margines pochwowy oznaczono kolorem '
        '[zielonym][czerwonym][niebieskim][czarnym], margines kanału szyjki oznaczono kolorem '
        '[zielonym][czerwonym][niebieskim][czarnym]. Pobrano "co godzina" wg wskazówek zegara począwszy od godziny [].'
    ]
    ner_extraction = ExtractionResult(**{
        "patient": {
            "first_name": "Wanda",
            "last_name": "Walcerzak",
            "age": 44
        },
        "components": [
            {
            "name": "macica",
            "dim_x": 5.0,
            "dim_y": 4.0,
            "dim_z": 3.5,
            "unit": "cm"
            },
            {
            "name": "jajowód prawy",
            "length": 5.0,
            "unit": "cm"
            },
            {
            "name": "jajowód lewy",
            "length": 6.0,
            "unit": "cm"
            },
            {
            "name": "jajnik prawy",
            "dim_x": 2.0,
            "dim_y": 1.5,
            "unit": "cm"
            },
            {
            "name": "jajnik lewy",
            "dim_x": 2.8,
            "dim_y": 1.5,
            "dim_z": 1.0,
            "unit": "cm"
            }
        ],
        "lesions": [],
        "fluid_samples": []
    })
    transcription = """
        Dobra, już zaczynamy. Mamy pacjentkę, wandę, wandę, walcerzak. PESAL 062309938013. 
        lat 44, szon macicy o wymiarach 5 na 4 na 3,5 cm, wraz z jajowodem, jajowodem prawym o długości 5 cm, 
        ...lewym o długości pięciu centymetrów, lewym o długości piję, nie, przepraszam, 
        sześciu centymetrów, jajnikiem prawym o wymiarach dwa na jeden i pół centymetra, 
        a lewym o wymiarach dwadzieścia osiem, nie, przepraszam dwa, przycinek 8 na półtora na jeden centymetr. 
        Materiał wielomistowo jest rozerwany, orientacja topograficzna utrudniona."""

    corrected_transcription = answerer.correct_transcription(transcription, rag_templates, ner_extraction)
    assert corrected_transcription
    print("Corrected transcripiton:", corrected_transcription)
    print("✓ Answerer passed")


def test_full_pipeline(audio_path: str):
    print(f"\n=== TEST: Full Pipeline ({audio_path}) ===")
    _setup_logging()
    import pprint
    
    from app_stt.pipeline import Pipeline, PipelineConfig
    from app_stt.pipeline.stages.rag.qdrant import QdrantClientMode
    from app_stt.pipeline.stages.rag.qdrant import index_database

    cfg = PipelineConfig(ner_strategy="chained", use_vad=False, qdrant_client_mode=QdrantClientMode.IN_MEMORY, top_k_results=5)
    index_database(cfg)
    pipeline = Pipeline(cfg)
    result = pipeline.run(audio_path)

    print("Transcript:", result["transcript"][:200], "...")
    print("Entities:", json.dumps(result["entities"], indent=2, ensure_ascii=False))
    print("Retrieved Templates:")
    pprint.pp(result["retrieved_templates"], width=120)
    print("Corrected transcript:", result["corrected_transcript"])
    print("✓ Full pipeline passed")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline test runner")
    parser.add_argument("--audio", type=str, default=None, help="Path to audio file for full pipeline test")
    parser.add_argument("--transcript", type=str, default=None, help="Custom transcript to run NER extraction on")
    parser.add_argument("--ner_extraction_path", type=str, default=None, help="Path to sample NER extraction JSON")
    parser.add_argument("--test", choices=[
        "ner", "split", "chained", "preprocessing", "rag", "answerer", "full", "all" 
    ], default="ner")
    args = parser.parse_args()

    if args.test in ("ner", "split", "all"):
        test_ner_split(args.transcript)

    if args.test in ("ner", "chained", "all"):
        test_ner_chained(args.transcript)

    if args.test in ("preprocessing", "all") and args.audio:
        test_preprocessing(args.audio)

    if args.test in ("answerer", "all"):
        test_answerer()
        
    if args.test in ("rag", "all") and args.ner_extraction_path:
        test_rag(args.ner_extraction_path)

    if args.test == "full":
        if not args.audio:
            print("ERROR: --audio required for full pipeline test")
            sys.exit(1)
        test_full_pipeline(args.audio)

    print("\n✓ All requested tests passed")
