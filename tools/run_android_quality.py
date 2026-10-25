"""Run the app's release instrumentation and retrieve only its fixture reports."""
import argparse,base64,gzip,json,pathlib,subprocess,zipfile
root=pathlib.Path(__file__).resolve().parents[1]
qa=root/'build/comic-quality';adb=r'C:\Android\Sdk\platform-tools\adb.exe'
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['model','ocr','full']);parser.add_argument('--import-fixtures',action='store_true')
parser.add_argument('--serial');parser.add_argument('--output-directory',type=pathlib.Path,default=qa);args=parser.parse_args()
adb_command=[adb]+(['-s',args.serial] if args.serial else [])
destination=args.output_directory;destination.mkdir(parents=True,exist_ok=True)
if args.import_fixtures:
    fixture=destination/'fixtures.zip'
    with zipfile.ZipFile(fixture,'w',compression=zipfile.ZIP_STORED) as archive:
        for name in ['manifest.json','model-input.json']:archive.write(qa/name,name)
        if args.mode!='model':
            for image in (qa/'images').rglob('*.webp'):archive.write(image,image.relative_to(qa).as_posix())
    subprocess.run(adb_command+['push',str(fixture),'/data/local/tmp/luma-quality-fixtures.zip'],check=True)
command=adb_command+['shell','am','instrument','-w','-r','-e','mode',args.mode]
if args.import_fixtures:command+=['-e','import','true']
command+=['com.example.traductor.test/com.example.traductor.QualityBenchmarkRunner']
process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
group={};files={};success=False
with (destination/f'android-{args.mode}-instrumentation.log').open('w',encoding='utf-8') as log:
    for line in process.stdout:
        log.write(line);log.flush()
        if line.startswith('INSTRUMENTATION_STATUS: '):
            key,_,value=line[len('INSTRUMENTATION_STATUS: '):].rstrip('\n').partition('=');group[key]=value
        elif line.startswith('INSTRUMENTATION_STATUS_CODE:'):
            if 'luma_file' in group:
                files.setdefault(group['luma_file'],{})[int(group['luma_part'])]=group['luma_data']
            elif group.get('stream'):print(group['stream'],flush=True)
            group={}
        elif line.startswith('INSTRUMENTATION_CODE: -1'):success=True
        elif line.startswith('INSTRUMENTATION_RESULT: stream='):print(line.strip(),flush=True)
process.wait()
if args.import_fixtures:subprocess.run(adb_command+['shell','rm','-f','/data/local/tmp/luma-quality-fixtures.zip'],check=True)
for name,chunks in files.items():
    assert pathlib.Path(name).name==name
    data=gzip.decompress(base64.b64decode(''.join(chunks[index] for index in sorted(chunks))))
    (destination/name).write_bytes(data);print('saved',name,len(data),'bytes',flush=True)
if not success:raise SystemExit('Instrumentation failed; see the saved log.')
