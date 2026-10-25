"""Copy a complete Windows release and pin the engine used by corpus tests."""
import argparse,hashlib,json,os,pathlib,re,shutil,stat

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCES=['native/local_translation.cpp','native/local_translation.h','native/ocr_recovery.h','native/translation_coverage.h','native/overlay_background.h','native/ocr_consensus_candidate.h','native/ocr_coverage_candidate.h','native/ocr_full_consensus_candidate.h','windows/runner/screen_translator.cpp','windows/runner/screen_translator.h','windows/runner/review_export.cpp','assets/models/opus-en-es/manifest.json']
SOURCES.append('native/short_dialogue_candidate.h')
SOURCES.append('native/ocr_morph_consensus_candidate.h')
SOURCES.extend(['native/translation_punctuation.h','windows/runner/main.cpp'])
SOURCES.append('native/translation_opening.h')
SOURCES.extend(['native/translation_question_clause.h','native/ocr_morph_edit_candidate.h'])
SOURCES.extend(['native/translation_tail.h','native/translation_tail_candidate.h'])
SOURCES.extend(['windows/CMakeLists.txt','assets/windows-ocr-readers/manifest.json'])

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def snapshot_copy(source,destination):
    """Reuse immutable content; never hard-link the mutable build output."""
    source=pathlib.Path(source);destination=pathlib.Path(destination)
    if source.stat().st_size<1024*1024:return shutil.copy2(source,destination)
    qa=(ROOT/'build/full-comics').resolve();pool=qa/'immutable-file-content'
    assert destination.resolve().is_relative_to(qa) and source.resolve().is_relative_to((ROOT/'build/windows/x64/runner/Release').resolve())
    pool.mkdir(exist_ok=True);sha=digest(source);stored=pool/sha
    if not stored.exists():
        shutil.copy2(source,stored)
        assert digest(stored)==sha
        os.chmod(stored,stat.S_IREAD)
    else:assert digest(stored)==sha
    os.link(stored,destination)
    return str(destination)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'[0-9]+',args.build):parser.error('Build must be numeric')
    qa=ROOT/'build/full-comics';source=ROOT/'build/windows/x64/runner/Release'
    destination=qa/('frozen-windows'+args.build);snapshot=qa/('windows-engine'+args.build+'.json')
    assert not destination.exists() and not snapshot.exists(),'Never overwrite an existing engine snapshot'
    models=source/'data/flutter_assets/assets/models/opus-en-es'
    manifest=json.loads((models/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():assert digest(models/name)==expected,('Unverified release asset',name)
    readers=source/'ocr-readers';reader_manifest=json.loads((readers/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in reader_manifest['files'].items():assert digest(readers/name)==expected,('Unverified Windows reader',name)
    # Reserve space before starting a snapshot; identical large assets will
    # share the immutable pool instead of being copied into each release.
    pool=qa/'immutable-file-content'
    additional=sum(p.stat().st_size for p in source.rglob('*') if p.is_file()
        and (p.stat().st_size<1024*1024 or not (pool/digest(p)).exists()))
    assert shutil.disk_usage(qa).free>additional+4*1024**3, 'Snapshot postponed: preserve 4 GiB of free disk space'
    shutil.copytree(source,destination,copy_function=snapshot_copy)
    proof={'engine':hashlib.sha256(b''.join((ROOT/p).read_bytes() for p in SOURCES)).hexdigest(),
        'binary_sha256':digest(destination/'traductor.exe'),
        'manifest_sha256':digest(destination/'data/flutter_assets/assets/models/opus-en-es/manifest.json'),
        'source_sha256':{p:digest(ROOT/p) for p in SOURCES}}
    proof['windows_reader_manifest_sha256']=digest(destination/'ocr-readers/manifest.json')
    for name,expected in reader_manifest['files'].items():assert digest(destination/'ocr-readers'/name)==expected
    for name,expected in manifest['files'].items():assert digest(destination/'data/flutter_assets/assets/models/opus-en-es'/name)==expected,('Copied release asset changed',name)
    snapshot.write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps({'snapshot':str(snapshot),'binary':str(destination/'traductor.exe'),'engine':proof['engine']}))

if __name__=='__main__':main()
