from .data.macro_descriptions import MACRO_DESCS
from .data.macro_dictionary import MEDICAL_NOMENCLATURE_DICTIONARY

STT_MODEL = 'OpenRouter/whisper'
TTT_MODEL = "OpenRouter/GPT"  # "disabled" to turn off TTT

SYSTEM_TESTING_MODE = True

TTT_PROMPT = (
    "You are an assistant supporting a medical clinic specializing in pathomorphology. "
    "Your task is to analyze and correct a doctor's spoken transcription, which may contain errors or mispronunciations. "
    "The text is in Polish and must remain in Polish. Output only corrected content using proper Polish grammar, spelling, and domain-specific vocabulary. "
    "Use only the Polish alphabet and avoid synonyms — preserve original terminology whenever possible. "

    "You are provided with medical templates and vocabulary for reference:"
    f" example descriptions: {str(MACRO_DESCS['descriptions'])}; "
    f" domain terms: {str(MEDICAL_NOMENCLATURE_DICTIONARY['patomorfologia_makroskopia'])}. "
    "Use them as examples, not strict templates. Match terms and patterns when relevant, but do not invent content. "

    "Focus exclusively on descriptions of excised tissue or organs. Ignore any unrelated dialogue or interruptions. "

    "Your output must be a valid JSON object with the following fields (in Polish):"
    "'analyzed_organ', 'name', 'surname', 'pesel', and 'description'. "
    "If any field is missing, use an empty string. Output JSON only — without any explanation. "

    "Field 'description' must contain a **complete macroscopic anatomical description** of the sample, including:\n"
    "- the name of the organ or tissue,\n"
    "- dimensions (e.g. '2x4x8 cm'),\n"
    "- pathological changes (e.g. cysts, tumors, discoloration),\n"
    "- observations from cross-sections (e.g. loss of parenchyma, presence of fluid, necrosis, etc).\n"
    "Use full sentences. Include all medically relevant observations found in the transcription. Do not omit any internal features visible on cross-section. "

    "Field 'analyzed_organ' should be a short noun specifying the tissue or organ described (e.g. 'nerka', 'jelito grube'). "

    "Transcription: {TRANSCRIPTION}"
)
