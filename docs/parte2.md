# Parte 2 — especialização para seleção de ferramentas

## Pergunta e hipótese

**Pergunta:** um modelo aberto pequeno especializado em escolher a próxima ferramenta melhora essa escolha, e isso muda o sucesso do agente?  A hipótese pré-registrada é: *LoRA/QLoRA no mesmo modelo pequeno aumenta a acurácia top-1 no split de teste por família de tarefa, em comparação com seu checkpoint base.*

Escolhemos `tool selection` porque a Parte 1 já separa LLM e ferramentas e preserva um rastro de ações. O resultado histórico registrado em `avaliacoes_historico/parte1/results.json` é 3/6; em `pagination` a aceitação independente passou, mas a execução terminou em `FAILED`, evidenciando um ponto de coordenação/seleção a investigar. Isso **não prova causalidade** e não é usado como resultado da Parte 2.

## Dados e prevenção de vazamento

`data/tool_selection/examples.jsonl` é um seed dataset curado a partir dos contratos das seis tarefas públicas da Parte 1. Cada exemplo contém estado, tarefa, spec, plano, feedback limitado e rótulo da próxima ferramenta — nunca argumentos executáveis ou segredos. São 24 exemplos: 16 treino (`discount`, `tax`, `tests`, `users`), 4 validação (`refactor`) e 4 teste (`pagination`). A unidade de split é `task_family`, portanto uma família não pode aparecer em dois splits. O validador falha em IDs duplicados, esquema incompleto, rótulos fora da allowlist, split vazio ou vazamento de família.

Regenerar o seed (apenas se revisar a curadoria):

```bash
python3 scripts/build_tool_selection_dataset.py
python3 scripts/validate_tool_selection_dataset.py data/tool_selection/examples.jsonl
```

Antes do treinamento real, ampliar os dados com exemplos adicionais, registrar a origem/revisor de cada um e congelar `test` antes de ajustar hiperparâmetros. Não usar o endpoint do professor como teacher sem registrar prompt, versão, filtragem humana e licença; esse repositório não contém chamadas nem credenciais de teacher.

## Treinamento e avaliação

O notebook [train_tool_selector_colab.ipynb](../notebooks/train_tool_selector_colab.ipynb) usa `Qwen/Qwen2.5-0.5B-Instruct` com QLoRA quando a GPU permite `bitsandbytes` e cai para LoRA fp16/bf16 quando não permite. LoRA mantém o peso base congelado e aprende \(W'=W+BA\), em que `A` e `B` têm posto `r` pequeno; assim há muito menos parâmetros treináveis que em fine-tuning completo. O notebook valida o dataset, tokeniza, treina, registra losses de treino/validação, plota as curvas e exporta predições separadas para o teste.

A comparação obrigatória é **o mesmo checkpoint** base versus base+adapter, com mesmo prompt e split test. Para pontuar uma execução já exportada:

```bash
python3 scripts/evaluate_tool_selection.py --predictions artifacts/base_test_predictions.jsonl --output artifacts/base_test_report.json
python3 scripts/evaluate_tool_selection.py --predictions artifacts/lora_test_predictions.jsonl --output artifacts/lora_test_report.json
```

Os artefatos `artifacts/` são ignorados; nenhuma métrica foi preenchida ou inferida neste repositório. O endpoint Qwen-14B é referência opcional, avaliada com o mesmo protocolo e anotada como referência, não como baseline do fine-tuning.

## Integração segura e end-to-end

Após servir o adapter no Colab (ou localmente) atrás de endpoint Chat Completions, crie um arquivo de ambiente separado com `MINICODE_BASE_URL`, `MINICODE_MODEL` e `MINICODE_API_KEY`; não o versione. Então passe `--tool-selector-env-file caminho.env` ao MiniCode. O Qwen principal continua gerando os argumentos; o seletor retorna somente um nome de ferramenta pertencente a uma allowlist. `Agent.call_tool`, a máquina de estados, paths protegidos, acceptance e gates de `DONE` continuam sendo a autoridade. Resposta inválida, ferramenta fora da allowlist ou divergência são recusadas e auditadas.

Avalie end-to-end numa cópia nova por tarefa e reporte TaskSuccessRate, FirstAttemptSuccess, AverageIterations e AverageLLMCalls para: (1) Qwen sem seletor e (2) Qwen com selector LoRA. Fixe a mesma suíte/commit, limites, temperatura e endpoint. Ainda falta executar isso em infraestrutura disponível.

## Ablação

Ablação definida: seletor recebe **com spec+plano** versus **sem spec+plano**, mantendo modelo, split, prompt e orçamento. Avaliar primeiro acurácia local e depois TaskSuccessRate end-to-end. Isso testa se o contexto estruturado contribui; não remover os hard gates, pois isso mudaria o modelo de ameaça e não é uma ablação segura.

## Estado atual

Implementados e verificados localmente: esquema/validador de dataset, detector de vazamento, protocolo de score, integração estreita e testes de segurança. Pendente: executar notebook no Colab com GPU, exportar adapter/predições, servir endpoint, rodar base/LoRA/Qwen-14B e preencher tabela de resultados reais.
