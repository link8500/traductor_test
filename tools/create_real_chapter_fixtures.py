"""Read actual cached chapters on Android, without replacing their lettering."""
import html,json,pathlib,urllib.parse

ROOT=pathlib.Path(__file__).resolve().parents[1];QA=ROOT/'build/full-comics'
images=json.loads((QA/'images-en.json').read_text(encoding='utf-8'));proof=[]
for number in [1,31,124]:
    chapter=f'absolute-regression-{number:02d}-en'
    pages=[r for r in images if r['chapter']==chapter]
    rows=[json.loads(s) for s in (QA/'translated-en-final'/(chapter+'.jsonl')).read_text(encoding='utf-8').splitlines()]
    candidates=[r for r in rows if len(r['source'])>=70 and not any(w in r['source'].upper() for w in ['ASURA','DISCORD','PATREON','HTTPS','CHAPTER'])
        and r['bounds'][1]>300 and r['bounds'][3]<next(p['height'] for p in pages if p['image']==r['image'])-800]
    assert candidates,chapter
    selected=candidates[0];target=max(0,selected['bounds'][1]-300)
    parts=[]
    for page in pages:
        src=urllib.parse.quote(pathlib.Path(page['path']).relative_to(QA).as_posix())
        anchor=f'<span id="scene" style="position:absolute;top:{target*100/page["height"]:.5f}%;width:1px;height:1px"></span>' if page['image']==selected['image'] else ''
        if number==124 and page['image']==1:
            anchor+='<span id="swim" style="position:absolute;top:92%;width:1px;height:1px"></span>'
        if number==124 and page['image']==2:
            anchor+='<span id="underwater" style="position:absolute;top:0;width:1px;height:1px"></span>'
        parts.append(f'<article>{anchor}<img loading="lazy" src="{html.escape(src,quote=True)}" width="{page["width"]}" height="{page["height"]}" alt=""></article>')
    document='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Absolute Regression · '+str(number)+'</title><style>body{margin:0;padding:0 16px;background:white}article{position:relative;margin:0 auto;max-width:1000px}img{display:block;width:100%;height:auto}</style>'+''.join(parts)+'</html>'
    name=f'chapter-{number}.html';(QA/name).write_text(document,encoding='utf-8')
    page=next(p for p in pages if p['image']==selected['image'])
    proof.append(dict(chapter=chapter,fixture=name,anchor='scene',full_chapter_images=len(pages),image=selected['image'],
        source_url=page['url'],sha256=page['sha256'],original_width=page['width'],original_height=page['height'],anchor_y=target,
        baseline_detected_text=selected['source'],purpose='Live overlay viewport only; full chapter traversal is reported separately'))
(QA/'real-chapter-fixtures8008.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([dict(chapter=r['chapter'],images=r['full_chapter_images'],image=r['image'],y=r['anchor_y']) for r in proof]))
