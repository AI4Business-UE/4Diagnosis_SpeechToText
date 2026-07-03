from morfeusz2 import Morfeusz

analyzer = Morfeusz()

def perform_morphological_analysis(text):
  return analyzer.analyse(text)

def prepare_fts_text(text):
    morfeusz_output = perform_morphological_analysis(text)

    cleaned_tokens = {}

    for item in morfeusz_output:
        start, end, details = item[0], item[1], item[2]
        
        original, lemma, tag, _, qualifiers = details
        
        if tag == 'interp':
            continue
            
        if 'daw.' in qualifiers:
            continue
            
        clean_lemma = lemma.split(':')[0].lower()

        if start not in cleaned_tokens:
            cleaned_tokens[start] = {'lemma': clean_lemma, 'tag': tag}
        elif cleaned_tokens[start]['tag'] == 'ign' and tag != 'ign':
            cleaned_tokens[start] = {'lemma': clean_lemma, 'tag': tag}

    sorted_keys = sorted(cleaned_tokens.keys())
    fts_string = " ".join([cleaned_tokens[k]['lemma'] for k in sorted_keys])
    
    return fts_string