"""Apply a blind paragraph recovery policy and run the unchanged offline NMT.

This produces experimental QA outputs; no reference answer enters selection
or translation, and no production inference file is overwritten.
"""
import argparse
import collections
import json
import pathlib
import subprocess

from audit_corpus_quality import ROOT, QA, CURRENT, read, records, digest, atomic
from paragraph_recovery import decide, choose_region, area, words, agreed_positions, known_word, key, alignment
from probe_reviewed_lettering import ordered as reading_order

OUT = QA / 'paragraph-probe8011'


def matching(old, rows):
    found = []
    for row in rows:
        if row['image'] != old['source_image']:
            continue
        a, b = old['bounds'], row['bounds']
        intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
        if intersection > .65*min(area(a), area(b)):
            found.append(row)
    return found


def supported_words(region, result, original_box):
    offset = region['crop_bounds']
    selected = []
    for line in result['lines']:
        if line['confidence'] < .85:
            continue
        quad = line['quad']
        box = [min(quad[::2])+offset[0], min(quad[1::2])+offset[1],
               max(quad[::2])+offset[0], max(quad[1::2])+offset[1]]
        intersection = max(0,min(box[2],original_box[2])-max(box[0],original_box[0])) * max(0,min(box[3],original_box[3])-max(box[1],original_box[1]))
        if intersection > .5*min(area(box),area(original_box)):
            selected.append(line)
    return reading_order(selected)


def dual_support(text, region, reader_rows, original_box):
    target = words(text)
    agreement = set(range(len(target)))
    for family in ['latin-v5', 'english-v4']:
        reading = supported_words(region, reader_rows[family][region['chapter']], original_box)
        agreement &= agreed_positions(target, words(reading))
    return ' '.join(word if i in agreement else f'UNSUPPORTEDWORD{i}' for i, word in enumerate(target))


def detector_ensemble(seed, region, reader_rows):
    """Choose actual detector reads, retaining their geometric correspondence."""
    primary = reader_rows['latin-v5'][region['chapter']]['lines']
    secondary = reader_rows['english-v4'][region['chapter']]['lines']
    assert len(primary) == len(secondary)
    selected = []
    support_by_quad = {}
    ox, oy = region['crop_bounds'][:2]
    original_box = seed['bounds']
    bounds = []
    for left, right in zip(primary, secondary):
        assert left['quad'] == right['quad'], 'Detector geometry differs between reader runs'
        if left['confidence'] < .65:
            continue
        q = left['quad']
        box = [min(q[::2])+ox, min(q[1::2])+oy, max(q[::2])+ox, max(q[1::2])+oy]
        intersection = max(0,min(box[2],original_box[2])-max(box[0],original_box[0])) * max(0,min(box[3],original_box[3])-max(box[1],original_box[1]))
        if intersection <= .5*min(area(box),area(original_box)):
            continue
        original_parts = [p for p in left['text'].split() if key(p)]
        other_parts = [p for p in right['text'].split() if key(p)]
        a, b = [key(p) for p in original_parts], [key(p) for p in other_parts]
        _, links = alignment(a, b)
        replacements = {}
        supported = set()
        for i, j in links:
            if i is None or j is None:
                continue
            if a[i] == b[j] and right['confidence'] >= .65:
                supported.add(i)
            elif not known_word(a[i]) and known_word(b[j]) and right['confidence'] >= .85:
                edits, _ = alignment(a[i], b[j])
                if edits <= max(1, .3*max(len(a[i]),len(b[j]))):
                    replacement = other_parts[j]
                    letters = [c for c in original_parts[i] if c.isascii() and c.isalpha()]
                    if letters and all(c.isupper() for c in letters):
                        replacement = replacement.upper()
                    replacements[i] = replacement;supported.add(i)
        parts = [replacements.get(i,p) for i,p in enumerate(original_parts)]
        support = [p if i in supported else f'UNSUPPORTEDWORD{i}' for i,p in enumerate(parts)]
        entry = dict(left, text=' '.join(parts))
        selected.append(entry)
        support_by_quad[tuple(q)] = ' '.join(support)
        bounds.append(box)
    if not selected:
        return None, 'no_detector_reading'
    text = reading_order(selected)
    support = reading_order([dict(r, text=support_by_quad[tuple(r['quad'])]) for r in selected])
    box = [min(b[0] for b in bounds), min(b[1] for b in bounds), max(b[2] for b in bounds), max(b[3] for b in bounds)]
    if not .5*area(original_box) <= area(box) <= 1.8*area(original_box):
        return None, 'large_geometry_change'
    return dict(source=text, original_bounds=box, support=support), None


def build(independent=False, ensemble=False):
    suffix = '-ensemble-cased' if ensemble else '-independent' if independent else ''
    output = OUT / ('selection'+suffix+'.json')
    if output.exists():
        return read(output)
    sample = read(QA / 'corpus-review-sample/sample.json')
    probe = read(OUT / 'results.json')
    variants = collections.defaultdict(dict)
    for case in probe['cases']:
        variants[case['id']][case['variant']] = case
    readers = {}
    if independent:
        for family in ['latin-v5', 'english-v4']:
            values = records(OUT/(family+'.jsonl'))
            assert len(values) == 248, 'Independent reader pass is not complete'
            readers[family] = {r['chapter']:r for r in values}
    judgments = {r['id']: r for r in read(ROOT/'benchmarks/full-comics/corpus-semantic-review.json')['entries']}
    cases = []
    for seed in sample['cases']:
        current = QA / CURRENT / (seed['chapter']+'-en.jsonl')
        folder = CURRENT if current.with_name(seed['chapter']+'-en.done.json').exists() else seed['current_folder']
        path = QA / folder / (seed['chapter']+'-en.jsonl')
        rows = matching(seed, records(path))
        if len(rows) != 1:
            cases.append(dict(id=seed['id'], selected=False, reason='ambiguous_control_region',
                              control_folder=folder, needs_visual_review=True))
            continue
        old = rows[0]
        selected, reason = False, None
        if ensemble:
            near, near_error = detector_ensemble(seed, variants[seed['id']]['near'], readers)
            context, context_error = detector_ensemble(seed, variants[seed['id']]['context'], readers)
        else:
            near, near_error = choose_region(seed, variants[seed['id']]['near'])
            context, context_error = choose_region(seed, variants[seed['id']]['context'])
        if near is None or context is None:
            reason = near_error or context_error
        else:
            near_native = near['support'] if ensemble else dual_support(near['source'], variants[seed['id']]['near'], readers, near['original_bounds']) if independent else ' '.join(w['text'] for w in near.get('native_words', []))
            context_native = context['support'] if ensemble else dual_support(context['source'], variants[seed['id']]['context'], readers, context['original_bounds']) if independent else ' '.join(w['text'] for w in context.get('native_words', []))
            selected, reason = decide(old['source'], ' '.join(w['text'] for w in old.get('native_words', [])),
                near['source'], near_native, context['source'], context_native)
        unchanged = seed['translation'] == old.get('translation', '')
        cases.append(dict(id=seed['id'], selected=selected, reason=reason,
            control_folder=folder, control_report_sha256=digest(path),
            control_source=old['source'], control_translation=old.get('translation', ''),
            candidate_source=near['source'] if selected else old['source'],
            candidate_bounds=near['original_bounds'] if selected else old['bounds'],
            original_sample_judgment_reused=unchanged,
            control_judgment=judgments[seed['id']]['after'] if unchanged else None,
            needs_visual_review=selected or not unchanged))
    result = dict(policy_sha256=digest(ROOT/'tools/paragraph_recovery.py'),
        sample_sha256=digest(QA/'corpus-review-sample/sample.json'),
        production_application_modified=False, reference_translations_used_for_selection=False,
        independent_readers=independent,
        detector_ensemble=ensemble,
        independent_reader_provenance_sha256=digest(OUT/'independent-readers-provenance.json') if independent else None,
        cases=cases)
    atomic(output, json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--independent', action='store_true')
    parser.add_argument('--detector-ensemble', action='store_true')
    args = parser.parse_args()
    selection = build(args.independent or args.detector_ensemble, args.detector_ensemble)
    process = None
    results = []
    try:
        for case in selection['cases']:
            result = dict(case)
            if case['selected']:
                if process is None:
                    process = subprocess.Popen([str(ROOT/'build/local-model/Release/luma_translate.exe'),
                        str(ROOT/'assets/models/opus-en-es')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
                process.stdin.write(json.dumps(dict(source=case['candidate_source']))+'\n')
                process.stdin.flush()
                line = process.stdout.readline()
                assert line, 'No translation output'
                value = json.loads(line)
                assert 'error' not in value, value
                result['candidate_inference'] = value
                result['candidate_translation'] = value['translation']
                result['candidate_meaning_judgment'] = None
            else:
                result['candidate_translation'] = case.get('control_translation')
                result['candidate_meaning_judgment'] = case.get('control_judgment')
            results.append(result)
    finally:
        if process is not None:
            process.stdin.close()
            process.wait(timeout=30)
    report = dict(**{k:v for k,v in selection.items() if k!='cases'}, cases=results,
        selected_regions=sum(r['selected'] for r in results),
        control_cohorts=dict(collections.Counter(r['control_folder'] for r in results)),
        reasons=dict(collections.Counter(r['reason'] for r in results)),
        all_regions_visually_reviewed=False, semantic_accuracy=None)
    suffix = '-ensemble-cased' if args.detector_ensemble else '-independent' if args.independent else ''
    atomic(OUT/('selected-translations'+suffix+'.json'), json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['cases']}))


if __name__ == '__main__':
    main()
