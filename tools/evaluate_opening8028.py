"""Freeze and test short dialogue openings across all complete control chapters.

The actual packaged app receives source text only. References and judgments
never enter inference. This experiment does not modify production behavior.
"""
import json
import pathlib
import re
import shutil
import subprocess

from audit_corpus_quality import ROOT, QA, atomic, digest, read, records
from quality_resources import wait_for_inference_memory


def main():
    folder = QA / 'opening8028'; folder.mkdir(exist_ok=True)
    sample = folder / 'sample.json'
    if not sample.exists():
        pattern = re.compile(r"^([A-Z][A-Za-z']+[!?])\s+(.{15,})$")
        cases = []; reports = {}
        paths = sorted((QA / 'translated-en8017-geometry').glob('*.done.json'))
        assert len(paths) == 124
        for done in paths:
            status = read(done)
            assert status['all_files_traversed'] and not status['runtime_errors']
            path = done.with_name(done.name.replace('.done.json', '.jsonl'))
            reports[path.name] = digest(path)
            for index, row in enumerate(records(path)):
                match = pattern.fullmatch(row.get('source', '').strip())
                if not match: continue
                cases.append(dict(id=len(cases)+1, report=path.name, report_row=index,
                                  source=row['source'], historical_translation=row['translation'],
                                  opening=match[1], rest=match[2], image=row['image'], bounds=row['bounds']))
        atomic(sample, json.dumps(dict(chapters_scanned=124, cases=cases, reports=reports,
                                      selection='Every source matching one initial word followed by ! or ? and a visible remainder',
                                      all_chapter_words_visually_reviewed=False), ensure_ascii=False, indent=2))
    frozen = read(sample)
    for name, expected in frozen['reports'].items():
        assert digest(QA / 'translated-en8017-geometry' / name) == expected
    inputs = []; ids = {}
    for case in frozen['cases']:
        for kind in ['source', 'opening', 'rest']:
            text = case[kind]
            if text not in ids:
                ids[text] = len(inputs) + 1
                inputs.append(dict(id=ids[text], image=0, bounds=[0, 0, 1, 1], source=text))
    manifest = folder / 'input.jsonl'; output = folder / 'native-output.jsonl'
    expected_input = ''.join(json.dumps(r) + '\n' for r in inputs)
    if manifest.exists(): assert manifest.read_text(encoding='utf-8') == expected_input
    else: atomic(manifest, expected_input)
    binary = QA / 'frozen-windows802701/traductor.exe'
    snapshot = QA / 'windows-engine802701.json'
    assert digest(binary) == read(snapshot)['binary_sha256']
    proof = dict(binary_sha256=digest(binary), snapshot_sha256=digest(snapshot), sample_sha256=digest(sample),
                 input_sha256=digest(manifest), manual_or_reference_answers_supplied=False,
                 new_translation_model_inference=True, new_ocr_inference=False, fresh_capture=False,
                 production_modified=False, model_weights_changed=False)
    provenance = folder / 'provenance.json'
    if provenance.exists(): assert read(provenance) == proof
    else: atomic(provenance, json.dumps(proof, indent=2))
    if not pathlib.Path(str(output) + '.summary.json').exists():
        assert shutil.disk_usage(folder).free >= 4 * 1024**3
        wait_for_inference_memory(minimum_free_bytes=5 * 1024**3 // 2)
        with (folder / 'runtime.log').open('ab') as log:
            subprocess.run([str(binary), '--translation-replay', str(manifest), str(output)], check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, stdout=log, stderr=log, timeout=1800)
    actual = records(output); assert len(actual) == len(inputs) and all('error' not in r for r in actual)
    assert read(pathlib.Path(str(output) + '.summary.json'))['runtime_errors'] == 0
    translations = {r['source']: r for r in actual}
    evaluated = [dict(case, native={kind:translations[case[kind]] for kind in ['source','opening','rest']},
                      meaning_reviewed=False) for case in frozen['cases']]
    atomic(folder / 'evaluated.json', json.dumps(evaluated, ensure_ascii=False, indent=2))
    summary = dict(chapters_scanned=124, candidates=len(evaluated), actual_native_model_inferences=len(actual),
                   runtime_errors=0, production_modified=False, sample_sha256=digest(sample),
                   output_sha256=digest(output), provenance_sha256=digest(provenance),
                   all_chapter_words_visually_reviewed=False, screen_attempt_failure_probability=None, target_achieved=False)
    atomic(folder / 'summary.json', json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__': main()
