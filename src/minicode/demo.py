"""Fixture roteirizada para testar o harness; não mede capacidade de uma LLM."""
import json


class DemoClient:
    def __init__(self):
        self.responses = iter([
            {"objective": "Calcular o fatorial", "acceptance_criteria": ["factorial(0) == 1", "factorial(5) == 120", "Negativos geram ValueError"]},
            {"steps": ["Ler a função", "Implementar fatorial", "Executar os testes e reparar"], "test_strategy": "Testes unittest de 0, 5 e negativo"},
            {"tool": "read_file", "args": {"path": "solution.py"}},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n):\n    return n\n"}},
            {"tool": "run_tests", "args": {}},
            {"tool": "write_file", "args": {"path": "solution.py", "content": "def factorial(n):\n    if n < 0:\n        raise ValueError('negative')\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n"}},
            {"tool": "run_tests", "args": {}},
        ])

    def complete(self, messages):
        return json.dumps(next(self.responses))
