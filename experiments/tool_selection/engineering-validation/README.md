# Validação de engenharia

`smoke.json` foi produzido executando `scripts/smoke_selector_training.py` em CPU com torch 2.5.1,
transformers 4.57.3, TRL 0.26.2 e PEFT 0.18.0. O modelo tem pesos aleatórios e tamanho reduzido.
Foi usado somente o início do split de treino; não é avaliação do Qwen2.5-0.5B nem do teste v2.

O smoke valida dois passos reais de otimização LoRA, supervisão da resposta, inferência nas três
condições e equivalência após salvar/recarregar o adapter, inclusive pelo cliente integrado.

Em 22/11/2026, `MINICODE_DOCKER_TESTS=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q`
concluiu 105 testes em 23,939 segundos, com `OK`, sem skips. Os testes do executor usam clientes
simulados; quaisquer métricas de fixtures impressas durante a suíte não são resultados experimentais.
