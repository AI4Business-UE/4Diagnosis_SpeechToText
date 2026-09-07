"""Raport z end_to_end_results.csv: porównanie modeli/preprocessingu (STT), zdrowie
pipeline'u, latencja i zachowanie sanity. Działa też na częściowym CSV (w trakcie runu).

Uruchomienie (z katalogu głównego repo):
    python3 backend/eval/analyze_results.py
    python3 backend/eval/analyze_results.py backend/eval/results/end_to_end_results.csv

Uwaga: metryki NER (precision/recall/f1) NIE są tutaj — mierzysz je w etapie `ner`
(ner_results.csv). Poprawność guardraila sanity mierzysz na sanity_guardrail_eval_gold.jsonl.
"""

import sys
from pathlib import Path

import pandas as pd

DEFAULT = Path(__file__).resolve().parent / "results" / "end_to_end_results.csv"

# Metryki STT liczone raz na transkrypcję (nie na każdy tryb sanity).
STT_UNIT = ["sample_id", "pipeline_model", "preprocessing", "ner_strategy"]
STT_METRICS = [
    "stt_wer", "stt_cer",
    "stt_number_recall", "stt_number_precision",
    "stt_dimension_recall", "stt_dimension_precision",
    "stt_pesel_accuracy", "stt_medical_term_recall",
]


def _num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _fmt(df, floats=3):
    return df.round(floats).to_string()


def ner_report(df):
    """Raport dla ner_results.csv: precision/recall/f1 per strategia i encja."""
    ents = ["overall", "patient", "components", "lesions", "fluid_samples"]
    df = _num(df, [f"{e}_{m}" for e in ents for m in ("f1", "precision", "recall")] + ["duration_seconds"])
    print("=" * 70)
    print("NER — status")
    print("=" * 70)
    if "status" in df.columns:
        print(df["status"].value_counts().to_string())
    ok = df[df.get("status", "ok") == "ok"] if "status" in df.columns else df
    print()
    print("=" * 70)
    print("NER — f1 per strategia i encja (patient zawiera name/pesel/age)")
    print("=" * 70)
    cols = [f"{e}_f1" for e in ents if f"{e}_f1" in ok.columns]
    tab = ok.groupby("strategy")[cols].mean() if "strategy" in ok.columns else ok[cols].mean().to_frame().T
    tab["n"] = ok.groupby("strategy").size() if "strategy" in ok.columns else len(ok)
    print(_fmt(tab))
    print()
    print("=" * 70)
    print("NER — overall precision/recall per strategia")
    print("=" * 70)
    pr = [c for c in ("overall_precision", "overall_recall", "overall_f1") if c in ok.columns]
    if "strategy" in ok.columns and pr:
        print(_fmt(ok.groupby("strategy")[pr].mean()))
    print()
    print("Uwaga: PESEL na poziomie NER jest wliczony w `patient_f1` (razem z name/age),")
    print("nie jest osobno wyodrębniony. PESEL-transkrypcja osobno: `stt_pesel_accuracy` w end_to_end.")


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.exists():
        raise SystemExit(f"Brak pliku: {path}")

    df = pd.read_csv(path)
    print(f"Plik: {path}  ({len(df)} wierszy)\n")

    # Auto-wykrycie: ner_results.csv ma kolumnę overall_f1 (bare); end_to_end nie.
    if "overall_f1" in df.columns and "pipeline_model" not in df.columns:
        ner_report(df)
        return

    df = _num(df, STT_METRICS + ["stt_has_critical_error", "pipeline_duration_seconds", "score"])

    # ── Zdrowie ──────────────────────────────────────────────────────────────
    print("=" * 70)
    print("ZDROWIE PIPELINE'U")
    print("=" * 70)
    print(df["pipeline_status"].value_counts().to_string())
    err = df[df["pipeline_status"] == "error"]
    if len(err):
        print("\nbłędy (pipeline_error → ile):")
        print(err["pipeline_error"].str.slice(0, 90).value_counts().to_string())
        print("\nbłędy per preprocessing:")
        print(err["preprocessing"].value_counts().to_string())
    print()

    ok = df[df["pipeline_status"] == "ok"].copy()
    if not len(ok):
        print("(brak wierszy ok — nic więcej do policzenia)")
        return

    # ── STT: dedup do unikalnych transkrypcji ────────────────────────────────
    stt = ok.drop_duplicates(subset=[c for c in STT_UNIT if c in ok.columns])
    have = [m for m in STT_METRICS if m in stt.columns]

    def stt_table(by):
        g = stt.groupby(by)
        out = g[have].mean()
        out["%critical"] = g["stt_has_critical_error"].mean() * 100 if "stt_has_critical_error" in stt else float("nan")
        out["n"] = g.size()
        return out

    print("=" * 70)
    print("STT — średnie per MODEL (im niżej WER/CER, tym lepiej; recall/accuracy — wyżej)")
    print("=" * 70)
    print(_fmt(stt_table("pipeline_model")))
    print()
    print("=" * 70)
    print("STT — średnie per PREPROCESSING")
    print("=" * 70)
    print(_fmt(stt_table("preprocessing")))
    print()
    if "stt_wer" in stt.columns:
        print("=" * 70)
        print("STT — średni WER: MODEL × PREPROCESSING")
        print("=" * 70)
        piv = stt.pivot_table(index="pipeline_model", columns="preprocessing", values="stt_wer", aggfunc="mean")
        print(_fmt(piv))
        print()

    # ── Latencja ─────────────────────────────────────────────────────────────
    if "pipeline_duration_seconds" in ok.columns:
        print("=" * 70)
        print("LATENCJA — śr. czas pipeline.run [s] per model")
        print("=" * 70)
        lat = stt.groupby("pipeline_model")["pipeline_duration_seconds"].agg(["mean", "max", "count"])
        print(_fmt(lat, 1))
        print()

    # ── Sanity: zachowanie per tryb ──────────────────────────────────────────
    print("=" * 70)
    print("SANITY — zachowanie per tryb (na tych danych nie ma gold-flag, więc to nie poprawność)")
    print("=" * 70)
    if "sanity_mode" in ok.columns:
        g = ok.groupby("sanity_mode")
        san = pd.DataFrame({
            "n": g.size(),
            "śr_score": g["score"].mean(),
        })
        if "status" in ok.columns:
            st = ok.groupby(["sanity_mode", "status"]).size().unstack(fill_value=0)
            san = san.join(st)
        if "repair_applied" in ok.columns:
            san["repair_applied"] = ok.assign(_r=ok["repair_applied"].astype(str).str.lower().eq("true")).groupby("sanity_mode")["_r"].sum()
        print(_fmt(san))
        print()

    # ── Najczęstsze issue_codes ──────────────────────────────────────────────
    if "issue_codes" in ok.columns:
        codes = ok["issue_codes"].dropna().str.split("|").explode()
        codes = codes[codes.str.strip() != ""]
        if len(codes):
            print("=" * 70)
            print("SANITY — najczęstsze issue_codes")
            print("=" * 70)
            print(codes.value_counts().head(12).to_string())
            print()

    # ── Wyciszanie PESEL (synthetic) ─────────────────────────────────────────
    if "ignored_sanity_issue_count" in ok.columns:
        ign = pd.to_numeric(ok["ignored_sanity_issue_count"], errors="coerce").fillna(0)
        print(f"Wyciszone issue PESEL/wieku (synthetic): {int(ign.sum())} łącznie, "
              f"{int((ign > 0).sum())} wierszy z wyciszeniem")


if __name__ == "__main__":
    main()
