"""Paint actual Windows OCR/NMT reports on their same saved pixel inputs."""
import json
import pathlib
import subprocess
from PIL import Image,ImageDraw,ImageFont
from audit_corpus_quality import QA,read,records,digest,atomic


def main():
    folder=QA/'windows8016-real-pixels';inputs=records(folder/'input.jsonl');proof=read(folder/'summary.json')
    for label,build in [('before','801501'),('after','801601')]:
        out=folder/label;out.mkdir(exist_ok=True);rows=records(folder/(label+'.jsonl'));items=[]
        for source in inputs:
            items.append(dict(path=source['path'],rows=[r for r in rows if r['image']==source['image']],output=str((out/f'{source["image"]:03d}.jpg').resolve())))
        manifest=out/'paint-input.jsonl';target=out/'paint-output.json';atomic(manifest,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in items))
        binary=QA/f'frozen-windows{build}/traductor.exe';assert digest(binary)==proof['binaries'][label]
        subprocess.run([str(binary),'--review-export',str(manifest),str(target)],creationflags=subprocess.CREATE_NO_WINDOW,check=True,timeout=180)
        assert read(target)['success'] and read(target)['images']==4
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',24)
    sheet=Image.new('RGB',(1640,3000),'#f1f4ed');draw=ImageDraw.Draw(sheet)
    for i in range(1,5):
        top=(i-1)*750;draw.text((12,top+10),f'Vista {i} · Windows anterior / recuperación aplicada · Mismos píxeles y OCR',font=font,fill='#243b2b')
        for x,label in [(12,'before'),(830,'after')]:
            with Image.open(folder/label/f'{i:03d}.jpg') as bitmap:
                crop=bitmap.convert('RGB');crop.thumbnail((790,690));sheet.paste(crop,(x+(790-crop.width)//2,top+52))
    sheet.save(folder/'comparison.jpg',quality=94)
    value=dict(actual_app_viewports=4,before_binary_sha256=proof['binaries']['before'],after_binary_sha256=proof['binaries']['after'],
        comparison_sha256=digest(folder/'comparison.jpg'),source_and_geometry_identical=True,
        from_saved_pixels_not_live_desktop_photos=True,layout_visually_reviewed=False,full_screen_semantic_review_complete=False)
    atomic(folder/'replay.json',json.dumps(value,indent=2));print(json.dumps(value),flush=True)


if __name__=='__main__':main()
