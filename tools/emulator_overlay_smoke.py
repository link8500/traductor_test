"""Exercise the actual overlay on a local fixture.

The default is the dedicated emulator; a phone requires an explicit serial.
No device fallback, production hooks, or external websites. Coordinates
for the floating action come from its rendered circle in the current screenshot.
"""
import argparse,io,json,pathlib,re,subprocess,time,xml.etree.ElementTree as ET
import cv2
import numpy as np
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parents[1]
ADB=r'C:\Android\Sdk\platform-tools\adb.exe'
SERIAL='emulator-5554'
QA=ROOT/'build/full-comics'
UI_EVENTS=[]

def adb(*args):
    return subprocess.check_output([ADB,'-s',SERIAL,*map(str,args)],timeout=40)

def screen(path):
    data=adb('exec-out','screencap','-p');path.write_bytes(data)
    return np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))

def nodes():
    for _ in range(3):
        adb('shell','uiautomator','dump','/data/local/tmp/luma-motion-ui.xml')
        controls=list(ET.fromstring(adb('shell','cat','/data/local/tmp/luma-motion-ui.xml')).iter('node'))
        if not any(n.get('text')=="System UI isn't responding" for n in controls):return controls
        wait=next((n for n in controls if n.get('text')=='Wait' and n.get('package')=='android'),None)
        if wait is None:break
        UI_EVENTS.append('Emulator System UI ANR: selected Wait; no Luma ANR dismissed')
        click(wait);time.sleep(1)
    raise RuntimeError('Emulator System UI is blocking the test')

def click(node):
    x1,y1,x2,y2=map(int,re.findall(r'\d+',node.get('bounds')))
    adb('shell','input','tap',(x1+x2)//2,(y1+y2)//2)

def allow_fixture_notifications(controls):
    if any(n.get('text')=='Allow Luma to send you notifications?' for n in controls):
        click(next(n for n in controls if n.get('resource-id')=='com.android.permissioncontroller:id/permission_allow_button'))
        return True
    return False

def capture_consent():
    controls=nodes()
    if allow_fixture_notifications(controls):return None
    if any(n.get('resource-id')=='com.android.systemui:id/screen_share_dialog_title' and 'Luma' in n.get('text','') for n in controls) and any(n.get('text')=='Compartir pantalla' for n in controls):
        assert any(n.get('text')=='Compartir pantalla completa' for n in controls),'POCO must share the whole test screen'
        return next(n for n in controls if n.get('resource-id')=='android:id/button1' and n.get('text')=='Compartir pantalla')
    share=next((n for n in controls if n.get('resource-id')=='android:id/button1' and n.get('text')=='Share screen'),None)
    if share is not None:return share
    state=status()
    if any(s in state for s in ['Modelo local listo','textos','Pantalla cambiada','Leyendo y traduciendo']):return 'already-active'
    return None

def button(image,colour=(214,238,168)):
    # Exact public action colour; refuse ambiguous or missing controls.
    mask=np.all(np.abs(image.astype(np.int16)-np.array(colour))<4,axis=2).astype(np.uint8)
    count,_,stats,centres=cv2.connectedComponentsWithStats(mask)
    hits=[tuple(map(int,centres[i])) for i in range(1,count)
          if stats[i,4]>2000 and 65<stats[i,2]<200 and .8<stats[i,2]/stats[i,3]<1.2]
    assert len(hits)==1,('Cannot identify the single floating action',hits)
    return hits[0]

def status():
    data=adb('shell','dumpsys','notification','--noredact').decode('utf-8','replace')
    for record in data.split('NotificationRecord('):
        if 'pkg=com.example.traductor ' not in record:continue
        match=re.search(r'android.text=(?:String|SpannableString)\s*\((.*?)\)',record)
        if match:return match[1]
    return ''

def wait_for(check,seconds=60):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=check()
        if isinstance(value,ET.Element) or value:return value
        time.sleep(1)
    raise TimeoutError('Timed out waiting for emulator state')

def main():
    global SERIAL
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--expect-tap-preserved',action='store_true')
    parser.add_argument('--current-page',action='store_true',help='Translate the already scrolled local fixture, without restarting capture')
    parser.add_argument('--fixture',default='emulator-fixture.html')
    parser.add_argument('--anchor',default='')
    parser.add_argument('--device',default='emulator-5554',help='Explicit serial; never fall back to another connected device')
    parser.add_argument('--button-rgb',default='214,238,168',help='Action colour observed in the device screenshot')
    parser.add_argument('--drag-repetitions',type=int,default=1)
    parser.add_argument('--translate-only',action='store_true',help='Check capture and translation without asserting gestures')
    args=parser.parse_args()
    assert re.fullmatch(r'[A-Za-z0-9_-]+',args.device)
    SERIAL=args.device
    palette=tuple(map(int,args.button_rgb.split(',')));assert len(palette)==3 and all(0<=c<=255 for c in palette)
    assert 1<=args.drag_repetitions<=10
    assert re.fullmatch(r'(?:emulator-(?:fixture|handwriting|whole-words)|chapter-[0-9]{1,3})\.html',args.fixture)
    assert not args.anchor or re.fullmatch(r'[a-z0-9-]+',args.anchor)
    assert re.fullmatch(r'[a-zA-Z0-9_-]+',args.label)
    directory=QA/args.label;directory.mkdir(exist_ok=True)
    report={'device':SERIAL,'fixture':args.fixture,'anchor':args.anchor,'tap_should_preserve':args.expect_tap_preserved,'steps':[],'infrastructure_events':UI_EVENTS}
    def record(name):
        image=screen(directory/(name+'.png'))
        pid=adb('shell','pidof','com.example.traductor').decode().strip()
        state=status();entry={'step':name,'pid':pid,'status':state}
        report['steps'].append(entry);print(json.dumps(entry,ensure_ascii=False),flush=True)
        (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return image,state
    try:
        if args.current_page:
            before,state=record('before-second-manual-translation')
            assert 'Pantalla cambiada' in state,state
            time.sleep(3)
            before,state=record('still-original-without-a-request')
            assert 'Pantalla cambiada' in state,state
            x,y=button(before,palette);adb('shell','input','tap',x,y)
            wait_for(lambda:'textos' in status(),120)
            record('second-page-translated')
            assert len({r['pid'] for r in report['steps']})==1,'Luma restarted'
            report['success']=True
            return
        adb('reverse','tcp:8765','tcp:8765')
        # Release the preceding comic reader before traversing accessibility;
        # long WebView chapters can otherwise exhaust the dump process.
        adb('shell','am','force-stop','com.example.traductor')
        adb('shell','am','force-stop','com.example.traductor.test')
        controls=nodes()
        if allow_fixture_notifications(controls):
            time.sleep(1);controls=nodes()
        if any(n.get('text')=='Share your screen with Luma?' for n in controls):
            cancel=next(n for n in controls if n.get('resource-id')=='android:id/button2')
            click(cancel)
        # A reused Activity receives a new Intent without rerunning onCreate.
        # Start a fresh fixture reader so its URL and scroll position are real.
        adb('shell','am','start','-W','-n','com.example.traductor.test/com.example.traductor.FixtureActivity',
            '--es','url','http://127.0.0.1:8765/full-comics/'+args.fixture+('#'+args.anchor if args.anchor else ''))
        adb('shell','am','start','-W','-n','com.example.traductor/.MainActivity')
        main_image=screen(directory/'main.png');main_height,main_width=main_image.shape[:2]
        for _ in range(8):
            controls=nodes();activate=next((n for n in controls if n.get('content-desc')=='Activar barra flotante'),None)
            if activate is not None:break
            adb('shell','input','swipe',int(main_width*900/1080),int(main_height*2000/2400),int(main_width*900/1080),int(main_height*1050/2400),400)
        assert activate is not None,'Activation control missing'
        click(activate)
        consent=wait_for(capture_consent,45)
        if isinstance(consent,ET.Element):click(consent)
        wait_for(lambda:b'com.example.traductor' in adb('shell','dumpsys','media_projection'),30)
        # Someone watching the phone may already have translated the page.
        # Wait for that request to finish, then make our own recorded capture.
        wait_for(lambda:any(s in status() for s in ['Modelo local listo','textos','Pantalla cambiada']),120)
        before,_=record('before');x,y=button(before,palette)
        height,width=before.shape[:2];scale=width/1080
        adb('shell','input','tap',x,y)
        time.sleep(.35);record('busy')
        wait_for(lambda:'textos' in status() or 'Pantalla cambiada' in status(),120)
        translated,state=record('translated');assert 'textos' in state,state
        if args.translate_only:
            report['scope']='Capture and translation only; gestures not checked in this run'
            assert len({r['pid'] for r in report['steps']})==1,'Luma restarted'
            report['success']=True
            return
        # The blank right margin is inert in the local reader.
        adb('shell','input','tap',int(width*1050/1080),int(height*1340/2400));time.sleep(2)
        after,state=record('after-inert-tap')
        preserved='textos' in state
        assert preserved==args.expect_tap_preserved,('Inert tap',state)
        if not preserved:
            x,y=button(after,palette);adb('shell','input','tap',x,y)
            wait_for(lambda:'textos' in status(),120)
            after,_=record('translated-again')
        for index in range(args.drag_repetitions):
            x,y=button(after,palette);start=int(x-140*scale)
            end=max(50,min(width-50,int(start+(350 if x<width*.5 else -350)*scale)))
            end_y=max(100,min(height-150,int(y+(650 if y<height*.6 else -650)*scale)))
            adb('shell','input','swipe',start,y,end,end_y,700);time.sleep(2)
            after,state=record('after-toolbar-drag'+('' if index==0 else '-'+str(index+1)))
            assert 'textos' in state,('Toolbar drag',state)
            moved_x,moved_y=button(after,palette)
            assert abs(moved_x-x)+abs(moved_y-y)>20,'The test did not actually move the toolbar'
        adb('shell','input','swipe',int(width*1040/1080),int(height*2200/2400),int(width*1040/1080),int(height*900/2400),500)
        wait_for(lambda:'Pantalla cambiada' in status(),15)
        record('after-page-swipe')
        assert len({r['pid'] for r in report['steps']})==1,'Luma restarted'
        report['success']=True
    except Exception:
        screen(directory/'failure.png')
        (directory/'failure-ui.xml').write_bytes(adb('shell','cat','/data/local/tmp/luma-motion-ui.xml'))
        raise
    finally:
        (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
