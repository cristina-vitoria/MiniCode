# Protocolo da avaliação v1

As execuções reais do Qwen são registradas em `results/`, com síntese em `REPORT.md`. A demo offline valida o harness, não a qualidade do modelo.

1. Registre commit do MiniCode, identificador exato do modelo, data, limites, modo do runner, Python e digest da imagem Docker.
2. Execute os seis casos com `minicode --evaluate experiments/results/qwen-01`.
3. Preserve `results.json`, código e rastros por tarefa. Revise os arquivos para remover informações privadas antes de compartilhar.
4. Repita em diretórios novos, mantendo configuração e tarefas constantes. Reporte cada execução; não selecione apenas as melhores.
5. Separe tarefas inéditas para avaliar generalização. Os seis exemplos publicados são dados de desenvolvimento.
6. Inspecione falhas: erro de formato, ferramenta recusada, implementação incorreta, limite de contexto/chamadas ou problema de infraestrutura. Uma falha operacional não deve ser descartada silenciosamente do denominador.

`FirstAttemptSuccess` é uma proporção sobre todas as tarefas. `AverageIterations` inclui a primeira tentativa e falhas; uma falha antes da implementação conta como zero iterações. `AverageLLMCalls` inclui retries de JSON. `TaskSuccessRate` exige tanto DONE quanto aprovação independente. A criação de testes inclui teste de mutação com quatro defeitos conhecidos.

Os oráculos não garantem correção universal: são amostras de entradas. Um resultado perfeito nesses seis casos não é evidência de desempenho em tarefas inéditas ou outras linguagens. Nenhum fine-tuning ou ablação da Parte 2 está incluído.

## Execução reproduzível

`../.venv/bin/python run_protocol.py` (a partir desta pasta) executa duas repetições, `qwen-01` e `qwen-02`, com os defaults fixos do CLI. Requer endpoint configurado no `.env` da raiz, Docker acessível e imagem `python:3.12-slim` já disponível. Não sobrescreve execuções existentes. Para uma nova série, altere explicitamente os identificadores de saída e registre essa mudança.

Cada repetição possui metadados, console e revisão de privacidade ao lado da pasta dos resultados. Os metadados registram commit, árvore de trabalho, hashes das fontes, modelo, data com fuso, limites, Python do host e do contêiner, ID e digest da imagem. A tag Docker não é fixada por digest pelo runner atual: o digest registrado identifica a imagem inspecionada; não altere a imagem durante a série.

Execute `../.venv/bin/python summarize.py` para reconstruir `REPORT.md` e `results/summary.json`. O protocolo remove valores exatos da chave, endpoint e caminho pessoal dos artefatos; é necessária revisão adicional antes de publicação. `results/` continua ignorado pelo Git; preservar localmente não equivale a publicar.

As propostas de generalização estão em `heldout/`. Ainda exigem projetos iniciais e oráculos congelados antes de avaliação. Não foram usadas para ajustar o agente.
