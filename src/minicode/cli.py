"""CLI: configuração confiável do runner fora das ações escolhidas pela LLM."""
import argparse
import json
from pathlib import Path
import sys

from .agent import Agent
from .evaluator import evaluate
from .llm import ModelError, QwenClient
from .tasks import TASKS, TaskAcceptance, contract_issues, prompts
from .tools import TestRunner, ToolError
from .workspace import copy_filtered
from .tool_selector import OpenAICompatibleToolSelector


def main(argv=None):
    parser = argparse.ArgumentParser(description='MiniCode — agente de programação')
    parser.add_argument('--project',default='.',help='Diretório do projeto alvo')
    parser.add_argument('--source',default='softwareteste',help='Projeto-base das seis tarefas')
    parser.add_argument('--task',help='Solicitação; omitida = entrada interativa')
    parser.add_argument('--task-id',choices=[task.id for task in TASKS],help='Enunciado e aceitação independentes de softwareteste')
    parser.add_argument('--env-file',help='Arquivo de configuração do endpoint')
    parser.add_argument('--tool-selector-env-file', help='Configuração de endpoint local/Colab do seletor LoRA; mantém Qwen para as demais funções')
    parser.add_argument('--tool-selector-without-context', action='store_true',
                        help='Ablação: omitir specification e plan da entrada do seletor')
    parser.add_argument('--allow-local-tests',action='store_true',help='Executar Python confiável no host, sem sandbox')
    parser.add_argument('--test-profile',choices=['unittest','pytest'],default='unittest')
    parser.add_argument('--test-python',help='Interpretador preparado para os testes locais')
    parser.add_argument('--test-image',default='minicode-tests:parte1',help='Imagem Docker previamente preparada')
    parser.add_argument('--acceptance-tests',help='Diretório confiável de aceitação fora do projeto')
    parser.add_argument('--max-iterations',type=int,default=3)
    parser.add_argument('--max-actions',type=int,default=20)
    parser.add_argument('--max-llm-calls',type=int,default=80)
    parser.add_argument('--timeout',type=int,default=30)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--evaluate',metavar='OUTPUT',help='Avaliar as seis tarefas em cópias independentes')
    modes.add_argument('--list-tasks',action='store_true')
    modes.add_argument('--prepare-task',choices=[task.id for task in TASKS],help='Copiar --source para --project novo')
    args = parser.parse_args(argv)
    mode = 'local' if args.allow_local_tests else 'docker'
    try:
        if min(args.max_iterations,args.max_actions,args.max_llm_calls,args.timeout) < 1:
            raise ValueError('Limites devem ser positivos')
        if args.task_id and args.task:
            raise ValueError('--task-id usa o enunciado fixo; não combine com --task')
        if args.list_tasks:
            print(json.dumps([{'id':task.id,'kind':task.kind} for task in TASKS],indent=2,ensure_ascii=False))
            return 0
        if args.prepare_task:
            instructions = prompts(args.source)
            copy_filtered(args.source,args.project)
            print(instructions[args.prepare_task])
            return 0
        if args.tool_selector_without_context and not args.tool_selector_env_file:
            raise ValueError('--tool-selector-without-context exige --tool-selector-env-file')
        progress = lambda message: print('→ '+message,flush=True)
        if args.evaluate:
            result = evaluate(lambda:QwenClient(args.env_file),args.evaluate,mode,args.max_iterations,
                              args.max_actions,args.max_llm_calls,args.timeout,args.source,args.test_python,
                              args.test_image,progress,
                              (lambda: OpenAICompatibleToolSelector(
                                  QwenClient(args.tool_selector_env_file),
                                  include_context=not args.tool_selector_without_context))
                              if args.tool_selector_env_file else None,
                              tool_selector_context=not args.tool_selector_without_context)
            print(json.dumps(result['metrics'],indent=2))
            return 0 if result['complete'] else 1
        acceptance = None
        editable_paths = None
        required_paths = None
        preflight = None
        if args.task_id:
            task = next(task for task in TASKS if task.id == args.task_id)
            source = Path(args.source).resolve()
            target = Path(args.project).resolve()
            if source == target or source.is_relative_to(target) or target.is_relative_to(source):
                raise ValueError('Prepare a tarefa em uma cópia fora do projeto-base')
            instruction = prompts(source)[task.id]
            acceptance = TaskAcceptance(task,source,mode,args.timeout,args.test_python,args.test_image)
            editable_paths = set(task.editable) | {'tests/' + task.test_file}
            required_paths = set(task.required) | {'tests/' + task.test_file}
            preflight = lambda root, task_id=task.id: contract_issues(task_id, root)
            profile = 'pytest'
        else:
            if not args.acceptance_tests:
                raise ValueError('Informe --task-id ou --acceptance-tests: DONE exige critérios independentes fornecidos pelo avaliador')
            instruction = args.task or input('MiniCode > ')
            profile = args.test_profile
        runner = TestRunner(args.project,mode,args.timeout,profile,args.test_python,args.test_image,args.acceptance_tests)
        selector = (OpenAICompatibleToolSelector(
            QwenClient(args.tool_selector_env_file),
            include_context=not args.tool_selector_without_context)
            if args.tool_selector_env_file else None)
        agent = Agent(args.project,QwenClient(args.env_file),runner,max_iterations=args.max_iterations,
                      max_actions=args.max_actions,max_llm_calls=args.max_llm_calls,progress=progress,
                      acceptance=acceptance,editable_paths=editable_paths,required_paths=required_paths,
                      preflight=preflight, tool_selector=selector)
        result = agent.run(instruction)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0 if result['state'] == 'DONE' else 1
    except (ModelError,ToolError,OSError,ValueError,EOFError) as exc:
        print(f'MiniCode: {exc}',file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('MiniCode: interrompido pelo usuário',file=sys.stderr)
        return 130
