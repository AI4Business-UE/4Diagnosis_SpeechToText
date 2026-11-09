# Replace manual Gold NER annotation with the deterministic Patient metadata score

Evaluating NER quality required hand-maintained, reviewed Gold NER references (`ner_references.json`), whose annotation cost we were no longer willing to pay. We decided to drop that machinery entirely and grade only the extracted Patient fields against the Patient metadata reference recorded in `samples_metadata.xlsx` (`imię pacjenta`, `nazwisko pacjenta`, `wiek`, `PESEL`), scored deterministically per sample. Component, lesion, and fluid-sample outputs remain surfaced in the review workbook but are no longer reference-graded; transcript WER/CER and the LLM judge are unaffected.

Rejected alternatives: keeping both paths (two divergent sources of truth for patient data), and extending the reviewed-reference workflow (accurate but manually expensive). Comparison grades reference-set fields only (recall-oriented), so hallucinated extra extraction is not penalized — a known, deliberate limitation.

Note: this scope is a subject of future change. If entity-level scoring for components, lesions, or fluid samples becomes necessary, expect to reintroduce a graded reference for them — preferably generated from reviewable sources rather than fully manual annotation.
