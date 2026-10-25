"""Local 390 px review of actual OCR/model output. No remote translation."""
import json,pathlib
from PIL import Image
root=pathlib.Path(__file__).resolve().parents[1]/'build/comic-quality'
destination=root/'preview';destination.mkdir(exist_ok=True)
chapters=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
report=root/'android-full.jsonl'
if not report.exists():report=root/'translated-regions.jsonl'
rows=[json.loads(line) for line in report.read_text(encoding='utf-8').splitlines()]
scenes=[]
for chapter in chapters:
    candidates=[row for row in rows if row['chapter']==chapter['id'] and row['image']>0 and len(row['source'])>60]
    if chapter['id']=='cultivation-35':candidates=[row for row in candidates if 'REGRESSOR' in row['source'].upper()] or candidates
    focus=max(candidates,key=lambda r:(r['bounds'][2]-r['bounds'][0])*(r['bounds'][3]-r['bounds'][1])/len(r['source']));entry=chapter['images'][focus['image']]
    with Image.open(root/entry['path']) as original:
        top=max(0,min(focus['bounds'][1]-200,original.height-2000));bottom=min(original.height,top+2000)
        original.convert('RGB').crop((0,top,original.width,bottom)).save(destination/(chapter['id']+'.png'))
    regions=[]
    seen=[]
    for row in sorted(rows,key=lambda r:(r['bounds'][2]-r['bounds'][0])*(r['bounds'][3]-r['bounds'][1]),reverse=True):
        if row['chapter']!=chapter['id'] or row['image']!=focus['image']:continue
        left,y,right,end=row['bounds']
        if y<top or end>bottom:continue
        if any(abs(y-prior)<35 for prior in seen):continue
        seen.append(y)
        regions.append({**row,'bounds':[left,y-top,right,end-top]})
    regions.sort(key=lambda r:r['bounds'][1])
    scenes.append({'chapter':chapter['id'],'url':chapter['url'],'image':chapter['id']+'.png','regions':regions})
(destination/'data.json').write_text(json.dumps(scenes,ensure_ascii=False),encoding='utf-8')
(destination/'index.html').write_text('''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luma · revisión de cómics</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f5ee;color:#23312a;font:15px system-ui}main{max-width:900px;margin:30px auto;padding:20px}
h1{font-size:22px;margin-bottom:6px}p{color:#59675e;line-height:1.5;font-size:12px}header{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:14px 0}
select,button{font:inherit;border:1px solid #cdd4c7;border-radius:10px;padding:11px;background:white;color:#23312a}button{background:#d6eea8;cursor:pointer}
.stage{margin:auto;width:390px;max-width:100%;border:8px solid #23312a;border-radius:20px;overflow:hidden;background:white;box-shadow:0 15px 35px #23312a25}canvas{display:block;width:100%;height:auto}
.bar{padding:10px;color:#d6eea8;background:#23312a;font-size:12px;display:flex;justify-content:space-between}.label{font-size:12px;color:#59675e}details{margin-top:25px}li{margin:12px 0;line-height:1.5}a{color:#315f40}
</style><main><h1>Luma · revisión de cómics</h1><p>Vista a tamaño móvil con resultados del motor local. Esta página permite revisar posición y legibilidad; el dibujo nativo se prueba por separado en cada sistema.</p>
<header><select id="chapter" aria-label="Capítulo"></select><button id="toggle" aria-label="Mostrar el original">Ver original</button><label class="label">Ancho <input id="width" type="range" min="280" max="560" value="390"> <output id="pixels">390 px</output></label></header>
<div class="stage" id="stage"><div class="bar"><strong>⠿ Luma</strong><span id="mode">Traducción calculada · EN → ES</span></div><canvas id="canvas"></canvas></div>
<p class="label">Las imágenes y resultados están guardados localmente para esta prueba. <a id="source" target="_blank" rel="noreferrer">Abrir el capítulo de origen</a></p><details><summary>Revisar texto reconocido y traducción</summary><ol id="regions"></ol></details></main>
<script>
const $=id=>document.getElementById(id),canvas=$('canvas'),ctx=canvas.getContext('2d');let scenes=[],scene,image,translated=true;
function wrap(text,size,width){ctx.font=`500 ${size}px Arial`;const words=text.split(/\\s+/),lines=[];let line='';for(const word of words){const next=line?line+' '+word:word;if(line&&ctx.measureText(next).width>width){lines.push(line);line=word}else line=next}if(line)lines.push(line);return lines}
function render(){if(!image)return;canvas.width=image.width;canvas.height=image.height;ctx.drawImage(image,0,0);if(!translated)return;
for(const r of scene.regions){if(!r.translation||r.translation.toLowerCase()===r.source.toLowerCase())continue;let [x,y,end,bottom]=r.bounds,w=end-x,h=bottom-y;
const samples=[[x-5,y-5],[end+5,y-5],[x-5,bottom+5],[end+5,bottom+5]].map(([a,b])=>ctx.getImageData(Math.max(0,Math.min(image.width-1,a)),Math.max(0,Math.min(image.height-1,b)),1,1).data);
const rgb=[0,1,2].map(c=>samples.map(s=>s[c]).sort((a,b)=>a-b)[2]);let text=r.source===r.source.toUpperCase()?r.translation.toUpperCase():r.translation;
const ax=Math.max(0,x-16),ay=Math.max(0,y-16),aw=Math.min(image.width-ax,w+32),ah=Math.min(image.height-ay,h+32),patch=ctx.getImageData(ax,ay,aw,ah),lo=[255,255,255],hi=[0,0,0];
for(let i=0;i<patch.data.length;i+=4)for(let c=0;c<3;c++){lo[c]=Math.min(lo[c],patch.data[i+c]);hi[c]=Math.max(hi[c],patch.data[i+c])}
const lower=hi.map(v=>v*.2),upper=lo.map(v=>204+v*.2),background=rgb.map((v,c)=>Math.max(lower[c],Math.min(upper[c],v)));
for(let row=0;row<ah;row++)for(let col=0;col<aw;col++){const d=Math.max(x-3-ax-col,ax+col-end-3,y-2-ay-row,ay+row-bottom-2,0),s=Math.max(0,1-d/12),i=(row*aw+col)*4;for(let c=0;c<3;c++)patch.data[i+c]=Math.round(patch.data[i+c]*(1-s)+background[c]*s)}ctx.putImageData(patch,ax,ay);
let low=9,high=h,lines=[];for(let i=0;i<11;i++){const size=(low+high)/2;lines=wrap(text,size,w);if(lines.length*size*1.1<=h)low=size;else high=size}lines=wrap(text,low,w);
ctx.save();ctx.beginPath();ctx.rect(x-3,y-2,w+6,h+4);ctx.clip();const ink=(rgb[0]+rgb[1]+rgb[2]>420)?Math.max(...lower):Math.min(...upper);ctx.fillStyle=`rgb(${ink},${ink},${ink})`;ctx.textBaseline='top';ctx.textAlign=r.centered?'center':'left';let top=y+(h-lines.length*low*1.1)/2;for(const line of lines){ctx.fillText(line,r.centered?x+w/2:x,top);top+=low*1.1}ctx.restore()}}
function select(){scene=scenes[+$('chapter').value];image=new Image;image.onload=render;image.src=scene.image;$('source').href=scene.url;$('regions').replaceChildren();for(const r of scene.regions){const li=document.createElement('li');li.textContent=r.source+' → '+(r.translation||r.error||'Original conservado');$('regions').append(li)}}
$('chapter').onchange=select;$('toggle').onclick=()=>{translated=!translated;$('toggle').textContent=translated?'Ver original':'Ver traducción';$('mode').textContent=translated?'Traducción calculada · EN → ES':'Texto original';render()};$('width').oninput=()=>{$('stage').style.width=$('width').value+'px';$('pixels').textContent=$('width').value+' px'};
new ResizeObserver(()=>{$('pixels').textContent=Math.round($('stage').getBoundingClientRect().width)+' px'}).observe($('stage'));
fetch('data.json').then(r=>r.json()).then(data=>{scenes=data;data.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s.chapter;$('chapter').append(o)});select()});
</script></html>''',encoding='utf-8')
print(destination/'index.html')
(destination/'fixture.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma screen test</title>
<style>body{margin:0;background:#ece9df;color:#111;font:24px Arial}article{min-height:180vh;padding:100px 20px 0}p{background:white;border:2px solid #333;border-radius:48%;padding:50px 24px;text-align:center;line-height:1.35;font-weight:bold;margin:80px 0 200px}footer{height:100vh;background:#d4e5cd}</style>
<article><p>AFTER FOUR DAYS IN THE FOREST,<br>WE FINALLY REACHED THE CAMP.</p><p>KEEP YOUR SWORD READY.<br>THE NEXT BATTLE WILL BEGIN SOON.</p></article><footer></footer></html>''',encoding='utf-8')
(destination/'comic-fixture.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Luma comic fixture</title><style>body{margin:0;background:white}img{display:block;width:100%;height:auto}footer{height:100vh;background:#e6e9e2}</style><img src="cultivation-35.png" alt=""><footer></footer></html>''',encoding='utf-8')
