# MiniCode — Parte 1

Agente de programação em Python, com cliente para Qwen via endpoint compatível com Chat Completions. A LLM produz especificação, plano e propostas de ferramentas; o harness controla os estados, executa a verificação e decide o resultado.

## Instalar

Requer Python 3.11+ e Linux para o runner de processos. Na raiz:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m minicode --help
python -m minicode --list-tasks
```

O extra `test` instala Flask e pytest para verificação local e testes do próprio MiniCode. O agente não instala dependências por conta própria.

Configure `.env` com as chaves descritas em `.env.example`:

```dotenv
MINICODE_BASE_URL=https://seu-servidor.example/v1
MINICODE_MODEL=identificador-exato-do-qwen-14b
MINICODE_API_KEY=sua-chave
```

A URL é ilustrativa. O cliente acrescenta `/chat/completions`. Variáveis exportadas têm precedência sobre `.env`; `--env-file` seleciona outro arquivo. A chave nunca é encaminhada no ambiente do runner.

## Preparar o Docker

```bash
docker build -t minicode-tests:parte1 sandbox
```

A imagem inclui as versões de Flask e pytest registradas em `sandbox/requirements.lock`. As execuções usam rede desativada, raiz e snapshot somente para leitura, usuário do host, limites de recursos e diretório temporário. O projeto original não é montado: uma cópia filtrada exclui `.env`, `.git`, `.minicode`, venvs e nomes conhecidos de segredos.

O daemon Docker deve estar acessível ao usuário. Falta de imagem ou de acesso ao daemon causa falha de verificação; não existe fallback automático para execução no host. A tag da imagem base ainda pode variar: registre o ID/digest da imagem usada em cada experimento.

## Executar uma tarefa de softwareteste

Use uma pasta nova fora do projeto-base:

```bash
python -m minicode --prepare-task discount --project /tmp/minicode-discount
python -m minicode --project /tmp/minicode-discount --task-id discount
```

IDs disponíveis:

| ID | Atividade |
| --- | --- |
| `discount` | Implementação do desconto |
| `tax` | Correção do imposto |
| `pagination` | Paginação de GET /products |
| `tests` | Testes de frete, pontos e cupons |
| `users` | Validação de POST /users |
| `refactor` | Refatoração do relatório |

Os enunciados são lidos de `softwareteste/TASKS.md`. A aceitação fica no pacote do avaliador, fora do workspace apresentado às ferramentas. As tarefas exigem novos testes e preservação dos arquivos protegidos. A tarefa `tests` exige também detectar quatro mutantes; a refatoração verifica resultados e extração de função auxiliar usada pelos dois canais.

Para outro projeto, forneça testes de aceitação preparados pelo avaliador em um diretório externo e separado do projeto:

```bash
python -m minicode --project /caminho/projeto \
  --task 'Implemente a funcionalidade descrita' \
  --test-profile pytest --acceptance-tests /caminho/aceitacao
```

Os perfis são `unittest` e `pytest`. `--task-id` e `--evaluate` selecionam pytest automaticamente. Nenhum desses parâmetros pode ser escolhido ou modificado pela LLM.

Execução local é uma opção explícita para código confiável:

```bash
python -m minicode --project /tmp/minicode-discount --task-id discount \
  --allow-local-tests --test-python "$PWD/softwareteste/.venv/bin/python"
```

Esse interpretador deve ter as dependências instaladas. O modo local usa snapshot e valida integridade, mas **não é um sandbox de sistema operacional**: código hostil ainda pode acessar o host. Use Docker para código não confiável.

## Condição de sucesso

O fluxo permitido é:

```text
RECEIVED → SPECIFIED → PLANNED → IMPLEMENTING → VERIFYING → DONE
                                    ↑              |
                                    └── REPAIRING ←┘
```

Falhas ou esgotamento de limites levam a `FAILED`. `DONE` exige:

1. Especificação e plano validados antes das escritas.
2. Relatório estruturado completo do launcher, execução terminada corretamente e testes efetivamente executados.
3. Aprovação dos testes do projeto e da aceitação independente configurada.
4. Integridade dos arquivos protegidos e digest da mesma revisão que foi verificada.

Imprimir `Ran 1 test ... OK` não aprova a execução. `unittest.py`, `pytest.py` e outros nomes reservados na raiz são rejeitados. O interpretador inicia com `-I`; o framework é carregado antes de adicionar o projeto ao caminho de importação.

Estas medidas resistem aos desvios demonstrados no review. Não são uma prova de segurança contra toda forma de sabotagem por Python arbitrário: testes e código importado ainda compartilham o interpretador dentro do container. O relatório não é uma atestação criptográfica, os testes independentes têm cobertura finita e o modo local depende de confiança. Consulte [arquitetura.md](arquitetura.md) para o limite de confiança.

## Limites e rastreabilidade

| Opção | Padrão |
| --- | ---: |
| `--max-iterations` | 3 tentativas, incluindo a primeira |
| `--max-actions` | 20 ações por tentativa |
| `--max-llm-calls` | 80 chamadas, incluindo retries de JSON |
| `--timeout` | 30 segundos por execução de testes |

O timeout HTTP é de 90 segundos por chamada. O orçamento de contexto é de 48.000 caracteres. Limites não positivos são rejeitados.

Cada execução salva em `<projeto>/.minicode/<id>/`:

- `specification.md` e `plan.md`, após validação de cada etapa;
- `actions.jsonl`, com ações, transições, erros e resultados;
- `state.json`, atualizado por substituição atômica;
- `tests-N.log`, com saída da verificação da tentativa.

O runner conserva a saída até o orçamento de 1 MB; ultrapassá-lo reprova a execução. O feedback preserva início e final do log e indica truncamento. A ferramenta `read_test_output(offset)` permite paginar o restante, sem abrir acesso genérico à pasta de rastros. Erros de protocolo do cliente são convertidos em falhas e exceções inesperadas são registradas como `FAILED`. Interrupções encerram o grupo de processos e removem o container.

## Avaliar a bateria completa

```bash
python -m minicode --evaluate /tmp/minicode-avaliacao-01
```

O destino deve ser novo. Cada tarefa recebe uma cópia isolada da mesma versão inicial. Os resultados são salvos em `results.json`, com versão da suíte, configuração, digest inicial, modelo quando disponível, métricas, tempo, estado e aceitação por tarefa. Os snapshots e registros ficam em subpastas por ID.

| Métrica | Definição |
| --- | --- |
| TaskSuccessRate | Tarefas corretas / todas as tarefas planejadas |
| FirstAttemptSuccess | Tarefas corretas com uma tentativa / todas as tarefas planejadas |
| AverageIterations | Soma das tentativas / todas as tarefas planejadas |
| AverageLLMCalls | Soma das chamadas / todas as tarefas planejadas |

As seis tarefas entram no denominador desde o primeiro checkpoint. Falha de inicialização de uma tarefa não exclui a tarefa nem impede as seguintes. Interrupções deixam `complete: false`. Um código de saída zero de `--evaluate` significa que a bateria terminou e foi registrada; consulte TaskSuccessRate para saber quantas tarefas foram resolvidas. O modo de tarefa individual retorna zero apenas com `DONE`.

## Testes de regressão

```bash
python -m unittest discover -s tests -v
MINICODE_DOCKER_TESTS=1 python -m unittest discover -s tests -p test_docker.py -v
```

Os testes do avaliador usam soluções de referência somente em pastas temporárias. Um resultado perfeito nesses testes valida o harness, não mede a qualidade do Qwen. Os defeitos de `softwareteste` permanecem intactos. Não há chamadas reais ao endpoint na suíte automatizada.

A suíte cobre os oito problemas do review: imports removidos, falsificação por stdout/sombreamento, aliases de caminhos, snapshots sem segredos, pytest, saída longa, falhas de protocolo/interrupções e denominador preservado.
