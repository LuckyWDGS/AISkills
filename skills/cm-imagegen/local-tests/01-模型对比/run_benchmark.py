"""Sequential first-sample benchmark through the installed cm-imagegen CLI."""
import hashlib,json,random,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
CLI=Path(r'C:\Users\miaoyin\.codex\skills\cm-imagegen\scripts\cm_image_gen.py')
MODELS=['gpt-image-2.5-flare','gpt-image-2.5-sunburst','gpt-image-2.6-flare','gpt-image-2.6-sunburst']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    mapping_path=ROOT/'model_key.json'
    if mapping_path.exists():
        raise SystemExit('Existing benchmark key: refusing a possible duplicate billable run.')
    shuffled=MODELS[:];random.SystemRandom().shuffle(shuffled)
    mapping=dict(zip('ABCD',shuffled));dump(mapping_path,mapping)
    reference=ROOT/'references'/'edit_control_2k.png'
    with Image.open(reference) as ref:
        assert ref.size==(2560,1440)
    cases=[]
    for task,operation in [('T1','generate'),('I1','edit')]:
        for code,model in mapping.items():
            case=f'{task}_{code}'
            out=ROOT/'results'/case;out.mkdir(parents=True,exist_ok=False)
            prompt_path=ROOT/'prompts'/f'{task}.txt'
            args=[sys.executable,'-X','utf8',str(CLI),operation,'--api','images','--model',model,
                  '--prompt',prompt_path.read_text(encoding='utf-8'),'--size','2560x1440',
                  '--quality','max','--n','1','--output-format','png','--response-format','b64_json',
                  '--require-exact-size','--timeout','900','--max-attempts','1',
                  '--out-dir',str(out),'--filename',case]
            if operation=='edit':args+=['--image',str(reference)]
            meta=dict(case=case,requested_model=model,operation=operation,started_at_utc=now(),
                      prompt_path=str(prompt_path),prompt_sha256=sha(prompt_path),
                      requested_size=[2560,1440],quality='max',complexity='omitted',seed='not exposed by CLI',
                      max_attempts=1,reference_sha256=sha(reference) if operation=='edit' else None,
                      script_sha256=sha(CLI))
            dump(out/'request.json',meta)
            print(json.dumps(dict(event='started',case=case,at=now())),flush=True)
            started=time.monotonic()
            proc=subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace')
            (out/'cli_stdout.json').write_text(proc.stdout,encoding='utf-8')
            (out/'cli_stderr.txt').write_text(proc.stderr,encoding='utf-8')
            try:result=json.loads(proc.stdout)
            except json.JSONDecodeError:result={'ok':False,'error':(proc.stderr or proc.stdout).strip()}
            meta.update(duration_seconds=round(time.monotonic()-started,2),exit_code=proc.returncode,
                        completed_at_utc=now(),result=result,images=[])
            for saved in result.get('paths',[]):
                p=Path(saved)
                try:
                    with Image.open(p) as pic:
                        pic.load();info=dict(path=str(p),size=list(pic.size),mode=pic.mode,sha256=sha(p),readable=True)
                except Exception as e:info=dict(path=str(p),readable=False,error=str(e))
                meta['images'].append(info)
            meta['has_readable_image']=any(i['readable'] for i in meta['images'])
            meta['meets_2k']=bool(meta['images']) and all(i.get('size')==[2560,1440] for i in meta['images'])
            dump(out/'result.json',meta);cases.append(meta)
            dump(ROOT/'run_status.json',dict(updated_at_utc=now(),completed=len(cases),total=8,cases=cases))
            print(json.dumps(dict(event='completed',case=case,ok=result.get('ok'),
                                  has_image=meta['has_readable_image'],meets_2k=meta['meets_2k'],
                                  seconds=meta['duration_seconds'],error=result.get('error')),
                             ensure_ascii=False),flush=True)
    print(json.dumps(dict(event='all_completed',count=len(cases))),flush=True)

if __name__=='__main__':main()
