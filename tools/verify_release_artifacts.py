"""Check that distributed APKs/Windows data contain the pinned offline models."""
import argparse,hashlib,json,pathlib,zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apk',type=pathlib.Path,action='append',help='Check only these APKs; repeat for multiple files')
parser.add_argument('--windows',action='store_true',help='Also check Windows when selecting APKs')
args=parser.parse_args()

root=pathlib.Path(__file__).resolve().parents[1]
directory=root/'assets/models/opus-en-es'
manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
expected={'manifest.json':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest(),**manifest['files']}
for apk in args.apk or sorted((root/'build/app/outputs/flutter-apk').glob('*release.apk')):
    with zipfile.ZipFile(apk) as archive:
        for name,digest in expected.items():
            with archive.open('assets/flutter_assets/assets/models/opus-en-es/'+name) as source:
                hash_value=hashlib.sha256()
                for block in iter(lambda:source.read(1024*1024),b''):hash_value.update(block)
            assert hash_value.hexdigest()==digest,(apk.name,name)
        names=set(archive.namelist())
        abis={name.split('/')[1] for name in names if name.startswith('lib/')}
        assert abis,apk.name
        for abi in abis:
            for library in ['libflutter.so','libapp.so','libluma_local.so']:
                assert f'lib/{abi}/{library}' in names,(apk.name,abi,'Incomplete native architecture',library)
        for name in ['onnxruntime.MIT.txt','onnxruntime.ThirdPartyNotices.txt','json.MIT.txt']:
            assert archive.getinfo('assets/flutter_assets/assets/licenses/'+name).file_size>100
    print(apk.name,apk.stat().st_size,'bytes: pinned offline models verified')
if args.windows or not args.apk:
    windows=root/'build/windows/x64/runner/Release'
    assert (windows/'onnxruntime.dll').is_file()
    for name,digest in expected.items():
        assert hashlib.sha256((windows/'data/flutter_assets/assets/models/opus-en-es'/name).read_bytes()).hexdigest()==digest,('Windows',name)
    print('Windows: pinned offline models and native runtime verified')
