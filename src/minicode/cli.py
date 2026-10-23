import argparse
import json
from pathlib import Path
import sys

from .agent import Agent
from .benchmark import CASES, test_source
from .demo import DemoClient
from .evaluator import evaluate
from .llm import ModelError, QwenClient
from .tools import TestRunner, ToolError


def main(argv=None):
    parser = argparse.ArgumentParser(description="MiniCode — agente de programação v1")
    parser.add_argument("--project", default=".", help="Diretório do projeto alvo")
    parser.add_argument("--task", help="Solicitação; omitida = entrada interativa")
    parser.add_argument("--allow-local-tests", action="store_true", help="Executar código do projeto no host (somente projetos confiáveis)")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--max-actions", type=int, default=20)
    parser.add_argument("--max-llm-calls", type=int, default=80)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--demo", action="store_true", help="Criar demo offline em --project (diretório novo)")
    parser.add_argument("--evaluate", metavar="OUTPUT", help="Executar seis tarefas com Qwen e salvar resultados em diretório novo")
    args = parser.parse_args(argv)
    mode = "local" if args.allow_local_tests else "docker"
    try:
        if args.evaluate:
            result = evaluate(QwenClient, args.evaluate, mode, args.max_iterations,
                              args.max_actions, args.max_llm_calls, args.timeout)
            print(json.dumps(result["metrics"], indent=2))
            return 0
        if args.demo:
            root = Path(args.project)
            root.mkdir(parents=True, exist_ok=False)
            (root / "tests").mkdir()
            (root / "solution.py").write_text(CASES[0]["source"])
            (root / "tests" / "test_factorial.py").write_text(test_source(CASES[0]["checks"]))
            client, task = DemoClient(), CASES[0]["task"]
        else:
            client, task = QwenClient(), args.task or input("MiniCode > ")
        agent = Agent(args.project, client, TestRunner(args.project, mode, args.timeout),
                      max_iterations=args.max_iterations, max_actions=args.max_actions,
                      max_llm_calls=args.max_llm_calls, progress=lambda text: print("→ " + text, flush=True))
        result = agent.run(task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["state"] == "DONE" else 1
    except (ModelError, ToolError, OSError, ValueError, EOFError) as exc:
        print(f"MiniCode: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("MiniCode: interrompido pelo usuário", file=sys.stderr)
        return 130
