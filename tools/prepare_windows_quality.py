"""Lossless copies of the six selected chapters for the Windows native benchmark."""
import concurrent.futures,json,pathlib
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
chapters=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
records=[]
for chapter in chapters:
    for image in chapter['images']:
        target=root/'windows-images'/chapter['id']/f"{image['index']:03d}.png"
        records.append({'chapter':chapter['id'],'image':image['index'],'path':str(target),'source_path':str(root/image['path'])})
def convert(row):
    target=pathlib.Path(row['path']);target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with Image.open(row['source_path']) as image:image.convert('RGB').save(target,compress_level=1)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for i,_ in enumerate(pool.map(convert,records)):
        if i%20==0:print(i+1,'/',len(records),flush=True)
(root/'windows-input.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records),encoding='utf-8')
print('Windows input ready',len(records),flush=True)
