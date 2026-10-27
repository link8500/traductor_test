"""Export every comparison and its expandable technical details to one PDF."""
from html.parser import HTMLParser
from html import escape
from pathlib import Path
import hashlib
import json
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build/temporal8040/index.html'
OUT = ROOT / 'output/pdf/Luma-informe-completo-8040.pdf'


class Node:
    def __init__(self, tag='', attrs=None):
        self.tag, self.attrs, self.children = tag, dict(attrs or []), []

    def text(self):
        return ''.join(child.text() if isinstance(child, Node) else child for child in self.children)

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if not isinstance(child, Node):
                continue
            if (tag is None or child.tag == tag) and (cls is None or cls in child.attrs.get('class', '').split()):
                result.append(child)
            result.extend(child.find(tag, cls))
        return result


class Tree(HTMLParser):
    VOID = {'meta', 'input', 'br', 'hr', 'link', 'img'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, text):
        self.stack[-1].children.append(text)


def normalize(text):
    return text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-').replace('\u2192', ' -> ')


pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Italic', 'C:/Windows/Fonts/ariali.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial-Italic', boldItalic='Arial-Bold')
STYLES = {
    'title': ParagraphStyle('title', fontName='Arial-Bold', fontSize=27, leading=32, textColor=colors.HexColor('#193445'), spaceAfter=12),
    'h1': ParagraphStyle('h1', fontName='Arial-Bold', fontSize=18, leading=23, spaceAfter=12),
    'h2': ParagraphStyle('h2', fontName='Arial-Bold', fontSize=10, leading=14, spaceAfter=7, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Arial', fontSize=9.3, leading=13, spaceAfter=7, splitLongWords=True),
    'small': ParagraphStyle('small', fontName='Arial', fontSize=8.1, leading=11, textColor=colors.HexColor('#50616c'), spaceAfter=7),
    'source': ParagraphStyle('source', fontName='Arial', fontSize=9.1, leading=12.5, spaceAfter=7),
    'label': ParagraphStyle('label', fontName='Arial-Bold', fontSize=8, leading=11, textColor=colors.HexColor('#36556a'), spaceAfter=5),
    'json': ParagraphStyle('json', fontName='Consolas', fontSize=7.1, leading=9.4, splitLongWords=True, spaceAfter=12),
}


def p(text, style='body'):
    return Paragraph(escape(normalize(text)).replace('\n', '<br/>'), STYLES[style])


def footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor('#c7d3db'))
    canvas.line(17*mm, 17*mm, width-17*mm, 17*mm)
    canvas.setFont('Arial', 8)
    canvas.setFillColor(colors.HexColor('#596b76'))
    canvas.drawString(17*mm, 12*mm, 'Luma | Informe completo 8040 | Candidato experimental')
    canvas.drawRightString(width-17*mm, 12*mm, str(doc.page))
    canvas.restoreState()


def main():
    tree = Tree()
    tree.feed(SOURCE.read_text(encoding='utf-8'))
    root = tree.root
    sections = root.find('section')
    intro = root.find('div', 'intro')[0]
    articles = root.find('article')
    assert len(articles) == 283 and len(sections) == 2
    OUT.parent.mkdir(parents=True, exist_ok=True)
    assert not OUT.exists(), 'Preserve existing exports'
    story = [p('Luma', 'title'), p('Informe completo de evaluación', 'h1'), p('Ensayos 8037-8040 | Exportación del informe local', 'small')]
    # Preserve the full source introduction, with the table in source order.
    for node in intro.children:
        if not isinstance(node, Node):
            continue
        if node.tag == 'p':
            story.append(p(node.text()))
        elif node.tag == 'table':
            data = [[p(cell.text(), 'label' if index == 0 else 'body') for cell in row.children if isinstance(cell, Node) and cell.tag in {'th', 'td'}]
                    for index, row in enumerate(node.find('tr'))]
            table = Table(data, colWidths=[90*mm, 41*mm, 41*mm], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e8f0f5')), ('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#ced8df')), ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story += [table, Spacer(1,9)]
    story.append(p('Esta exportación contiene las 283 comparaciones y, en el anexo, todos los detalles técnicos que se despliegan en la página. La búsqueda y los filtros interactivos pertenecen a la versión HTML.', 'small'))
    story.append(PageBreak())
    index = []
    for section in sections:
        story.append(p(section.find('h2')[0].text(), 'h1'))
        for article in section.find('article'):
            head = article.find('header')[0]
            ident = head.find('b')[0].text().strip()
            status = head.find('span')[0].text().strip()
            source = article.find('p','source')[0].text()
            columns = article.find('div','columns')[0]
            cells = [child for child in columns.children if isinstance(child, Node) and child.tag == 'div']
            note = article.find('p','note')[0].text()
            raw = article.find('pre')[0].text()
            technical = json.loads(raw)
            marker = ('Cambio' if article.attrs['data-changed'] == 'true' else 'Sin cambio')
            body = [p(f'{ident} | {marker}', 'h2'), p(status, 'small'), p('INGLÉS ORIGINAL', 'label'), p(source,'source')]
            data = [[p(cell.find('h3')[0].text(),'label') for cell in cells], [p(cell.find('p')[0].text()) for cell in cells]]
            table = Table(data, colWidths=[86*mm, 86*mm], hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3f6')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#cdd9e0')),('LINEBEFORE',(1,0),(1,-1),.3,colors.HexColor('#cdd9e0')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            body += [table, Spacer(1,7), p(note,'small'), Spacer(1,9)]
            story.append(KeepTogether(body))
            index.append(dict(identifier=ident, source=source, native=cells[0].find('p')[0].text(), selected=cells[1].find('p')[0].text(), status=status, note=note, technical=technical))
        story.append(PageBreak())
    story += [p('Anexo: detalles técnicos completos','h1'), p('Se conservan las tres alternativas, las puntuaciones inversas, los vetos temporales y los perfiles morfológicos de cada comparación. Son datos de investigación; las puntuaciones no representan una probabilidad de acierto.', 'body')]
    for entry in index:
        story.append(p(entry['identifier'],'h2'))
        # Compact valid JSON preserves every detail without hundreds of lines
        # devoted only to indentation and braces from the HTML's pretty JSON.
        story.append(p(json.dumps(entry['technical'], ensure_ascii=False, separators=(', ', ': ')),'json'))
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=19*mm,leftMargin=19*mm,topMargin=18*mm,bottomMargin=23*mm,
                            title='Luma - Informe completo de evaluación 8040', author='Luma - evaluación local', pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    manifest = dict(source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    pdf=str(OUT), bytes=OUT.stat().st_size, comparisons=len(index), technical_records=len(index))
    (ROOT/'tmp/pdfs/export-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'tmp/pdfs/comparison-index.json').write_text(json.dumps(index,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=True))


if __name__ == '__main__':
    main()
