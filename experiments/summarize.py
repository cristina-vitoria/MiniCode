"""Summarize all runs, including failures, with rejected model responses from execution traces."""
import html
import json
from pathlib import Path

base = Path(__file__).resolve().parent / 'results'
rows = []
for folder in sorted(base.glob('qwen-*')):
    if not folder.is_dir(): continue
    file = folder/'results.json'
    if not file.exists(): continue
    result = json.loads(file.read_text())
    failures = []
    for task in result['tasks']:
        events = []
        for run_dir in sorted((folder/task['id']/'.minicode').glob('*')):
            trace = run_dir/'actions.jsonl'
            if trace.is_file():
                events.extend(json.loads(line) for line in trace.read_text().splitlines() if line.strip())
        rejected = [
            {key: event[key] for key in ('kind', 'state', 'llm_call', 'attempt',
                                        'validation', 'reason', 'error', 'raw_response') if key in event}
            for event in events if event.get('kind') in {'invalid_response', 'tool_rejected'}
        ]
        errors = [e['error'] for e in events if e['kind'] == 'error']
        categories = []
        if any(e['kind'] == 'invalid_response' for e in events) or any('Especificação' in e or 'Plano inválido' in e or 'JSON' in e for e in errors): categories.append('formato/estrutura')
        if any(e['kind'] == 'tool_rejected' for e in events): categories.append('ferramenta recusada')
        if any('Contexto' in e or 'Limite' in e for e in errors): categories.append('limite de contexto/chamadas')
        if any('conexão' in e or 'HTTP' in e or 'Runner' in e for e in errors) or 'Runner indisponível' in task['acceptance'].get('output', ''): categories.append('infraestrutura')
        if not task['success'] and not categories: categories.append('implementação/verificação')
        failures.append({'id':task['id'], 'success':task['success'], 'state':task['state'], 'categories':categories, 'errors':errors, 'rejected_responses':rejected, 'iterations':task['iterations'], 'llm_calls':task['llm_calls']})
    rows.append({'run':folder.name, 'metrics':result['metrics'], 'tasks':failures})
(base/'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
lines = ['# Resultados das execuções Qwen', '', 'Todas as execuções planejadas são reportadas. Falhas permanecem no denominador. As categorias também registram ocorrências recuperadas durante tarefas bem-sucedidas.', '', '| Execução | Tarefas | TaskSuccessRate | FirstAttemptSuccess | AverageIterations | AverageLLMCalls |', '|---|---:|---:|---:|---:|---:|']
for row in rows:
    m=row['metrics']; lines.append(f"| {row['run']} | {m['total_tasks']} | {m['TaskSuccessRate']:.2%} | {m['FirstAttemptSuccess']:.2%} | {m['AverageIterations']:.2f} | {m['AverageLLMCalls']:.2f} |")
for row in rows:
    lines += ['', f"## {row['run']}", '']
    for task in row['tasks']:
        lines.append(f"- {task['id']}: {task['state']}; sucesso independente={task['success']}; {', '.join(task['categories']) or 'sucesso'}; {'; '.join(task['errors']) or 'sem erro fatal registrado'}.")
        for rejection in task['rejected_responses']:
            reason = rejection.get('reason', rejection.get('error', 'Motivo não registrado'))
            lines += ['', f"  Chamada {rejection.get('llm_call', 'não registrada')} — {html.escape(rejection.get('validation', rejection['kind']))}: {html.escape(reason)}", '']
            if 'raw_response' in rejection:
                lines.append('<pre>' + html.escape(rejection['raw_response']) + '</pre>')
            else:
                lines.append('  Resposta bruta indisponível neste rastro antigo.')
lines += ['', 'A rejeição de uma especificação indica falha de estrutura exigida pelo harness; as respostas brutas disponíveis nos rastros são apresentadas acima e preservadas em summary.json. Rastros antigos podem não conter esse campo. Zero iterações significa falha antes da implementação, não solução na primeira tentativa.', '']
(base.parent/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps([{'run':r['run'], **r['metrics']} for r in rows], ensure_ascii=False))
