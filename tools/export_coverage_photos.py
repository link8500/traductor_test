"""Publish an isolated 8014 gallery, reusing only identical painter inputs.

Unchanged pictures retain their actual recorded render with hash provenance.
Changed pictures are replayed through the exact same frozen Windows renderer.
No reference/translated answer is substituted for a native model output.
"""
import argparse
import collections
import datetime
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
from PIL import Image
from audit_corpus_quality import ROOT, QA, read, records, digest, atomic
from export_chapter_photos import write_chapter, STYLE


def paint_inputs(rows):
    return [(r['bounds'],r['translation']) for r in rows if 'translation' in r and not r.get('retained_original',False) and 'error' not in r]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--watch',action='store_true')
    parser.add_argument('--html-only',action='store_true');args=parser.parse_args();assert not(args.watch and args.html_only)
    folder=QA/'chapter-photos8014-fixed-ocr';folder.mkdir(exist_ok=True)
    reports=QA/'translated-en8014-fixed-ocr';previous=QA/'chapter-photos'
    binary=QA/'frozen-windows8009/traductor.exe';renderer_sha=digest(binary)
    pages={lang:collections.defaultdict(list) for lang in ['en','es']}
    for lang in pages:
        for page in read(QA/f'images-{lang}.json'):
            if page['series']=='absolute-regression':pages[lang][page['chapter'].removesuffix('-'+lang)].append(page)
    def index():
        completed=[read(p) for p in folder.glob('absolute-regression-*/provenance.json')]
        completed.sort(key=lambda r:int(r['chapter'].rsplit('-',1)[1]))
        result=dict(chapters_exported=len(completed),chapters_expected=124,source_images_rendered=sum(r['images'] for r in completed),
            reused_identical_painter_input_images=sum(r['reused_identical_painter_input_images'] for r in completed),
            fresh_replay_images=sum(r['fresh_replay_images'] for r in completed),cohort=reports.name,all_words_visually_reviewed=False,semantic_accuracy=None,
            generated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        atomic(folder/'summary.json',json.dumps(result,indent=2))
        rows=''.join(f'<tr><td><a href="{r["chapter"]}.html">{int(r["chapter"].rsplit("-",1)[1])}</a></td><td>{r["images"]}</td><td>{r["regions"]}</td><td>Pendiente</td></tr>' for r in completed)
        atomic(folder/'index.html',f'<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="60"><title>Luma · Traducción 8014, imágenes completas</title><style>{STYLE}</style><main><h1>Traducción 8014 · imágenes completas</h1><p>{len(completed)} / 124 capítulos publicados · {result["source_images_rendered"]} imágenes completas.</p><p class="note">Salida nativa 8014 sobre el OCR guardado 8011. Esta galería mantiene separado el nuevo recorrido del OCR. Se conservan originales y traducciones sin corregir para la foto. Las imágenes sin cambios visuales reutilizan la imagen de revisión guardada con el mismo pintor y las mismas entradas; las modificadas se dibujan de nuevo con ese pintor de Windows. No son capturas del teléfono ni una aprobación de todas las palabras.</p><p><a href="../metrics/index.html">Resultados agregados</a> · <a href="../chapter-photos/index.html">Galería histórica conservada</a> · <a href="summary.json">Procedencia y alcance</a></p><table><tr><th>Capítulo</th><th>Imágenes completas</th><th>Regiones</th><th>Revisión completa</th></tr>{rows}</table></main></html>')
        return len(completed)
    while True:
        for number in range(1,125):
            chapter=f'absolute-regression-{number:02d}';report=reports/(chapter+'-en.jsonl');done=report.with_name(report.stem+'.done.json')
            if not done.exists():continue
            target=folder/chapter;target.mkdir(exist_ok=True);proof=target/'provenance.json';report_sha=digest(report)
            if proof.exists():
                value=read(proof);assert value['report_sha256']==report_sha and value['renderer_binary_sha256']==renderer_sha
                if args.html_only:
                    write_chapter(folder,chapter,pages['en'][chapter],records(report),reports.name,value,pages['es'][chapter])
                    html_path=folder/(chapter+'.html')
                    atomic(html_path,html_path.read_text(encoding='utf-8').replace('Reconocimiento 8014-fixed-ocr','Traducción 8014 sobre el OCR guardado 8011'))
                continue
            if args.html_only:continue
            assert shutil.disk_usage(folder).free>2*1024**3,'Insufficient temporary space for the next native replay'
            status=read(done);assert status['all_files_traversed'] and not status['runtime_errors']
            old=read(previous/chapter/'provenance.json')
            assert old['renderer_binary_sha256']==renderer_sha and old['report_directory']=='translated-en8011-context'
            old_report=QA/old['report_directory']/(chapter+'-en.jsonl');assert digest(old_report)==old['report_sha256']
            rows=records(report);old_rows=records(old_report);old_pages={p['image']:p for p in old['pages']}
            output=[];fresh=[];linked=0
            rendered=target/report_sha[:16];rendered.mkdir(exist_ok=True)
            for page in pages['en'][chapter]:
                assert old_pages[page['image']]['original_sha256']==page['sha256']
                current=[r for r in rows if r['image']==page['image']];before=[r for r in old_rows if r['image']==page['image']]
                destination=rendered/f'{page["image"]:03d}.jpg';same=paint_inputs(current)==paint_inputs(before)
                record=dict(image=page['image'],original_sha256=page['sha256'],file=destination.relative_to(target).as_posix(),
                    width=page['width'],height=page['height'],reused_identical_painter_inputs=same)
                if same:
                    original=previous/chapter/old_pages[page['image']]['file'];assert digest(original)==old_pages[page['image']]['output_sha256']
                    if destination.exists():assert digest(destination)==old_pages[page['image']]['output_sha256']
                    else:os.link(original,destination)
                    record.update(output_sha256=old_pages[page['image']]['output_sha256'],reused_output_path=str(original),
                        reused_provenance_sha256=digest(previous/chapter/'provenance.json'))
                    linked+=1
                else:fresh.append((page,destination,current,record))
                output.append(record)
            if fresh:
                with tempfile.TemporaryDirectory(prefix=chapter+'-',dir=folder) as temporary:
                    temporary=pathlib.Path(temporary);inputs=[]
                    assert temporary.resolve().is_relative_to(folder.resolve())
                    for page,destination,current,record in fresh:
                        assert digest(pathlib.Path(page['path']))==page['sha256']
                        png=temporary/f'{page["image"]:03d}.png'
                        with Image.open(page['path']) as image:image.convert('RGB').save(png,compress_level=1)
                        inputs.append(dict(path=str(png.resolve()),output=str(destination.resolve()),rows=current))
                    manifest=temporary/'input.jsonl';atomic(manifest,''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in inputs));summary=temporary/'result.json'
                    subprocess.run([str(binary), '--review-export',str(manifest.resolve()),str(summary.resolve())],check=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
                    result=read(summary);assert result['success'] and result['images']==len(fresh)
                    for page,destination,current,record in fresh:
                        with Image.open(destination) as image:assert image.size==(page['width'],page['height']);image.verify()
                        record['output_sha256']=digest(destination)
            value=dict(chapter=chapter,images=len(output),regions=len(rows),report_directory=reports.name,report_sha256=report_sha,
                recorded_inference_engine=status['engine'],renderer_binary_sha256=renderer_sha,reused_identical_painter_input_images=linked,
                fresh_replay_images=len(fresh),fresh_capture=False,fresh_ocr=False,all_words_visually_reviewed=False,meaning_approved=False,pages=output)
            atomic(proof,json.dumps(value,ensure_ascii=False,indent=2))
            write_chapter(folder,chapter,pages['en'][chapter],rows,reports.name,value,pages['es'][chapter])
            html_path=folder/(chapter+'.html')
            document=html_path.read_text(encoding='utf-8').replace('Reconocimiento 8014-fixed-ocr','Traducción 8014 sobre el OCR guardado 8011')
            atomic(html_path,document)
            print('Published images:',index(),'/ 124 chapters;',linked,'unchanged,',len(fresh),'replayed',flush=True)
        count=index()
        if not args.watch or count==124:break
        time.sleep(20)


if __name__=='__main__':main()
