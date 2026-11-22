#!/usr/bin/env python3
"""Recompute and summarize exported predictions; never fill absent experiments."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from minicode.specialization_data import load_examples, validate_examples
from minicode.selector_training import sha256_file
from evaluate_tool_selection import evaluate, read_predictions


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--end-to-end',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads((args.run_dir/'run_manifest.json').read_text())
    if manifest['status']!='local_evaluation_complete':
        parser.error('Execução local incompleta')
    dataset=args.run_dir/'dataset.jsonl'
    if sha256_file(dataset)!=manifest['dataset_sha256']:
        parser.error('Dataset difere do manifesto')
    rows=load_examples(dataset)
    validate_examples(rows)
    reports={}
    for name in ('base_test','lora_test','lora_no_context_test'):
        predictions=args.run_dir/f'{name}_predictions.jsonl'
        if sha256_file(predictions)!=manifest['artifact_sha256'][predictions.name]:
            parser.error('Predições diferem do manifesto')
        reports[name]=evaluate(rows,read_predictions(predictions))
    delta=reports['lora_test']['accuracy']-reports['base_test']['accuracy']
    ablation=reports['lora_test']['accuracy']-reports['lora_no_context_test']['accuracy']
    lines=['# Resultados da Parte 2','',
        '| Condição | Acertos | Acurácia | Inválidas |','|---|---:|---:|---:|']
    for name,report in reports.items():
        lines.append(f"| {name} | {report['correct']}/{report['examples']} | {report['accuracy']:.2%} | {report['invalid_predictions']} |")
    lines += ['',f'Diferença LoRA − base: {delta:+.2%} pontos percentuais.',
        f'Diferença contexto − sem contexto: {ablation:+.2%} pontos percentuais.',
        '', 'Este é um piloto sintético com duas famílias de teste e templates compartilhados.',
        'As decisões de uma família não são observações independentes. Não há evidência de generalização ampla.']
    if args.end_to_end:
        manifest_e2e=json.loads((args.end_to_end/'manifest.json').read_text())
        if manifest_e2e.get('status')!='complete': parser.error('Bateria end-to-end incompleta')
        if manifest_e2e['training_manifest_sha256'] != sha256_file(args.run_dir/'run_manifest.json'):
            parser.error('Bateria end-to-end pertence a outro treinamento')
        lines += ['','| Agente | TaskSuccessRate | FirstAttemptSuccess | Iterações | Chamadas totais |',
                  '|---|---:|---:|---:|---:|']
        expected=None
        for name in ('qwen','qwen_lora','qwen_lora_no_context'):
            report=json.loads((args.end_to_end/name/'results.json').read_text())
            if not report['complete']: parser.error('Condição incompleta: '+name)
            config=report['configuration']
            common={k:config[k] for k in ('source_digest','mode','max_iterations','max_actions','max_llm_calls','timeout','image')}
            if expected is not None and common!=expected: parser.error('Condições não comparáveis')
            expected=common
            m=report['metrics']
            lines.append(f"| {name} | {m['TaskSuccessRate']:.2%} | {m['FirstAttemptSuccess']:.2%} | {m['AverageIterations']:.2f} | {m['AverageLLMCalls']:.2f} |")
        lines += ['', 'As seis tarefas são públicas e uma única repetição não estima variabilidade.',
                  'Chamadas totais incluem o seletor; falhas de infraestrutura permanecem no denominador.']
    else:
        lines += ['', 'Avaliação end-to-end: PENDENTE. Não se pode concluir ganho no agente completo.']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        stream.write('\n'.join(lines)+'\n')
    print(args.output)


if __name__=='__main__':
    main()
