"""Launcher controlado pelo harness. Executado por caminho absoluto com python -I.

O resultado é separado de stdout. Saída textual do projeto nunca decide sucesso.
Este processo executa Python do projeto: Docker é a fronteira de isolamento.
"""
import json
import os
from pathlib import Path
import sys
import traceback
import unittest  # carregado ANTES de incluir o projeto no caminho de imports


def main():
    root, profile, report_path, trusted_tests = sys.argv[1:]
    sys.argv = ["minicode-test-worker"]
    report_file = Path(report_path)
    dump = json.dumps
    write = report_file.write_text
    report = {"protocol": 1, "completed": False, "tests": 0, "discovered": 0,
              "failed": 0, "skipped": 0, "passed": False}
    code = 2
    try:
        if profile == "pytest":
            import pytest
        # Frameworks e stdlib têm precedência sobre nomes dentro do projeto.
        sys.path.append(root)
        os.chdir(root)
        test_dir = trusted_tests or str(Path(root) / "tests")
        if profile == "unittest":
            suite = unittest.TestLoader().discover(test_dir)
            outcome = unittest.TextTestRunner(verbosity=2).run(suite)
            skipped = len(outcome.skipped) + len(outcome.expectedFailures)
            report.update(tests=outcome.testsRun - skipped, discovered=outcome.testsRun,
                          skipped=skipped, failed=len(outcome.failures) + len(outcome.errors) + len(outcome.unexpectedSuccesses),
                          passed=outcome.wasSuccessful() and outcome.testsRun > skipped)
            code = 0 if report["passed"] else 1
        else:
            class Results:
                def __init__(self):
                    self.executed = set()
                    self.skipped = set()
                    self.failed = set()
                    self.collected = 0
                    self.collection_errors = 0

                def pytest_collection_finish(self, session):
                    self.collected = len(session.items)

                def pytest_collectreport(self, report):
                    if report.failed:
                        self.collection_errors += 1

                def pytest_runtest_logreport(self, report):
                    if report.failed:
                        self.failed.add(report.nodeid)
                    if report.skipped or hasattr(report, "wasxfail"):
                        self.skipped.add(report.nodeid)
                    elif report.when == "call":
                        self.executed.add(report.nodeid)

            results = Results()
            args = [test_dir, "-q", "-s", "--tb=short", "-p", "no:cacheprovider",
                    "--import-mode=importlib", "-c", str(Path(__file__).with_name("runner.ini")),
                    "--rootdir", root, "--confcutdir", test_dir]
            code = int(pytest.main(args, plugins=[results]))
            executed = len(results.executed - results.skipped)
            report.update(tests=executed, discovered=results.collected, skipped=len(results.skipped),
                          failed=len(results.failed) + results.collection_errors,
                          passed=code == 0 and executed > 0 and not results.failed and not results.collection_errors)
        report["completed"] = True
    except BaseException:
        traceback.print_exc()
    # os._exit durante coleta/testes não chega aqui: relatório ausente => falha.
    write(dump(report), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
