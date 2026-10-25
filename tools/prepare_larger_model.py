"""Pinned ONNX conversion for a local quality comparison, kept outside app assets."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, pathlib, shutil, requests
from prepare_comic_quality import download

ROOT=pathlib.Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'build/comic-quality/tc-big'
REVISION='1ccec650fb90f50f3462bf106bf5015064024f5d'
BASE=f'https://huggingface.co/VaishalBusiness/opus/resolve/{REVISION}/Helsinki-NLP-opus-mt-tc-big-en-es/'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',action='store_true');args=parser.parse_args()
    files={'encoder.float.onnx':'encoder_model.onnx','decoder.float.onnx':'decoder_model_merged.onnx',
           'config.json':'config.json','source.spm':'source.spm','vocab.json':'vocab.json'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(download,BASE+remote,DIRECTORY/local):local for local,remote in files.items()}
        for job in concurrent.futures.as_completed(jobs): job.result();print(jobs[job],'downloaded',flush=True)
    from onnxruntime.quantization import quantize_dynamic, QuantType
    for part in ['encoder','decoder']:
        if not (DIRECTORY/f'{part}.onnx').exists() or (DIRECTORY/f'{part}.onnx').stat().st_size>400_000_000:
            print('quantizing',part,flush=True)
            quantize_dynamic(str(DIRECTORY/f'{part}.float.onnx'),str(DIRECTORY/f'{part}.onnx'),weight_type=QuantType.QInt8,
                             extra_options={'EnableSubgraph':True})
    import sentencepiece as sp
    processor=sp.SentencePieceProcessor(model_file=str(DIRECTORY/'source.spm'))
    vocab=json.loads((DIRECTORY/'vocab.json').read_text(encoding='utf-8'));config=json.loads((DIRECTORY/'config.json').read_text())
    tokens=['']*len(vocab)
    for token,index in vocab.items():tokens[index]=token
    # Segmentation uses the entire source vocabulary even when a source piece
    # is absent from Marian's joint lookup. Those pieces map to <unk> only
    # after the Viterbi path is chosen, as in the upstream tokenizer.
    pieces=[[processor.id_to_piece(i),processor.get_score(i),vocab.get(processor.id_to_piece(i),vocab['<unk>'])] for i in range(processor.get_piece_size())
            if not processor.is_control(i) and not processor.is_unknown(i)]
    tokenizer={'pieces':pieces,'tokens':tokens,'unk':vocab['<unk>'],'eos':vocab['</s>'],'pad':vocab['<pad>'],
               'heads':config['decoder_attention_heads'],'head_size':config['d_model']//config['decoder_attention_heads']}
    (DIRECTORY/'tokenizer.json').write_text(json.dumps(tokenizer,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (DIRECTORY/'terminology.json').write_bytes((ROOT/'assets/models/opus-en-es/terminology.json').read_bytes())
    lock={'upstream':'Helsinki-NLP/opus-mt-tc-big-en-es','conversion':'VaishalBusiness/opus','revision':REVISION,
          'license':'CC-BY-4.0','files':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in DIRECTORY.iterdir() if path.suffix!='.part' and path.name!='manifest.json'}}
    (DIRECTORY/'manifest.json').write_text(json.dumps(lock,indent=2),encoding='utf-8')
    print('larger model ready',flush=True)
    if args.bundle:
        import runpy
        runpy.run_path(str(ROOT/'tools/compare_int4_model.py'))
        selected=ROOT/'build/comic-quality/tc-big-int4'
        destination=ROOT/'assets/models/opus-en-es'
        license_url='https://creativecommons.org/licenses/by/4.0/legalcode.txt'
        download(license_url,DIRECTORY/'LICENSE.CC-BY-4.0.txt')
        previous=json.loads((destination/'manifest.json').read_text(encoding='utf-8')) if (destination/'manifest.json').exists() else {}
        upstream=previous.get('upstream_revision') if previous.get('revision')==REVISION else None
        if not upstream:upstream=requests.get('https://huggingface.co/api/models/Helsinki-NLP/opus-mt-tc-big-en-es',timeout=30).json()['sha']
        download(f'https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-es/resolve/{upstream}/README.md',DIRECTORY/'README.upstream.md')
        runtime=['encoder.onnx','decoder.onnx','tokenizer.json','terminology.json','LICENSE.CC-BY-4.0.txt','README.upstream.md']
        for name in runtime+['source.spm','vocab.json','config.json']:
            origin=selected/name if name in ['encoder.onnx','decoder.onnx'] else DIRECTORY/name
            shutil.copyfile(origin,destination/name)
        from prepare_ocr_model import prepare
        ocr=prepare(destination)
        from prepare_text_detector import prepare as prepare_detector
        detector=prepare_detector(destination)
        runtime+=['english-ocr.onnx','ocr-characters.json','english-ocr-fallback.onnx','ocr-characters-fallback.json','LICENSE.OCR.Apache-2.0.txt','text-detector.onnx']
        lock={'upstream':'Helsinki-NLP/opus-mt-tc-big-en-es','upstream_revision':upstream,'conversion':'VaishalBusiness/opus',
              'revision':REVISION,'license':'CC-BY-4.0','quantization':'ONNX Runtime 1.23.2 RTN Int4, block_size=32, accuracy_level=4, MatMul/Gather; constant output projection transpose folded',
              'compatibility':'Int4 scale initializers are local to decoder If branches so ORT 1.23.2 ARM64 prepacking can resolve them; values and graph operators unchanged.',
              'ocr':ocr,'text_detector':detector,'files':{name:hashlib.sha256((destination/name).read_bytes()).hexdigest() for name in runtime}}
        (destination/'manifest.json').write_text(json.dumps(lock,indent=2),encoding='utf-8')
        print('bundled EN-ES quality model',flush=True)

if __name__=='__main__':main()
