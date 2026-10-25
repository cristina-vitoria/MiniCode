"""Avaliação das seis tarefas com denominador fixo e checkpoints atômicos."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import tempfile
import time

from .agent import Agent
from .tasks import TASKS, VERSION, TaskAcceptance, prompts
from .tools import TestRunner
from .workspace import Workspace, copy_filtered


def metrics(rows):
    count = len(rows)
    return {'total_tasks':count,
            'TaskSuccessRate':sum(row['success'] for row in rows)/count if count else 0,
            'FirstAttemptSuccess':sum(row['success'] and row['iterations'] == 1 for row in rows)/count if count else 0,
            'AverageIterations':sum(row['iterations'] for row in rows)/count if count else 0,
            'AverageLLMCalls':sum(row['llm_calls'] for row in rows)/count if count else 0}


def evaluate(client_factory, output, mode='docker', max_iterations=3, max_actions=20,
             max_llm_calls=80, timeout=30, source='softwareteste', python=None,
             image='minicode-tests:parte1', progress=None):
    if min(max_iterations,max_actions,max_llm_calls,timeout) < 1 or mode not in {'docker','local'}:
        raise ValueError('Modo ou limites inválidos')
    source = Path(source).resolve(strict=True)
    instructions = prompts(source)
    output = Path(output).resolve()
    if output.is_relative_to(source):
        raise ValueError('Saída da avaliação deve ficar fora do projeto-base')
    output.mkdir(parents=True,exist_ok=False)
    rows = [{'id':task.id,'kind':task.kind,'state':'PENDING','success':False,'iterations':0,
             'llm_calls':0,'changed_files':[],'trace':None,'acceptance':None,'seconds':0.0} for task in TASKS]
    config = {'mode':mode,'profile':'pytest','max_iterations':max_iterations,'max_actions':max_actions,
              'max_llm_calls':max_llm_calls,'timeout':timeout,'image':image,'python':python or platform.python_version(),
              'source_digest':Workspace(source).digest(),'started_at':datetime.now(timezone.utc).isoformat()}
    finished = False

    def save():
        report = {'suite_version':VERSION,'configuration':config,'complete':finished,
                  'metrics':metrics(rows),'tasks':rows}
        temp = output/'results.tmp'
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(output/'results.json')
        return report

    save()
    with tempfile.TemporaryDirectory(prefix='minicode-evaluation-') as temporary:
        baseline = Path(temporary)/'baseline'
        copy_filtered(source,baseline)
        for task,row in zip(TASKS,rows):
            start = time.monotonic()
            agent = None
            root = Path(temporary)/task.id
            try:
                copy_filtered(baseline,root)
                client = client_factory()
                if getattr(client,'model',None):
                    row['model'] = client.model
                runner = TestRunner(root,mode,timeout,profile='pytest',python=python,image=image)
                acceptance = TaskAcceptance(task,baseline,mode,timeout,python,image)
                agent = Agent(root,client,runner,max_iterations,max_actions,max_llm_calls,
                              progress=progress,acceptance=acceptance)
                row.update(agent.run(instructions[task.id]))
                row['acceptance'] = agent.last_test.get('acceptance') if agent.last_test else None
                row['success'] = bool(row['state'] == 'DONE' and row['acceptance']
                                      and row['acceptance'].get('verified') and row['acceptance']['passed'])
            except KeyboardInterrupt:
                row.update(state='FAILED',error='Execução interrompida',success=False)
                raise
            except Exception as exc:
                row.update(state='FAILED',error=f'{type(exc).__name__}: {exc}',success=False)
            finally:
                if agent:
                    row.update(iterations=agent.iterations,llm_calls=agent.llm_calls)
                try:
                    if root.exists():
                        copy_filtered(root,output/task.id)
                    if agent and agent.run_dir:
                        trace = output/task.id/'.minicode'/agent.run_dir.name
                        trace.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copytree(agent.run_dir,trace)
                        row['trace'] = str(trace)
                except (OSError,ValueError) as exc:
                    row.update(state='FAILED',success=False,snapshot_error=str(exc))
                row['seconds'] = time.monotonic()-start
                save()
    finished = True
    return save()
