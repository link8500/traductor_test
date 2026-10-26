"""Bounded additional training-label queue, never automatic unsupervised labels."""
import json
import pathlib
import subprocess
import sys
from prepare_finetune8031 import ROOT,OUT,sha,save


def main():
    folder=OUT/'expansion-v1';folder.mkdir(exist_ok=True)
    jobs=[['prepare_finetune8031.py','expansion'],['prepare_finetune8031_pairs.py','ocr','--expansion'],
          ['prepare_finetune8031_pairs.py','align','--expansion'],['prepare_finetune8031_pairs.py','pairs','--expansion']]
    for args in jobs:
        result=subprocess.run([sys.executable,str(ROOT/'tools'/args[0]),*args[1:]],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        print(json.dumps(dict(stage=args,exit_code=result.returncode)),flush=True)
    selected=json.loads((folder/'review-selection.json').read_text(encoding='utf-8'))
    assert all(r['split']=='train' for r in selected)
    save(folder/'summary.json',dict(state='awaiting_bilingual_pixel_and_meaning_review',new_proposals=len(selected),
        selection_sha256=sha(folder/'review-selection.json'),automatic_training_started=False,approved_new_training_pairs=0,
        heldout_test_answers_reused_for_training=False,application_modified=False))
    print(json.dumps(dict(state='awaiting_review',training_proposals=len(selected))),flush=True)


if __name__=='__main__':main()
