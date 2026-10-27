"""Coarse Spanish temporal evidence, independent of story IDs and source words.

This is a conservative candidate veto, not a meaning or completeness oracle.
"""


def category(token):
    if token.pos_ not in {'VERB', 'AUX'} or 'Fin' not in token.morph.get('VerbForm'):
        return None
    if 'Cnd' in token.morph.get('Mood'):
        return 'conditional'
    tense = token.morph.get('Tense')
    if any(value in tense for value in ('Past', 'Imp')):
        return 'past'
    if 'Fut' in tense:
        return 'future'
    if 'Pres' in tense:
        return 'present'
    return None


def profile(doc):
    result, evidence = set(), []
    for token in doc:
        value = category(token)
        if value is None:
            continue
        # Spanish compound perfect: present haber + participle denotes past,
        # while future/conditional perfect retains the auxiliary's time.
        if token.lemma_ == 'haber' and token.dep_.startswith('aux') and 'Part' in token.head.morph.get('VerbForm'):
            if value == 'present':
                value = 'past'
        result.add(value)
        evidence.append(dict(token=token.text, lemma=token.lemma_, category=value,
                             morph=str(token.morph), dependency=token.dep_))
    return dict(categories=sorted(result), evidence=evidence)
