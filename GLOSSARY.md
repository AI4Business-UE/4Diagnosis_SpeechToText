# Pathology Transcription

This context covers recording and transcribing spoken descriptions of pathology examinations.

## Language

**Keyword**:
A domain-specific word or short phrase that may be spoken during a pathology examination and is supplied as vocabulary to support its recognition in transcription.
_Avoid_: Prompt, instruction

**Keyword Catalog**:
The shared collection of keywords used to support every pathology transcription.
_Avoid_: Per-recording vocabulary

**Reference transcript**:
The expected written account associated with a recording, used to assess how faithfully its spoken content was transcribed.

**Raw transcript**:
The text recognized from a recording before editorial correction.

**Corrected transcript**:
A revised transcription intended to preserve the recording's information while correcting recognition and formatting errors.

**Gold NER reference**:
The reviewed expected annotation of patient, component, lesion, and fluid-sample information for a recording.
_Avoid_: Expected output

**LLM judge**:
A language model that assesses how faithfully a corrected transcript preserves the reference transcript.

**Judge opt-out**:
A sample-level choice to exclude a recording from LLM judge assessment while retaining it in pipeline evaluation.
