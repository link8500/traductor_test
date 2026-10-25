"""Conservative, offline QA signals over unedited OCR and translation outputs.

Signals are review candidates, never semantic approvals or training examples.
No chapter-specific vocabulary or expected translations are used here.
"""
import functools
import json
import pathlib
import re

RULE_VERSION = 3
TOKENS = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
PROMOTION = re.compile(
    r'asura|olympus|discord|patreon|https?[:/]|scanlation|translator|typesetter|'
    r'proofreader|redraw|cleaner|all rights reserved', re.I)
# Punctuation inside or attached to a letter sequence. A standalone ampersand,
# ordinary quotation, hyphen, money amount or exclamation is not malformed.
MALFORMED = re.compile(
    r'[A-Za-zÀ-ÿ]{2,}[&$|{}@#][A-Za-zÀ-ÿ]*|'
    r'[&$|{}@#][A-Za-zÀ-ÿ]{3,}|[A-Za-zÀ-ÿ]{2,}[0-9][A-Za-zÀ-ÿ]{2,}')
ENGLISH_PHRASE = re.compile(
    r"\b(?:i['’]m|i['’]ve|i['’]ll|you['’]re|you['’]ve|we['’]re|they['’]re)\b|"
    r'\b(?:i am|i was|i have|i will|you are|you have|you will|it is|it was|'
    r'this is|that is|there is|there are|do you|did you|are you|'
    r'of the|in the|to the|with the|for the|from the)\b', re.I)
SPANISH_NEGATION = re.compile(r'\b(?:no|nunca|jamás|tampoco|ni|sin)\b', re.I)
ENGLISH_NEGATION = re.compile(r"\b(?:not|never|without|cannot|can['’]t|"
                               r"don['’]t|doesn['’]t|didn['’]t|isn['’]t|"
                               r"wasn['’]t|won['’]t|wouldn['’]t|couldn['’]t)\b", re.I)

LABELS = {
    'missing_output': 'No produjo traducción',
    'malformed_source': 'Palabra reconocida con símbolos o dígitos intercalados',
    'malformed_output': 'Palabra de salida con símbolos o dígitos intercalados',
    'english_phrase_output': 'Secuencia inglesa conservada en la salida',
    'unchanged_sentence': 'Oración conservada sin traducir',
    'repeated_output': 'Repetición consecutiva en la salida',
    'possible_lost_negation': 'Posible negación perdida; requiere cotejo de sentido',
    'possible_truncation': 'Salida muy corta respecto al texto reconocido',
    'mixed_case_source': 'Alternancia anómala de mayúsculas dentro de palabras reconocidas',
    'unresolved_copied_token': 'Palabra copiada sin resolver; puede ser un nombre o una lectura corrupta',
}


@functools.lru_cache(maxsize=1)
def whole_pieces():
    # This is a subword vocabulary, NOT a complete spelling dictionary. Absence
    # only raises a review candidate when the same token survives in the output.
    path = pathlib.Path(__file__).resolve().parents[1] / 'assets/models/opus-en-es/tokenizer.json'
    return {piece[1:].casefold() for piece in json.loads(path.read_text(encoding='utf-8'))['tokens']
            if piece.startswith('\u2581')}


def tokens(text):
    return TOKENS.findall(text.casefold())


def signals(row):
    source = row.get('source', '')
    target = row.get('translation', '')
    result = []
    if row.get('error') or not target.strip():
        result.append('missing_output')
    if PROMOTION.search(source):
        return result
    source_words, target_words = tokens(source), tokens(target)
    if MALFORMED.search(source):
        result.append('malformed_source')
    if MALFORMED.search(target):
        result.append('malformed_output')
    # Two or more lower-to-upper transitions within a long word are common in
    # failed stylized lettering. Short mixed-case names and camelCase identifiers
    # remain possible false positives, so this is only a review signal.
    if any(len(word) >= 8 and len(re.findall(r'[a-z][A-Z]', word)) >= 2
           for word in re.findall(r'[A-Za-z]+', source)):
        result.append('mixed_case_source')
    if ENGLISH_PHRASE.search(target):
        result.append('english_phrase_output')
    shared = set(source_words) & set(target_words)
    if any(len(word) >= 3 and word.isalpha() and word not in whole_pieces() for word in shared):
        result.append('unresolved_copied_token')
    if len(source_words) >= 4 and source_words == target_words:
        result.append('unchanged_sentence')
    # Repeated two-word chunks catch decoder loops, without flagging a stutter.
    if len(target_words) >= 8 and any(
            target_words[i:i+2] == target_words[i+2:i+4] == target_words[i+4:i+6]
            for i in range(len(target_words)-5)):
        result.append('repeated_output')
    if len(source_words) >= 6 and ENGLISH_NEGATION.search(source) and not SPANISH_NEGATION.search(target):
        result.append('possible_lost_negation')
    if len(source_words) >= 12 and 0 < len(target_words) < .3 * len(source_words):
        result.append('possible_truncation')
    return result
