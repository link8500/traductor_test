"""Verify packaged model files; --refresh records an intentional asset update."""
import argparse,hashlib,json,pathlib
parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
directory=pathlib.Path(__file__).resolve().parents[1]/'assets/models/opus-en-es'
manifest=directory/'manifest.json';data=json.loads(manifest.read_text(encoding='utf-8'))
for name,expected in data['files'].items():
    actual=hashlib.sha256((directory/name).read_bytes()).hexdigest()
    if args.refresh:data['files'][name]=actual
    elif actual!=expected:raise SystemExit(f'Model asset checksum mismatch: {name}')
if args.refresh:manifest.write_text(json.dumps(data,indent=2),encoding='utf-8')
print('Model checksums OK:',len(data['files']),'files')
