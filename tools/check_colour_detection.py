"""Independent known-text colour/rotation fixtures through the shared C++ OCR."""
import argparse,json,pathlib,subprocess
from PIL import Image,ImageDraw,ImageFont
import numpy as np

ROOT=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--recognizer',type=pathlib.Path,default=ROOT/'assets/models/opus-en-es')
parser.add_argument('--detector',type=pathlib.Path,default=ROOT/'build/full-comics/candidate')
parser.add_argument('--output',type=pathlib.Path,default=ROOT/'build/full-comics/colour-fixtures')
args=parser.parse_args();QA=args.output;QA.mkdir(parents=True,exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',36)
tests=[]
for name,fg,bg,angle,outline in [('black','black','white',0,0),('red','#b91c1c','white',0,0),('blue','#1d4ed8','white',0,0),
    ('green','#16803d','white',0,0),('gold','#ffc62a','#182132',0,0),('white','white','#172232',0,0),
    ('slanted-red','#b91c1c','white',-14,0),('slanted-blue','#2558ff','white',18,0),('outlined','#fdbe40','#282045',-10,2)]:
    phrase='THE ANCIENT SWORD';layer=Image.new('RGBA',(460,100));draw=ImageDraw.Draw(layer)
    draw.text((15,20),phrase,font=font,fill=fg,stroke_width=outline,stroke_fill='black' if outline else fg)
    layer=layer.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
    canvas=Image.new('RGB',(700,360),bg);canvas.paste(layer,((700-layer.width)//2,(360-layer.height)//2),layer)
    path=QA/(name+'.png');canvas.save(path);raw=path.with_suffix('.bgra')
    rgba=np.asarray(canvas.convert('RGBA'));raw.write_bytes(rgba[:,:,[2,1,0,3]].tobytes())
    tests.append(dict(id=name,path=str(raw.resolve()),width=canvas.width,height=canvas.height,expected=phrase))
process=subprocess.Popen([str(ROOT/'build/local-model/Release/luma_ocr.exe'),str(args.recognizer.resolve()),str(args.detector.resolve())],
    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
results=[]
try:
    for test in tests:
        process.stdin.write(json.dumps(test)+'\n');process.stdin.flush();line=process.stdout.readline()
        if not line:raise RuntimeError(process.stderr.read())
        result=json.loads(line);result['recognized']=' '.join(r['text'] for r in result.get('lines',[]) if r['confidence']>=.85)
        result['passed']=test['expected'].casefold() in result['recognized'].casefold();results.append(result)
        print(test['id'],result['passed'],repr(result['recognized']),result.get('milliseconds'),flush=True)
finally:process.stdin.close();process.wait()
(QA/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
assert all(r['passed'] for r in results),'Some colour/rotation cases failed'
