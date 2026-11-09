"""Complete only terminal 503/no-image cases after the user's renewed request.

Uses cm-imagegen's bounded retry once per missing case, no outer retry loop.
Preserves earlier failures and never reruns cases that already returned images.
"""
from run_benchmark import ROOT,CLI,sha,now,dump
import json,subprocess,sys,time
from PIL import Image

def main():
    initial=json.loads((ROOT/'run_status.json').read_text(encoding='utf-8'))
    target=ROOT/'recovery_20261107'
    target.mkdir(exist_ok=False)
    results=[]
    for original in initial['cases']:
        if original.get('has_readable_image'):continue
        if 'status=503' not in original['result'].get('error',''):
            continue
        case=original['case'];out=target/case;out.mkdir()
        prompt_path=ROOT/'prompts'/f"{case.split('_')[0]}.txt"
        reference=ROOT/'references'/'edit_control_2k.png'
        assert sha(prompt_path)==original['prompt_sha256']
        if original['operation']=='edit':assert sha(reference)==original['reference_sha256']
        args=[sys.executable,'-X','utf8',str(CLI),original['operation'],'--api','images',
              '--model',original['requested_model'],'--prompt',prompt_path.read_text(encoding='utf-8'),
              '--size','2560x1440','--quality','max','--n','1','--output-format','png',
              '--response-format','b64_json','--require-exact-size','--timeout','900',
              '--max-attempts','3','--out-dir',str(out),'--filename',case]
        if original['operation']=='edit':args+=['--image',str(reference)]
        meta={k:original[k] for k in ['case','requested_model','operation','prompt_path','prompt_sha256',
              'requested_size','quality','complexity','seed','reference_sha256']}
        meta.update(started_at_utc=now(),max_attempts=3,script_sha256=sha(CLI),
                    prior_result=str(ROOT/'results'/case/'result.json'),
                    reason='Renewed user request after terminal 503/no-image result; preserve same visual inputs.')
        dump(out/'request.json',meta)
        print(json.dumps(dict(event='started',case=case,at=now())),flush=True)
        start=time.monotonic()
        proc=subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace')
        (out/'cli_stdout.json').write_text(proc.stdout,encoding='utf-8')
        (out/'cli_stderr.txt').write_text(proc.stderr,encoding='utf-8')
        try:result=json.loads(proc.stdout)
        except json.JSONDecodeError:result=dict(ok=False,error=(proc.stderr or proc.stdout).strip())
        meta.update(duration_seconds=round(time.monotonic()-start,2),exit_code=proc.returncode,
                    completed_at_utc=now(),result=result,images=[])
        for saved in result.get('paths',[]):
            p=__import__('pathlib').Path(saved)
            with Image.open(p) as pic:
                pic.load();meta['images'].append(dict(path=str(p),size=list(pic.size),mode=pic.mode,sha256=sha(p),readable=True))
        meta['has_readable_image']=bool(meta['images'])
        meta['meets_2k']=bool(meta['images']) and all(x['size']==[2560,1440] for x in meta['images'])
        dump(out/'result.json',meta);results.append(meta)
        dump(target/'status.json',dict(updated_at_utc=now(),cases=results))
        print(json.dumps(dict(event='completed',case=case,has_image=meta['has_readable_image'],
                              meets_2k=meta['meets_2k'],seconds=meta['duration_seconds'],
                              error=result.get('error')),ensure_ascii=False),flush=True)
    print(json.dumps(dict(event='recovery_completed',cases=len(results))),flush=True)

if __name__=='__main__':main()
