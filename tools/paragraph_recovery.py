"""Blind, conservative selection of paragraph re-reads for experimental QA.

Only pixels/OCR evidence and the existing model vocabulary are consulted.
No comic transcripts, Spanish references or expected answers are inputs.
"""
import functools
import json
import pathlib
import re


def key(text):
    return ''.join(c.upper() for c in text if c.isascii() and c.isalnum())


def words(text):
    return [value for part in text.split() if (value := key(part))]


@functools.lru_cache(maxsize=1)
def known_words():
    root = pathlib.Path(__file__).resolve().parents[1]
    data = json.loads((root/'assets/models/opus-en-es/tokenizer.json').read_text(encoding='utf-8'))
    return {key(piece[1:]) for piece in data['tokens'] if piece.startswith('\u2581')}


def known_word(value):
    return value in known_words() and (len(value) > 1 or value in {'A', 'I'})


def alignment(left, right):
    costs = [[0]*(len(right)+1) for _ in range(len(left)+1)]
    for i in range(len(left)+1):
        costs[i][0] = i
    for j in range(len(right)+1):
        costs[0][j] = j
    for i, a in enumerate(left, 1):
        for j, b in enumerate(right, 1):
            costs[i][j] = min(costs[i-1][j]+1, costs[i][j-1]+1, costs[i-1][j-1]+(a != b))
    trace = []
    i, j = len(left), len(right)
    while i or j:
        if i and j and costs[i][j] == costs[i-1][j-1]+(left[i-1] != right[j-1]):
            trace.append((i-1, j-1)); i -= 1; j -= 1
        elif i and costs[i][j] == costs[i-1][j]+1:
            trace.append((i-1, None)); i -= 1
        else:
            trace.append((None, j-1)); j -= 1
    return costs[-1][-1], list(reversed(trace))


def agreed_positions(text, native):
    _, trace = alignment(text, native)
    return {i for i, j in trace if i is not None and j is not None and text[i] == native[j]}


NEGATIVE = {'NO', 'NOT', 'NEVER', 'NONE', 'NOTHING', 'NOBODY', 'WITHOUT', 'CANNOT',
            'CANT', 'DONT', 'DOESNT', 'DIDNT', 'ISNT', 'ARENT', 'WASNT', 'WERENT',
            'WONT', 'WOULDNT', 'COULDNT', 'SHOULDNT', 'HASNT', 'HAVENT', 'HADNT'}


def protected_numbers(values):
    result = []
    for value in values:
        digits = [(i, c) for i, c in enumerate(value) if c.isdigit()]
        if not digits:
            continue
        embedded_confusion = sum(c.isalpha() for c in value) >= 3 and all(
            c in '0158' and 0 < i < len(value)-1 and value[i-1].isalpha() and value[i+1].isalpha()
            for i, c in digits)
        if not embedded_confusion:
            result.append(value)
    return result


def decide(old, old_native, near, near_native, context, context_native):
    if key(near) != key(context):
        return False, 'crop_readers_disagree'
    if key(old) == key(near):
        return False, 'unchanged'
    a, b = words(old), words(near)
    if not a or not b or max(len(a), len(b)) > 150:
        return False, 'unsupported_length'
    before_key, after_key = key(old), key(near)
    edits, _ = alignment(before_key, after_key)
    if edits > max(2, .35*max(len(before_key), len(after_key))):
        return False, 'large_text_change'
    if protected_numbers(a) != protected_numbers(b):
        return False, 'numbers_changed'
    if sorted(w for w in a if w in NEGATIVE) != sorted(w for w in b if w in NEGATIVE):
        return False, 'negation_changed'
    _, trace = alignment(a, b)
    native_old = agreed_positions(a, words(old_native))
    native_near = agreed_positions(b, words(near_native))
    native_context = agreed_positions(b, words(context_native))
    for i, j in trace:
        if j is None:
            return False, 'word_removed'
        if i is not None and a[i] == b[j]:
            continue
        if j not in native_near or j not in native_context:
            return False, 'changed_word_without_system_agreement'
        if not known_word(b[j]):
            return False, 'new_word_not_in_vocabulary'
        if i is not None and known_word(a[i]) and i in native_old:
            return False, 'original_known_word_already_corroborated'
    return True, 'two_crops_and_system_support_changed_words'


def area(box):
    return max(0, box[2]-box[0])*max(0, box[3]-box[1])


def choose_region(case, result):
    x, y = result['crop_bounds'][:2]
    old = case['bounds']
    proposed = []
    for row in result['regions']:
        bounds = [row['bounds'][0]+x, row['bounds'][1]+y, row['bounds'][2]+x, row['bounds'][3]+y]
        intersection = max(0, min(old[2], bounds[2])-max(old[0], bounds[0])) * max(0, min(old[3], bounds[3])-max(old[1], bounds[1]))
        if intersection > .6*min(area(old), area(bounds)):
            proposed.append(dict(**row, original_bounds=bounds))
    if len(proposed) != 1:
        return None, 'missing_or_split_region'
    selected = proposed[0]
    if not .5*area(old) <= area(selected['original_bounds']) <= 1.8*area(old):
        return None, 'large_geometry_change'
    return selected, None
