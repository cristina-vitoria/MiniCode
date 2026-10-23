"""Run every declared repetition and preserve metadata, failures and private-data review."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from minicode.config import read_config

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

def command(args):
    return subprocess.check_output(args, text=True).strip()

def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def main():
    config = read_config()
    image = json.loads(command(['docker', 'image', 'inspect', 'python:3.12-slim']))[0]
    metadata = {
        'commit': command(['git', 'rev-parse', 'HEAD']),
        'working_tree_status': command(['git', 'status', '--short']),
        'model': config['MINICODE_MODEL'],
        'timezone': 'America/Campo_Grande',
        'limits': {'max_iterations': 3, 'max_actions': 20, 'max_llm_calls': 80, 'context_chars': 48000, 'test_timeout_seconds': 30},
        'runner': 'docker', 'python': platform.python_version(),
        'docker_image': 'python:3.12-slim', 'docker_repo_digests': image['RepoDigests'],
        'docker_image_id': image['Id'],
        'container_python': command(['docker', 'run', '--rm', '--network=none', '--read-only', 'python:3.12-slim', 'python', '--version']),
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src/minicode').glob('*.py'))},
        'repetitions_planned': 2,
        'split': 'development',
    }
    base = ROOT/'experiments/results'
    base.mkdir(exist_ok=True)
    for index in (1, 2):
        output = base/f'qwen-{index:02d}'
        if output.exists() or (base/f'qwen-{index:02d}.metadata.json').exists():
            raise SystemExit(f'Refusing overwrite: {output.name}')
    for index in (1, 2):
        name = f'qwen-{index:02d}'
        output = base/name
        meta_path = base/f'{name}.metadata.json'
        run_meta = {**metadata, 'started_at': datetime.now(ZoneInfo(metadata['timezone'])).isoformat()}
        args = [sys.executable, '-m', 'minicode', '--evaluate', str(output.relative_to(ROOT))]
        run_meta['command'] = args
        write(meta_path, run_meta)
        print(f'Starting {name}', flush=True)
        with (base/f'{name}.console.log').open('w') as log:
            process = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
        run_meta.update(returncode=process.returncode, finished_at=datetime.now(ZoneInfo(metadata['timezone'])).isoformat())
        write(meta_path, run_meta)
        # Remove exact configured secrets and endpoint; do not print either.
        replacements = [(config.get('MINICODE_API_KEY', ''), '[REDACTED_API_KEY]'), (config.get('MINICODE_BASE_URL', ''), '[REDACTED_ENDPOINT]'), (str(Path.home()), '[HOME]')]
        redactions = []
        paths = list(output.rglob('*')) if output.exists() else []
        paths += [meta_path, base/f'{name}.console.log']
        for path in paths:
            if not path.is_file(): continue
            try: content = path.read_text()
            except UnicodeError: continue
            for value, replacement in replacements:
                if value and value in content:
                    content = content.replace(value, replacement)
                    redactions.append({'file': str(path.relative_to(base)), 'category': replacement})
            path.write_text(content)
        write(base/f'{name}.privacy-review.json', {'exact_config_values_checked': True, 'redactions': redactions, 'scope': 'Configured key, endpoint and home path; heuristic review still required for unrelated private data.'})
        if (output/'results.json').exists():
            results = json.loads((output/'results.json').read_text())
            print(name, json.dumps(results['metrics']), flush=True)
        else:
            print(name, 'Operational failure: no results.json; do not exclude six scheduled tasks.', flush=True)

if __name__ == '__main__':
    main()
