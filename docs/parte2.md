# Parte 2 — especialização para seleção de ferramentas

## Pergunta e hipótese

**Pergunta:** um modelo aberto pequeno especializado em escolher a próxima ferramenta melhora essa escolha, e isso muda o sucesso do agente?  A hipótese pré-registrada é: *LoRA/QLoRA no mesmo modelo pequeno aumenta a acurácia top-1 no split de teste por família de tarefa, em comparação com seu checkpoint base.*

Escolhemos `tool selection` porque a Parte 1 já separa LLM e ferramentas e preserva um rastro de ações. O resultado histórico registrado em `avaliacoes_historico/parte1/results.json` é 3/6; em `pagination` a aceitação independente passou, mas a execução terminou em `FAILED`, evidenciando um ponto de coordenação/seleção a investigar. Isso **não prova causalidade** e não é usado como resultado da Parte 2.

## Dados e prevenção de vazamento

`data/tool_selection/examples.jsonl` é o dataset curado v2. Cada exemplo contém estado, tarefa, spec, plano, feedback limitado e rótulo da próxima ferramenta — nunca argumentos executáveis ou segredos. São 96 exemplos em 12 famílias: 64 de treino, 16 de validação e 16 de teste. A unidade de split é `task_family`, portanto uma família não pode aparecer em dois splits. As famílias finais `retry_timeout` e `audit_logging` não correspondem às seis tarefas públicas da Parte 1. Origem, limitações e SHA-256 estão registrados em `data/tool_selection/DATASET_CARD.md`.

Regenerar o seed (apenas se revisar a curadoria):

```bash
python3 scripts/build_tool_selection_dataset.py
python3 scripts/validate_tool_selection_dataset.py data/tool_selection/examples.jsonl
```

O teste v2 está congelado: não deve orientar prompts, hiperparâmetros ou nova curadoria. Se isso ocorrer, será necessário criar uma nova versão com outras famílias. Não usar o endpoint do professor como teacher sem registrar prompt, versão, filtragem humana e licença; este dataset não contém chamadas nem credenciais de teacher.

## Treinamento e avaliação

O notebook [train_tool_selector_colab.ipynb](../notebooks/train_tool_selector_colab.ipynb) usa `Qwen/Qwen2.5-0.5B-Instruct` com QLoRA 4-bit. LoRA mantém o peso base congelado e aprende \(W'=W+BA\), em que `A` e `B` têm posto `r` pequeno; assim há muito menos parâmetros treináveis que em fine-tuning completo. O notebook usa o protocolo canônico de `selector_protocol.py`, fixa seeds, valida o dataset, treina, registra losses, salva a curva e exporta três condições na mesma execução: base, LoRA e LoRA sem spec+plano.

A comparação obrigatória é **o mesmo checkpoint** base versus base+adapter, com mesmo prompt e split test. Para pontuar uma execução já exportada:

```bash
python3 scripts/evaluate_tool_selection.py --predictions artifacts/base_test_predictions.jsonl --output artifacts/base_test_report.json
python3 scripts/evaluate_tool_selection.py --predictions artifacts/lora_test_predictions.jsonl --output artifacts/lora_test_report.json
```

O primeiro treinamento real, feito no seed v1 em Tesla T4, foi preservado em `experiments/tool_selection/2026-11-22-seed-v1/`: loss de validação final 2,176619, mas acurácia LoRA 0/4 e quatro saídas inválidas. Ele não possui baseline e usou um protocolo antigo; portanto é evidência histórica negativa, não o resultado final. O endpoint Qwen-14B é referência opcional, anotada como referência e não como baseline do fine-tuning.

## Integração segura e end-to-end

Após servir o adapter no Colab (ou localmente) atrás de endpoint Chat Completions, crie um arquivo de ambiente separado com `MINICODE_BASE_URL`, `MINICODE_MODEL` e `MINICODE_API_KEY`; não o versione. Então passe `--tool-selector-env-file caminho.env` ao MiniCode. O prompt e o parser de produção são os mesmos usados pelo notebook: a única saída aceita é o nome exato de uma ferramenta da allowlist. O Qwen principal continua gerando argumentos; `Agent.call_tool`, máquina de estados, paths protegidos, aceitação e gates de `DONE` continuam sendo a autoridade.

Avalie end-to-end numa cópia nova por tarefa e reporte TaskSuccessRate, FirstAttemptSuccess, AverageIterations e AverageLLMCalls para: (1) Qwen sem seletor, (2) Qwen com seletor LoRA e (3) ablação LoRA sem spec+plano. A terceira condição usa `--tool-selector-without-context` junto de `--tool-selector-env-file`. Fixe a mesma suíte/commit, limites, temperatura e endpoint. Ainda falta executar isso em infraestrutura disponível.

## Ablação

Ablação definida: LoRA **com spec+plano** versus o mesmo LoRA **sem spec+plano**, mantendo modelo, split, decodificação e orçamento. O notebook produz ambas as predições locais. Depois, as duas condições devem ser repetidas end-to-end. Não remover os hard gates, pois isso mudaria o modelo de ameaça e não seria uma ablação segura.

## Estado atual

Implementados: dataset v2 e card, detector de vazamento, protocolo único treino/produção, score independente do diretório atual, notebook base×LoRA×ablação, carregamento direto de adapter, executor end-to-end e testes de segurança. O novo notebook contém alvos supervisionados, loss somente na resposta e verificação das máscaras antes de treinar. O treinamento anterior da versão v2 construía somente prompts; essa falha foi corrigida antes de uma execução científica v2.

Executados em 22/11/2026: treinamento real v2 em Tesla T4, 40 passos/5 épocas, e avaliação base×LoRA×ablação. O ZIP entregue teve hashes conferidos: base 0/16, LoRA 12/16 (75%), sem spec/plano 13/16 (81,25%). Consulte `RESULTADOS_LOCAIS_V2.md` e `experiments/tool_selection/2026-11-22-v2-trained/`. O adapter está em `artifacts/colab-v2/adapter/`; não é necessário repetir o treino para retomar a integração.

A recarga local em CPU/float32 produziu 0/16, 8/16 e 9/16, respectivamente: é outra condição numérica e não reproduz os valores da T4/NF4. Os resultados brutos estão em `experiments/tool_selection/2026-11-22-v2-cpu/`. A comparação end-to-end permanece incompleta por timeouts da rota de geração Qwen, apesar de DNS/TCP/TLS responderem. Não há conclusão sobre ganho no agente. O smoke com modelo aleatório e a referência Qwen-14B (2/16) são evidências separadas.

## Procedimento de conclusão

As etapas 1–4 abaixo já foram cumpridas na execução entregue. Não retreinar para
retomar. Após a API responder, usar a etapa 5 com o ambiente existente e a nova
pasta `parte2-v2-e2e-02`; a pasta sem sufixo preserva a tentativa interrompida.

1. Execute a partir da raiz `python3 scripts/build_colab_bundle.py`. O ZIP contém código, notebook,
   dataset e manifesto de arquivos, sem .env nem pesos. Extraia `MiniCode-parte2` em
   `/content/drive/MyDrive/redesneurais/` e confira que o notebook importado é o do pacote novo.
2. Abra `notebooks/train_tool_selector_colab.ipynb` em uma sessão Colab limpa com GPU e execute
   todas as células. Dependências são instaladas com erro verificável; cada execução usa uma pasta
   nova, preservando as anteriores. Registre essa execução sem alterar o protocolo depois do teste.
3. O notebook resolve e fixa a revisão do modelo, registra hashes, ambiente, seed, losses,
   parâmetros treináveis, predições base/LoRA/ablação, relatórios e adapter. Ele usa `trainer.model`
   para garantir que a inferência recebe o PeftModel treinado. `small_results.zip` leva as métricas;
   a pasta `adapter` deve ser exportada separadamente com seus checksums.
4. Copie a pasta completa da execução escolhida para
   `/home/vitoria/Documentos/redesneurais/MiniCode/artifacts/colab-v2`. Ela deve conter
   `run_manifest.json`, `dataset.jsonl`, os relatórios/predições e `adapter/`.
5. Na raiz local, prepare o ambiente e execute as condições com Docker disponível:

```bash
python3 -m venv .venv-ml
.venv-ml/bin/python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
.venv-ml/bin/python -m pip install -r requirements-ml.txt
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 .venv-ml/bin/python scripts/run_part2_experiments.py --run-dir MiniCode/artifacts/colab-v2 --output MiniCode/experiments/results/parte2-v2-e2e-02 --device cpu
```

O carregador direto usa o mesmo template/parser do notebook e elimina a necessidade de túnel
público para o Colab. Em CPU ele recarrega o checkpoint base em float32 e aplica o adapter;
essa diferença em relação à inferência local 4-bit é registrada no manifesto. As duas condições
end-to-end com seletor usam a mesma precisão. Em máquina CUDA, `--device cuda --quantized` conserva
NF4. Não compare runs com precisões diferentes como se fossem a mesma configuração.

O executor verifica hashes do adapter, dataset e protocolo, fixa imagem Docker por ID no manifesto,
recusa destino existente e detecta alterações de código entre condições. `AverageLLMCalls` e o limite
global incluem chamadas ao Qwen e ao seletor; `AverageSelectorCalls` informa a parcela especializada.
Uma saída inválida do seletor causa falha auditada, sem fallback oculto.

6. Gere as tabelas a partir de arquivos verificados:

```bash
cd /home/vitoria/Documentos/redesneurais/MiniCode
.venv/bin/python scripts/summarize_part2_results.py --run-dir MiniCode/artifacts/colab-v2 --end-to-end MiniCode/experiments/results/parte2-v2-e2e-02 --output MiniCode/docs/RESULTADOS_EXECUCAO_V2.md
```

7. Revise as oito respostas em `RESULTADOS_PARTE2.md'.

## Verificação de engenharia

```bash
.venv/bin/python -m unittest discover -s tests -v
MINICODE_DOCKER_TESTS=1 .venv/bin/python -m unittest discover -s tests -p test_docker.py -v
.venv-ml/bin/python scripts/smoke_selector_training.py
```

O smoke test usa somente quatro exemplos de treino e um modelo aleatório criado localmente;
não acessa teste, não baixa um checkpoint e não mede desempenho científico. Ele valida a perda
supervisionada, três caminhos de inferência, salvamento, recarga e cliente do seletor.

Referências de API verificadas: [TRL 0.26.2](https://huggingface.co/docs/trl/v0.26.2/en/sft_trainer)
e [PEFT 0.18](https://huggingface.co/docs/peft/v0.18.0/en/developer_guides/quantization).
