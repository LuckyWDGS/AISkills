"""One independent Images request using the installed cm-imagegen transport.

The requested 2.6 names are registered in the provider-scoped local catalog.
This runner sends them unchanged to the SAME configured provider and uses cm's
transport/polling behavior. It does not change the installed skill/config.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL_SCRIPT = Path(r'C:\Users\miaoyin\.codex\skills\cm-imagegen\scripts\cm_image_gen.py')
spec = importlib.util.spec_from_file_location('cm_benchmark_transport', SKILL_SCRIPT)
cm = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cm
spec.loader.exec_module(cm)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--size', default='1536x1024')
    parser.add_argument('--complexity', choices=['low', 'medium', 'high'])
    parser.add_argument('--max-attempts', type=cm.retry_attempt_count, default=1)
    parser.add_argument('--image', action='append', default=[])
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    if args.model not in ('gpt-image-2.6-flare', 'gpt-image-2.6-sunburst'):
        parser.error('This benchmark accepts only the two explicitly requested 2.6 names.')
    prompt_path = Path(args.prompt_file)
    prompt = prompt_path.read_text(encoding='utf-8-sig')
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    operation = 'edit' if args.image else 'generate'
    payload = dict(model=args.model, prompt=prompt, size=args.size,
                   quality='max', response_format='b64_json', n=1)
    if args.complexity:
        payload['complexity'] = args.complexity
    inputs = [cm.load_input_image(Path(p), 'Benchmark reference') for p in args.image]
    multipart = {'fields': payload, 'files': [{'field': 'image', 'image': i} for i in inputs]} if inputs else None
    metadata = dict(case=args.case, requested_model=args.model, api='images',
                    quality='max', complexity=args.complexity, requested_size=args.size, operation=operation,
                    prompt_file=str(prompt_path.resolve()),
                    prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                    references=[{'path': str(Path(p).resolve()), 'sha256': hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in args.image],
                    skill_script=str(SKILL_SCRIPT),
                    request_fields={k:v for k,v in payload.items() if k != 'prompt'},
                    complexity_field_present='complexity' in payload,
                    max_attempts=args.max_attempts,
                    started_at_utc=datetime.now(timezone.utc).isoformat())
    metadata_path = out / 'result.json'
    if metadata_path.exists():
        raise SystemExit('Existing result; refusing to accidentally repeat a billable request.')
    (out / 'request.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    start = time.monotonic()
    try:
        active_provider, _ = cm.configured_provider()
        metadata['catalog_check'] = cm.model_catalog_check(active_provider, args.model)
        if not metadata['catalog_check']['ok']:
            raise SystemExit(metadata['catalog_check']['error'])
        data, provider, endpoint, transport, request_url, errors = cm.request_with_retry(
            operation, payload, 600, multipart=multipart, max_attempts=args.max_attempts)
        items = cm.response_image_items(data)
        paths = [cm.save_image_from_item(item, out, args.case, i, provider) for i, item in enumerate(items)]
        metadata.update(ok=bool(paths), endpoint=endpoint, transport=transport,
                        api_provider=cm.cli_provider_label(provider),
                        attempt_count=len(errors) + 1, previous_errors=errors,
                        paths=[str(p.resolve()) for p in paths],
                        response_model=data.get('model'), usage=data.get('usage'), created=data.get('created'),
                        size_check=cm.validate_output_sizes(paths, args.size, require_exact=False),
                        async_poll_used=bool(data.get('_cm_async_poll_used')))
    except (Exception, SystemExit) as exc:
        metadata.update(ok=False, error_type=type(exc).__name__, error=str(exc))
    metadata['duration_seconds'] = round(time.monotonic() - start, 3)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0 if metadata.get('ok') else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
