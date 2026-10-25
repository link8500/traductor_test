"""Replay the real renderer on every saved full reading viewport.

This does not run live capture or approve OCR, meaning, or painting.
"""
import json
import subprocess
from audit_corpus_quality import QA, atomic, digest, read, records


def main():
    variants = {}
    for variant in ['baseline', 'consensus']:
        folder = QA / ('windows8020-full-viewports-' + variant)
        assert read(folder / 'summary.json')['reading_viewports_processed'] == 124
        variants[variant] = records(folder / 'output.jsonl')
    before, after = variants['baseline'], variants['consensus']
    assert len(before) == len(after) == 228
    changed = []
    for a, b in zip(before, after):
        assert (a['image'], a['bounds'], a['source']) == (b['image'], b['bounds'], b['before_consensus'])
        if a['source'] != b['source'] or a['translation'] != b['translation']:
            changed.append(dict(image=a['image'], bounds=a['bounds'], before_source=a['source'],
                                source=b['source'], before=a['translation'], after=b['translation']))
    out = QA / 'windows8020-full-viewports-review'
    out.mkdir(exist_ok=True)
    atomic(out / 'changes.json', json.dumps(dict(changes=changed, rows=228, viewports=124,
        original_blocks_and_bounds_preserved=True, output_meanings_reviewed=False), ensure_ascii=False, indent=2))
    for variant in ['baseline', 'consensus']:
        build = '801901' if variant == 'baseline' else '802001'
        binary = QA / f'frozen-windows{build}/traductor.exe'
        assert digest(binary) == read(QA / f'windows-engine{build}.json')['binary_sha256']
        paint = out / variant
        paint.mkdir(exist_ok=True)
        manifest = []
        for ident in range(1, 125):
            manifest.append(dict(path=str(QA / 'recovery-viewports801201' / f'{ident:03d}.png'),
                rows=[r for r in variants[variant] if r['image'] == ident],
                output=str(paint / f'{ident:03d}.jpg')))
        path = paint / 'input.jsonl'
        atomic(path, ''.join(json.dumps(row) + '\n' for row in manifest))
        result = paint / 'result.json'
        if not result.exists():
            subprocess.run([str(binary), '--review-export', str(path), str(result)],
                creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=900)
        assert read(result)['success'] and read(result)['images'] == 124
        atomic(paint / 'provenance.json', json.dumps(dict(binary_sha256=digest(binary),
            input_sha256=digest(path), native_output_sha256=digest(QA / ('windows8020-full-viewports-' + variant) / 'output.jsonl'),
            render_result_sha256=digest(result), layout_visually_reviewed=False,
            saved_pixels_not_live_desktop_capture=True), indent=2))
    print(json.dumps(dict(viewports=124, native_rows=228, changed_rows=len(changed),
        changed_viewports=len({r['image'] for r in changed}), layout_visually_reviewed=False)), flush=True)


if __name__ == '__main__':
    main()
