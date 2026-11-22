#!/usr/bin/env python3
"""Run all end-to-end conditions against the same source and budgets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from minicode.evaluator import evaluate
from minicode.llm import QwenClient
from minicode.local_selector import LocalSelectorClient
from minicode.selector_protocol import PROTOCOL_VERSION
from minicode.selector_training import sha256_file, write_json
from minicode.tool_selector import OpenAICompatibleToolSelector


def code_fingerprint():
    paths = list((ROOT/'src/minicode').rglob('*.py')) + list((ROOT/'scripts').glob('*.py'))
    paths += [ROOT/'pyproject.toml', ROOT/'requirements-ml.txt']
    return {str(p.relative_to(ROOT)): sha256_file(p) for p in sorted(paths)}


def validate_export(run_dir):
    manifest = json.loads((run_dir/'run_manifest.json').read_text())
    if manifest.get('status') != 'local_evaluation_complete' or manifest.get('protocol') != PROTOCOL_VERSION:
        raise ValueError('Exporte primeiro uma execução local completa com protocolo atual')
    for filename in ('src/minicode/selector_protocol.py', 'src/minicode/selector_training.py'):
        if sha256_file(ROOT/filename) != manifest['code_sha256'][filename]:
            raise ValueError('Protocolo de inferência difere do notebook executado: '+filename)
    for name, digest in manifest['adapter_files'].items():
        if Path(name).name != name or sha256_file(run_dir/'adapter'/name) != digest:
            raise ValueError('Adapter alterado/incompleto')
    for name in ('base_test', 'lora_test', 'lora_no_context_test'):
        for suffix in ('_predictions.jsonl', '_report.json'):
            filename = name + suffix
            if sha256_file(run_dir/filename) != manifest['artifact_sha256'][filename]:
                raise ValueError('Resultado local alterado/incompleto: '+filename)
    if sha256_file(ROOT/'data/tool_selection/examples.jsonl') != manifest['dataset_sha256']:
        raise ValueError('Dataset local difere do treinamento')
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True, help='Saída completa exportada pelo notebook')
    parser.add_argument('--output', type=Path, required=True, help='Destino novo')
    parser.add_argument('--env-file', type=Path, default=ROOT/'.env')
    parser.add_argument('--device', choices=['cpu','cuda'], default='cpu')
    parser.add_argument('--quantized', action='store_true')
    parser.add_argument('--max-iterations', type=int, default=3)
    parser.add_argument('--max-actions', type=int, default=20)
    parser.add_argument('--max-llm-calls', type=int, default=80)
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--image', default='minicode-tests:parte1')
    args = parser.parse_args(argv)
    if min(args.max_iterations,args.max_actions,args.max_llm_calls,args.timeout) < 1:
        parser.error('Limites devem ser positivos')
    if args.output.exists():
        parser.error('Destino já existe; use uma nova pasta')
    training = validate_export(args.run_dir)
    qwen = QwenClient(args.env_file)
    image_id = subprocess.run(['docker','image','inspect','--format={{.Id}}',args.image],
                             check=True, capture_output=True, text=True).stdout.strip()
    selector_client = LocalSelectorClient(training['config']['model'], device=args.device,
        quantized=args.quantized, revision=training['model_revision'],
        adapter=args.run_dir/'adapter', tokenizer_path=args.run_dir/'adapter')
    snapshot = code_fingerprint()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {'status':'running', 'started_at':datetime.now(timezone.utc).isoformat(),
        'code_sha256':snapshot, 'qwen_model':qwen.model, 'selector':selector_client.metadata,
        'docker_image_id':image_id,
        'training_manifest_sha256':sha256_file(args.run_dir/'run_manifest.json'),
        'call_budget':'total main + selector', 'conditions':{}}
    write_json(args.output/'manifest.json',manifest)
    try:
        for name, context in [('qwen',None), ('qwen_lora',True), ('qwen_lora_no_context',False)]:
            if code_fingerprint() != snapshot:
                raise RuntimeError('Código mudou durante o experimento; preserve a execução parcial')
            factory = None if context is None else (lambda context=context:
                OpenAICompatibleToolSelector(selector_client, include_context=context))
            report = evaluate(lambda:QwenClient(args.env_file), args.output/name, mode='docker',
                source=ROOT/'softwareteste', image=image_id, timeout=args.timeout,
                max_iterations=args.max_iterations, max_actions=args.max_actions,
                max_llm_calls=args.max_llm_calls, tool_selector_factory=factory,
                tool_selector_context=context, progress=lambda s:print(name, s, flush=True))
            manifest['conditions'][name] = {'complete':report['complete'], 'metrics':report['metrics']}
            write_json(args.output/'manifest.json',manifest)
            if not report['complete']:
                raise RuntimeError('Bateria incompleta: '+name)
        manifest['status'] = 'complete'
    except BaseException as exc:
        manifest['status'] = 'incomplete'
        manifest['error_type'] = type(exc).__name__
        raise
    finally:
        manifest['ended_at'] = datetime.now(timezone.utc).isoformat()
        write_json(args.output/'manifest.json',manifest)
    print(json.dumps(manifest['conditions'],indent=2))


if __name__ == '__main__':
    main()
