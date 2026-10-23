"""Summarize all runs, including failures, without exposing task contents."""
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
        for trace in (folder/task['id']/'.minicode').glob('*/actions.jsonl'):
            events.extend(json.loads(line) for line in trace.read_text().splitlines())
        errors = [e['error'] for e in events if e['kind'] == 'error']
        categories = []
        if any(e['kind'] == 'invalid_response' for e in events) or any('Especificação' in e or 'Plano inválido' in e or 'JSON' in e for e in errors): categories.append('formato/estrutura')
        if any(e['kind'] == 'tool_rejected' for e in events): categories.append('ferramenta recusada')
        if any('Contexto' in e or 'Limite' in e for e in errors): categories.append('limite de contexto/chamadas')
        if any('conexão' in e or 'HTTP' in e or 'Runner' in e for e in errors) or 'Runner indisponível' in task['acceptance'].get('output', ''): categories.append('infraestrutura')
        if not task['success'] and not categories: categories.append('implementação/verificação')
        failures.append({'id':task['id'], 'success':task['success'], 'state':task['state'], 'categories':categories, 'errors':errors, 'iterations':task['iterations'], 'llm_calls':task['llm_calls']})
    rows.append({'run':folder.name, 'metrics':result['metrics'], 'tasks':failures})
(base/'summary.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2)+'\n')
lines = ['# Resultados das execuções Qwen', '', 'Todas as execuções planejadas são reportadas. Falhas permanecem no denominador. As categorias também registram ocorrências recuperadas durante tarefas bem-sucedidas.', '', '| Execução | Tarefas | TaskSuccessRate | FirstAttemptSuccess | AverageIterations | AverageLLMCalls |', '|---|---:|---:|---:|---:|---:|']
for row in rows:
    m=row['metrics']; lines.append(f"| {row['run']} | {m['total_tasks']} | {m['TaskSuccessRate']:.2%} | {m['FirstAttemptSuccess']:.2%} | {m['AverageIterations']:.2f} | {m['AverageLLMCalls']:.2f} |")
for row in rows:
    lines += ['', f"## {row['run']}", '']
    for task in row['tasks']:
        lines.append(f"- {task['id']}: {task['state']}; sucesso independente={task['success']}; {', '.join(task['categories']) or 'sucesso'}; {'; '.join(task['errors']) or 'sem erro fatal registrado'}.")
lines += ['', 'A rejeição de uma especificação indica falha de estrutura exigida pelo harness; o rastro atual não salva a resposta bruta rejeitada, portanto não permite atribuir a causa exata ao conteúdo do modelo. Zero iterações significa falha antes da implementação, não solução na primeira tentativa.', '', 'Não houve ajuste entre repetições. Os resultados são do conjunto de desenvolvimento; a reserva heldout não foi executada.']
(base.parent/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps([{'run':r['run'], **r['metrics']} for r in rows], ensure_ascii=False))
