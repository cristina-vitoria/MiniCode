#!/usr/bin/env python3
"""Optional Qwen-14B reference, using the identical selector prompt and parser."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from minicode.llm import QwenClient
from minicode.selector_protocol import PROTOCOL_VERSION, selector_messages
from minicode.selector_training import sha256_file, write_json, write_jsonl
from minicode.specialization_data import load_examples, validate_examples
from evaluate_tool_selection import evaluate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    args=parser.parse_args()
    dataset=ROOT/'data/tool_selection/examples.jsonl'
    rows=load_examples(dataset)
    validate_examples(rows)
    client=QwenClient(args.env_file)
    args.output.mkdir(parents=True,exist_ok=False)
    manifest={'status':'running','role':'additional_reference_not_finetuning_baseline',
        'model':client.model,'dataset_sha256':sha256_file(dataset),'protocol':PROTOCOL_VERSION,
        'protocol_sha256':sha256_file(ROOT/'src/minicode/selector_protocol.py'),
        'started_at':datetime.now(timezone.utc).isoformat(), 'calls':0,
        'generation':{'temperature':0.0,'max_tokens':4096},
        'limitation':'API Qwen uses 4096 output tokens; small-model protocol caps at 16.'}
    write_json(args.output/'manifest.json',manifest)
    predictions=[]
    start=time.monotonic()
    try:
        for row in [r for r in rows if r['split']=='test']:
            manifest['calls']+=1
            raw=client.complete(selector_messages(**row['input']))
            predictions.append({'id':row['id'],'tool':raw.strip(),'raw_output':raw})
            write_jsonl(args.output/'predictions.jsonl',predictions)
            write_json(args.output/'manifest.json',manifest)
            print(f"Reference {len(predictions)}/16 saved",flush=True)
        report=evaluate(rows,{r['id']:r['tool'] for r in predictions})
        write_json(args.output/'report.json',report)
        manifest['status']='complete'
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as exc:
        manifest.update(status='incomplete',error_type=type(exc).__name__)
        raise
    finally:
        manifest['seconds']=time.monotonic()-start
        manifest['ended_at']=datetime.now(timezone.utc).isoformat()
        write_json(args.output/'manifest.json',manifest)


if __name__=='__main__':
    main()
