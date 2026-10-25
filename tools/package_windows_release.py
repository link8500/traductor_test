"""Package the complete tested Windows release, excluding QA/corpus files."""
import argparse,hashlib,json,pathlib,zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    assert args.version.replace('.','').replace('+','').isdigit()
    source=ROOT/'build/windows/x64/runner/Release'
    assert (source/'traductor.exe').is_file()
    models=source/'data/flutter_assets/assets/models/opus-en-es'
    manifest=json.loads((models/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['files'].items():
        assert hashlib.sha256((models/name).read_bytes()).hexdigest()==digest,name
    directory=ROOT/'build/releases';directory.mkdir(exist_ok=True)
    target=directory/f'Luma-Windows-{args.version}.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for path in sorted(source.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(source).as_posix())
        archive.writestr('LEEME.txt',
            'Luma '+args.version+' para Windows x64\n\n'
            'Extrae TODO el ZIP en una misma carpeta y abre traductor.exe.\n'
            'Elige English -> Español en la aplicación y activa la barra.\n'
            'Pulsa el icono o Ctrl + Shift + L para traducir.\n'
            'Arrastra Luma para mover la barra. Al desplazarse la página,\n'
            'la traducción se retira. No se traduce otra vez hasta que lo pidas.\n\n'
            'OCR y traducción inglés -> español incluidos y sin conexión.\n'
            'El reconocimiento de letras decorativas y la traducción aún\n'
            'pueden fallar. Esta versión no certifica precisión perfecta.\n')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert {'traductor.exe','flutter_windows.dll','onnxruntime.dll'}<=set(archive.namelist())
    print(target,target.stat().st_size,'bytes',hashlib.sha256(target.read_bytes()).hexdigest())

if __name__=='__main__':main()
