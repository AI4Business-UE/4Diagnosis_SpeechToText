# Pathology Transcription

This context covers recording and transcribing spoken descriptions of pathology examinations.

## Language

**Keyword**:
A domain-specific word or short phrase that may be spoken during a pathology examination and is supplied as vocabulary to support its recognition in transcription.
_Avoid_: Prompt, instruction

**Keyword Catalog**:
The shared collection of keywords used to support every pathology transcription.
_Avoid_: Per-recording vocabulary

**Patient Metadata**:
The five facts describing one examination recording: examined organ, patient full name, age, PESEL and examination description.
_Avoid_: Form data, patient data

**Transfer**:
A one-time hand-off of Patient Metadata values into a Target Page's form, leaving the form unsubmitted for human review.
_Avoid_: Migration, sync, save

**Target Page**:
A third-party browser page whose form receives a Transfer. Its source code is not ours.
_Avoid_: Destination, external site

**Field Mapping**:
The configuration binding each Patient Metadata field to the control on the Target Page that represents it.
_Avoid_: Selector config

**Transfer Profile**:
A named set of {Target Page URL pattern + Field Mappings} — the unit switched between environments (e.g. Mock, Production); exactly one is active.
_Avoid_: Environment, config preset

**Transfer Report**:
The outcome of one Transfer: per-field status (filled / not found / failed) and how it matched, plus overall result. It never contains the transferred values themselves.
_Avoid_: Log, result

**Mock Target Page**:
A locally served stand-in for the Target Page, used to develop and test Transfers until the real page's URL and Field Mapping are known.
**Reference transcript**:
The expected written account associated with a recording, used to assess how faithfully its spoken content was transcribed.

**Raw transcript**:
The text recognized from a recording before editorial correction.

**Corrected transcript**:
A revised transcription intended to preserve the recording's information while correcting recognition and formatting errors.

**Patient metadata reference**:
The patient information recorded alongside a sample, used to assess how well patient data was extracted from its recording.
_Avoid_: Gold NER reference, Expected output

**Patient metadata score**:
The share of a sample's Patient metadata reference entries that were extracted correctly, graded per entry and averaged over samples that have any.
_Avoid_: Metadata accuracy

**LLM judge**:
A language model that assesses how faithfully a corrected transcript preserves the reference transcript.

**Judge opt-out**:
A sample-level choice to exclude a recording from LLM judge assessment while retaining it in pipeline evaluation.
