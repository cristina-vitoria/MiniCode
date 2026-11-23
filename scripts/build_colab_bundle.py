#!/usr/bin/env python3
"""Create a reviewed source bundle, excluding env files, weights and workspaces."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/minicode-colab.zip')
    args = parser.parse_args()
    files = [ROOT/'README.md',ROOT/'AI_USAGE.md',ROOT/'pyproject.toml',ROOT/'requirements-ml.txt']
    for directory, patterns in {'src':['*.py','*.ini'], 'scripts':['*.py'],
            'tests':['*.py'], 'notebooks':['*.ipynb'], 'docs':['*.md'],
            'data':['*.jsonl','*.md'], 'experiments/tool_selection':['*.json','*.jsonl','*.md','loss.png','environment.txt'],
            'experiments/end_to_end':['*.json','*.md'],
            'softwareteste':['*.py','*.md','*.ini','*.txt','*.lock'],
            'sandbox':['Dockerfile','*.lock']}.items():
        for pattern in patterns:
            files.extend(p for p in (ROOT/directory).rglob(pattern)
                         if not any(part.startswith('.') or part=='__pycache__' for part in p.relative_to(ROOT).parts))
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(set(files))}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():
        parser.error('Arquivo já existe; use outro --output para preservar a versão anterior')
    with zipfile.ZipFile(args.output,'x',zipfile.ZIP_DEFLATED) as archive:
        for path in hashes:
            archive.write(ROOT/path, 'MiniCode-parte2/'+path)
        archive.writestr('MiniCode-parte2/BUNDLE_MANIFEST.json',json.dumps(hashes,indent=2)+'\n')
    print(json.dumps({'path':str(args.output),'files':len(hashes),
                      'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()},indent=2))


if __name__ == '__main__':
    main()
