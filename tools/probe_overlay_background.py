"""Run the native background policy on original, unmodified comic pixels."""
import json
import pathlib
import subprocess
from PIL import Image
from audit_corpus_quality import ROOT,QA,read,records,digest,atomic


def main():
    out=QA/'background8015';out.mkdir(exist_ok=True);sample=read(QA/'sentence-coverage8014/photo-layout/sample.json');inputs=[]
    for case in sample['cases']:
        image=Image.open(case['source_page']['path']).convert('RGB');left,top,right,bottom=case['bounds']
        box=(max(0,left-10),max(0,top-10),min(image.width,right+10),min(image.height,bottom+10));crop=image.crop(box).convert('RGBA')
        path=out/f'{case["id"]:03d}.bgra';path.write_bytes(crop.tobytes('raw','BGRA'))
        inputs.append(dict(id=case['id'],path=str(path.resolve()),width=crop.width,height=crop.height,
            bounds=[left-box[0],top-box[1],right-box[0],bottom-box[1]],old_corner_color=list(image.getpixel((max(0,left-2),max(0,top-2)))),
            original_pixels_sha256=case['source_page']['sha256'],cropped_pixels_sha256=digest(path)))
    manifest=out/'input.jsonl';target=out/'output.jsonl';atomic(manifest,''.join(json.dumps(r)+'\n' for r in inputs))
    binary=ROOT/'build/background8015/Release/luma_background_test.exe'
    result=subprocess.run([str(binary),str(manifest),str(target)],check=True,capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    actual=records(target);assert len(actual)==8
    changed=sum(row['confident'] and row['color']!=item['old_corner_color'] for item,row in zip(inputs,actual))
    # The pixels were visually inspected. All eight balloons have a white fill;
    # uncertain cases keep their original (already white) fallback.
    for item,row in zip(inputs,actual):assert (row['color'] if row['confident'] else item['old_corner_color'])==[255,255,255]
    summary=dict(cases=8,changed_backgrounds=changed,all_selected_balloon_fills_white=True,native_guards=json.loads(result.stdout)['guards'],
        binary_sha256=digest(binary),policy_sha256=digest(ROOT/'native/overlay_background.h'),input_sha256=digest(manifest),output_sha256=digest(target),
        translation_source_changed=False,ocr_source_changed=False,full_corpus_visual_accuracy=None)
    atomic(out/'summary.json',json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
