from pathlib import Path
import json
import re
import subprocess

import pdfplumber
from pypdf import PdfReader
from PIL import Image, ImageDraw

from export_luma_report import ROOT, OUT, normalize


def flat(text):
    return re.sub(r'\s+', '', normalize(text))


reader = PdfReader(OUT)
text = '\n'.join(page.extract_text() or '' for page in reader.pages)
index = json.loads((ROOT / 'tmp/pdfs/comparison-index.json').read_text(encoding='utf-8'))
body = flat(text)
missing = []
for entry in index:
    for field in ['identifier', 'source', 'native', 'selected', 'note']:
        if flat(entry[field]) not in body:
            missing.append(dict(identifier=entry['identifier'], field=field))
assert not missing, missing
assert len(index) == 283
assert '\ufffd' not in text and '\u25a0' not in text
appendix_start = next(i + 1 for i, page in enumerate(reader.pages) if 'Anexo: detalles t' in (page.extract_text() or ''))
assert text.count('inverse_scores') == 283 and text.count('temporal_vetoes') == 283
bad_bounds = []
with pdfplumber.open(OUT) as pdf:
    for page_no, page in enumerate(pdf.pages, 1):
        for char in page.chars:
            if char['text'].strip() and (char['x0'] < 30 or char['x1'] > page.width - 30 or char['top'] < 20 or char['bottom'] > page.height - 20):
                bad_bounds.append(dict(page=page_no, char=char['text'], x=char['x0'], y=char['top']))
assert not bad_bounds, bad_bounds[:10]
render = ROOT / 'tmp/pdfs/luma8040-render'
render.mkdir(exist_ok=True)
poppler = Path('C:/Users/MSI THIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe')
subprocess.run([str(poppler), '-r', '45', '-png', str(OUT), str(render/'page')], check=True, capture_output=True)
paths = sorted(render.glob('page-*.png'))
assert len(paths) == len(reader.pages)
for start in range(0, len(paths), 24):
    rows, cols, width, height = 6, 4, 214, 322
    sheet = Image.new('RGB', (cols*width, rows*height), '#dbe3e8')
    draw = ImageDraw.Draw(sheet)
    for offset, path in enumerate(paths[start:start+24]):
        picture = Image.open(path).convert('RGB')
        picture.thumbnail((202, 288))
        x, y = (offset%cols)*width+6, (offset//cols)*height+23
        sheet.paste(picture,(x,y))
        draw.text((x,y-17), str(start+offset+1), fill='black')
    sheet.save(render/f'contact-{start//24+1}.png')
for page in sorted(set([1,2,appendix_start-1,appendix_start,len(reader.pages)])):
    subprocess.run([str(poppler),'-f',str(page),'-l',str(page),'-r','110','-singlefile','-png',str(OUT),str(render/f'detail-{page}')],check=True,capture_output=True)
verification = dict(pages=len(reader.pages), comparisons_verified=283, technical_records_verified=283,
                    all_source_native_selected_notes_found=True, missing_glyphs=False,
                    characters_outside_safe_page_bounds=0, appendix_first_page=appendix_start,
                    rendered_pages=len(paths), pdf_bytes=OUT.stat().st_size)
(ROOT/'tmp/pdfs/pdf-verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
print(json.dumps(verification))
