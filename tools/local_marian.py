"""Reference CPU inference for the exact ONNX files shipped with Luma."""
from __future__ import annotations
import json, pathlib, re, time, unicodedata
import numpy as np
import onnxruntime as ort
import sentencepiece as sp

ROOT=pathlib.Path(__file__).resolve().parents[1]
MODEL=ROOT/'assets/models/opus-en-es'

class LocalMarian:
    def __init__(self):
        self.vocab=json.loads((MODEL/'vocab.json').read_text(encoding='utf-8'))
        self.tokens={v:k for k,v in self.vocab.items()}
        self.spm=sp.SentencePieceProcessor(model_file=str(MODEL/'source.spm'))
        options=ort.SessionOptions(); options.intra_op_num_threads=2
        self.encoder=ort.InferenceSession(str(MODEL/'encoder.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.decoder=ort.InferenceSession(str(MODEL/'decoder.onnx'),sess_options=options,providers=['CPUExecutionProvider'])

    def encode(self,text):
        return [self.vocab.get(x,1) for x in self.spm.encode(text,out_type=str)]+[0]

    def translate(self,text,max_tokens=384):
        ids=self.encode(text)
        if len(ids)>500: raise ValueError('Paragraph exceeds the local model context; split at sentence boundaries.')
        attention=np.ones((1,len(ids)),dtype=np.int64)
        hidden=self.encoder.run(None,{'input_ids':np.array([ids],dtype=np.int64),'attention_mask':attention})[0]
        feeds={'encoder_hidden_states':hidden,'encoder_attention_mask':attention,'input_ids':np.array([[65000]],dtype=np.int64),'use_cache_branch':np.array([False])}
        for layer in range(6):
            for scope in ['decoder','encoder']:
                for kind in ['key','value']: feeds[f'past_key_values.{layer}.{scope}.{kind}']=np.zeros((1,8,0,64),dtype=np.float32)
        output=[]
        for step in range(max_tokens):
            values=self.decoder.run(None,feeds)
            logits=values[0][0,-1].copy();logits[65000]=-np.inf
            token=int(logits.argmax())
            if token==0: break
            output.append(token)
            feeds['input_ids']=np.array([[token]],dtype=np.int64);feeds['use_cache_branch']=np.array([True])
            for name,value in zip([x.name for x in self.decoder.get_outputs()][1:],values[1:]):
                if '.decoder.' in name or step==0: feeds[name.replace('present.','past_key_values.')]=value
        else: raise RuntimeError('Decoder did not finish; result intentionally rejected.')
        result=''.join(self.tokens.get(x,'') for x in output).replace('▁',' ').strip()
        result=re.sub(r'\s+([,.!?;:])',r'\1',result)
        return result

if __name__=='__main__':
    import sys
    engine=LocalMarian()
    samples=["Subconsciously, I thought my life wasn't that precious, because I'm a regressor.",
             "SUBCONSCIOUSLY, I THOUGHT MY LIFE WASN'T THAT PRECIOUS, BECAUSE I'M A REGRESSOR.",
             "I have reached the Qi Refining stage.","Seo Eun-hyun is a cultivator.","I must survive at the academy.",
             "I didn't know what he meant. Now I finally understand."]
    report=[]
    for text in samples:
        started=time.monotonic(); translated=engine.translate(text)
        item={'source':text,'translation':translated,'seconds':round(time.monotonic()-started,3),'tokens':engine.encode(text)}
        report.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
    (ROOT/'build/comic-quality/local-model-samples.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
