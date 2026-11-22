#!/usr/bin/env python3
"""Build the reviewed v2 tool-selection dataset.

The split unit is a scenario family. Test families are deliberately unrelated
to the six public Parte 1 tasks and must not be used for prompt or hyperparameter
selection after this version is frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "tool_selection" / "examples.jsonl"

SCENARIOS = [
    ("factorial", "train", "Implemente factorial com validação de negativos.", "Implementar fatorial seguro", "solution.py", "replace_python_function"),
    ("health_route", "train", "Adicione GET /health retornando status ok.", "Adicionar rota de saúde", "app/routes.py", "write_file"),
    ("tax_rounding", "train", "Corrija o arredondamento do imposto em centavos.", "Corrigir cálculo tributário", "app/tax.py", "replace_text"),
    ("user_validation", "train", "Valide nome, e-mail e idade antes de persistir.", "Validar cadastro de usuário", "app/users.py", "replace_python_function"),
    ("pagination", "train", "Adicione page e page_size ao endpoint de produtos.", "Paginar produtos", "app/controllers.py", "replace_python_function"),
    ("report_refactor", "train", "Extraia a soma de itens sem alterar a saída.", "Refatorar relatório", "app/report.py", "replace_python_function"),
    ("service_tests", "train", "Crie testes de regressão para regras de frete.", "Cobrir serviço de frete", "tests/test_shipping.py", "write_file"),
    ("config_search", "train", "Localize e corrija o timeout padrão da aplicação.", "Corrigir timeout", "app/config.py", "replace_text"),
    ("cache_invalidation", "validation", "Corrija a invalidação de cache após atualização.", "Invalidar cache corretamente", "app/cache.py", "replace_python_function"),
    ("csv_export", "validation", "Adicione exportação CSV preservando a ordem das colunas.", "Exportar relatório CSV", "app/export.py", "write_file"),
    ("retry_timeout", "test", "Interrompa retries quando o orçamento de tempo expirar.", "Limitar retentativas", "app/retry.py", "replace_python_function"),
    ("audit_logging", "test", "Registre alterações aceitas sem gravar dados sensíveis.", "Adicionar auditoria segura", "app/audit.py", "write_file"),
]


def trajectory(task: str, objective: str, target: str, edit_tool: str):
    plan = {
        "steps": [
            f"localizar a implementação relacionada a {target}",
            "ler produção e testes existentes",
            "aplicar a menor mudança compatível com o contrato",
            "adicionar ou ajustar testes",
            "executar a verificação e reparar falhas",
        ],
        "test_strategy": "executar a suíte existente e os critérios de aceitação independentes",
    }
    specification = {
        "objective": objective,
        "acceptance_criteria": [
            "o comportamento solicitado é observável por teste",
            "testes e APIs existentes permanecem preservados",
        ],
    }
    return specification, plan, [
        ("list_files", "Início da implementação; ainda não há inventário do projeto."),
        ("search_code", f"Inventário disponível; localizar referências a {target}."),
        ("read_file", f"Busca encontrou {target}; conteúdo ainda não foi inspecionado."),
        ("read_file", "Produção lida; é necessário inspecionar os testes existentes."),
        (edit_tool, f"Produção e testes lidos; aplicar a mudança em {target}."),
        ("write_file", "Mudança de produção aplicada; falta criar o teste novo planejado."),
        ("run_tests", "Produção e teste foram alterados; executar a verificação."),
        ("read_test_output", "A verificação falhou e o trecho exibido não contém a causa completa."),
    ]


def main():
    rows = []
    for family, split, task, objective, target, edit_tool in SCENARIOS:
        specification, plan, steps = trajectory(task, objective, target, edit_tool)
        for number, (label, feedback) in enumerate(steps, 1):
            rows.append({
                "id": f"{family}-{number}",
                "task_family": family,
                "split": split,
                "input": {
                    "state": "IMPLEMENTING",
                    "task": task,
                    "specification": specification,
                    "plan": plan,
                    "feedback": feedback,
                },
                "label": label,
                "provenance": "human_curated_scenario_v2",
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
