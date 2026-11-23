#!/usr/bin/env python3
"""Check exported adapter inference in the exact local CPU serving runtime."""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from minicode.local_selector import LocalSelectorClient
from minicode.selector_training import predict, sha256_file, write_json, write_jsonl
from minicode.specialization_data import load_examples
from run_part2_experiments import validate_export
from evaluate_tool_selection import evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--quantized',action='store_true',help='NF4/double quant, float16; requires bitsandbytes 0.48.2')
    args=parser.parse_args()
    training=validate_export(args.run_dir)
    if args.output.exists(): parser.error('Destino já existe')
    rows=load_examples(args.run_dir/'dataset.jsonl')
    test=[row for row in rows if row['split']=='test']
    client=LocalSelectorClient(training['config']['model'],device='cpu',quantized=args.quantized,
        revision=training['model_revision'],adapter=args.run_dir/'adapter',
        tokenizer_path=args.run_dir/'adapter')
    args.output.mkdir(parents=True,exist_ok=False)
    manifest={'status':'running','role':'CPU deployment check; separate from Colab GPU experiment',
        'started_at':datetime.now(timezone.utc).isoformat(),
        'training_manifest_sha256':sha256_file(args.run_dir/'run_manifest.json'),
        'selector':client.metadata,'versions':{name:importlib.metadata.version(name)
            for name in ('torch','transformers','peft','trl')},'conditions':{}}
    if args.quantized:
        manifest['versions']['bitsandbytes']=importlib.metadata.version('bitsandbytes')
    write_json(args.output/'manifest.json',manifest)
    try:
        for name,enabled,context in [('base',False,True),('lora',True,True),('lora_no_context',True,False)]:
            predictions=[]
            for index,row in enumerate(test,1):
                predictions.extend(predict(client.model_object,client.tokenizer,[row],
                    adapter_enabled=enabled,include_context=context))
                write_jsonl(args.output/f'{name}_predictions.jsonl',predictions)
                print(f'{name}: {index}/{len(test)}',flush=True)
            report=evaluate(rows,{p['id']:p['tool'] for p in predictions})
            write_json(args.output/f'{name}_report.json',report)
            manifest['conditions'][name]={k:report[k] for k in ('examples','correct','accuracy','invalid_predictions')}
            write_json(args.output/'manifest.json',manifest)
        manifest['status']='complete'
    except BaseException as exc:
        manifest.update(status='incomplete',error=type(exc).__name__)
        raise
    finally:
        manifest['ended_at']=datetime.now(timezone.utc).isoformat()
        write_json(args.output/'manifest.json',manifest)
    print(json.dumps(manifest['conditions'],indent=2))


if __name__=='__main__': main()
