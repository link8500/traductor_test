"""Prepare the pinned Latin line reader used by the complete model bundler."""
import pathlib
from prepare_comic_quality import download
from prepare_latin_ocr import prepare as prepare_latin
def prepare(directory):
    metadata=prepare_latin(directory)
    download('https://raw.githubusercontent.com/RapidAI/RapidOCR/main/LICENSE',directory/'LICENSE.OCR.Apache-2.0.txt')
    return metadata
if __name__=='__main__':prepare(pathlib.Path(__file__).resolve().parents[1]/'assets/models/opus-en-es')
