"""Read-only catalog and public gateway/source diagnostics; no generation calls."""
import concurrent.futures
import importlib.util
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
skill = Path(r'C:\Users\miaoyin\.codex\skills\cm-imagegen\scripts\cm_image_gen.py')
spec = importlib.util.spec_from_file_location('cm_catalog_transport', skill)
cm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cm
spec.loader.exec_module(cm)
provider, _ = cm.configured_provider()
parsed = urllib.parse.urlsplit(provider.base_url)
root = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, '/', '', ''))
out = Path(__file__).resolve().parent / 'catalog-diagnostics'
out.mkdir(exist_ok=True)

def fetch(url, auth=False):
    headers = {'User-Agent': 'cm-imagegen-readonly-diagnostic', 'Accept': 'application/json,text/html,*/*'}
    if auth:
        headers['Authorization'] = 'Bearer ' + provider.api_key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as resp:
        return resp.read(), {k: v for k, v in resp.headers.items() if k.lower() in ('server', 'date', 'etag', 'last-modified', 'cache-control', 'age', 'x-request-id', 'content-type')}

def catalog():
    raw, headers = fetch(provider.base_url + '/models', auth=True)
    data = json.loads(raw)
    (out / 'models.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'headers': headers, 'root_keys': list(data), 'image_entries': [e for e in data.get('data', []) if 'image' in str(e.get('id', ''))], 'model_count': len(data.get('data', []))}

def frontend():
    raw, headers = fetch(root)
    html = raw.decode('utf-8', 'replace')
    scripts = re.findall(r'<script[^>]*src=[\"\']([^\"\']+)', html)
    conf_match = re.search(r'window\.__APP_CONFIG__\s*=\s*(\{.*?\})\s*;', html, re.S)
    conf = {}
    if conf_match:
        try:
            all_conf = json.loads(conf_match.group(1))
            conf = {k:v for k,v in all_conf.items() if any(s in k.lower() for s in ('version','build','model','site_name'))}
        except ValueError:
            pass
    contexts = []
    for src in scripts:
        js, _ = fetch(urllib.parse.urljoin(root, src))
        text = js.decode('utf-8','replace')
        (out / Path(urllib.parse.urlsplit(src).path).name).write_text(text, encoding='utf-8')
        for match in re.finditer(r'/version|/models|/health|build_time|git_commit|app_version', text):
            contexts.append(text[max(0,match.start()-130):match.end()+180])
    return {'title': re.findall(r'<title>(.*?)</title>', html, re.S), 'headers': headers, 'bundles': scripts, 'public_config': conf, 'endpoint_contexts': contexts[:35]}

def source_tree():
    raw, _ = fetch('https://api.github.com/repos/Wei-Shaw/sub2api/git/trees/main?recursive=1')
    tree = json.loads(raw)
    (out / 'public-source-tree.json').write_text(json.dumps(tree), encoding='utf-8')
    paths = [x['path'] for x in tree.get('tree',[]) if x['type']=='blob' and x['path'].endswith('.go') and ('model' in x['path'].lower() or ('openai' in x['path'] and '/handler/' in x['path']) or '/server/routes/' in x['path'])]
    return {'commit': tree.get('sha'), 'candidate_paths': paths}

jobs = {'catalog': catalog, 'frontend': frontend, 'source_tree': source_tree}
result = {}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(fn): name for name, fn in jobs.items()}
    for future in concurrent.futures.as_completed(futures):
        name = futures[future]
        try:
            result[name] = future.result()
        except Exception as exc:
            result[name] = {'error_type':type(exc).__name__, 'error':str(exc)}
(out / 'discovery.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
