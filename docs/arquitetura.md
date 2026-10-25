# Decisões de arquitetura — Parte 1

## Separação de responsabilidades

- `cli.py`: opções confiáveis, escolha de perfil, imagem, aceitação e cliente.
- `agent.py`: máquina de estados, limites, especificação, plano e repair loop.
- `contracts.py`: protocolos de cliente e runner e tipos de resultado.
- `workspace.py`: política comum de caminhos, proteção por hash e cópias filtradas.
- `tools.py`: processo/container, budgets, relatório, integridade e timeout.
- `_test_worker.py`: integração controlada com unittest ou pytest.
- `tasks.py` e `acceptance/`: contratos independentes de softwareteste e mutações.
- `evaluator.py`: cópias por tarefa, métricas e checkpoints.

## Agent Hardness

A LLM não recebe uma ferramenta para mudar estados, executar shell, escolher o runner ou alterar sua configuração. A transição para implementação exige especificação e plano. Escritas são recusadas fora de IMPLEMENTING. DONE exige aprovação independente, relatório verificado e digest atualizado; a autorização é produzida pelo fluxo de verificação, não por uma resposta textual do modelo.

As condições são programáticas, mas os critérios semânticos dependem da qualidade dos testes fornecidos pelo avaliador. Um teste superficial continua sendo evidência superficial.

## Identidade de arquivos e integridade

Caminhos são normalizados antes da comparação. `./tests/test_x.py` e `tests/test_x.py` possuem a mesma identidade. O inventário dos arquivos protegidos não usa o limite de apresentação de 1.000 arquivos. Testes iniciais e configuração do runner recebem hashes; remoções e alterações externas são detectadas antes e depois da verificação.

Links, hard links, arquivos especiais, caminhos externos e nomes de módulos reservados ao runner são recusados. A ferramenta de escrita não pode criar conftest ou modificar configuração de coleta. Isso impede que uma alteração da configuração substitua o cumprimento da tarefa.

## Verificação e limites de confiança

Cada execução recebe um snapshot filtrado e um launcher externo ao projeto. Python inicia com `-I`, e o framework é importado antes de incluir os módulos do projeto. Unittest usa o objeto TestResult; pytest usa hooks de coleta e resultado. A saída textual não é interpretada para determinar sucesso.

O relatório separado precisa estar completo e consistente, com código de saída zero, testes executados e ausência de erros. Aceitação independente não admite testes ignorados. Relatório ausente, término antecipado, excesso de saída, mudança de arquivos ou timeout reprovam a verificação.

A aceitação executa em outra cópia, sem carregar os testes/conftest criados pelo candidato. Oráculos e launcher são montados somente para leitura. Docker não tem rede nem acesso ao projeto original; a área gravável para o relatório é separada do snapshot. O modo local é deliberadamente opt-in e não confina acesso ao host.

**Limitação:** Python avaliado e framework compartilham um processo. Código deliberadamente hostil pode tentar introspecção, monkeypatching do framework ou sabotagem do canal de resultado. Um JSON separado e Docker não transformam esse processo numa raiz de confiança absoluta. Esta implementação cobre os desvios reproduzidos, evita confiar em stdout e exige aceitação independente; não promete prova universal de correção ou resistência a todo código Python adversarial. Para esse nível de ameaça, a verificação de comportamento precisa ocorrer fora do runtime do candidato, por exemplo por testes HTTP externos de um serviço isolado, e deve existir uma política adicional para execução de código hostil.

O filtro remove caminhos sensíveis conhecidos. Não detecta automaticamente todo segredo que possa estar embutido em um arquivo de código permitido. As ferramentas tratam arquivos e logs como dados não confiáveis, mas essa instrução também não elimina todas as formas de prompt injection.

## Repair loop e observabilidade

Falhas de testes e de aceitação são associadas à revisão corrente e voltam ao modelo. O log completo fica no rastro, limitado a 1 MB por subprocesso; o contexto recebe uma prévia identificada e pode pedir páginas adicionais. A saída não é cortada antes de determinar a contagem dos testes.

O grupo de processos é encerrado em timeout, interrupção ou saída; containers interrompidos são removidos. Exceções inesperadas no cliente não deixam a execução registrada como bem-sucedida. Erros de gravação dos próprios rastros continuam dependendo da disponibilidade do sistema de arquivos; não há retomada automática ou rollback.

## Avaliação independente

Cada tarefa parte de uma cópia do mesmo software inicial. O avaliador conserva todas as seis linhas desde o início, com sucesso falso para pendências. Um erro de cliente conta como falha com zero chamadas ou tentativas efetivamente feitas. A média inclui falhas, e FirstAttemptSuccess usa o total de tarefas como denominador.

Os testes independentes podem reprovar uma tentativa mesmo quando todos os testes do candidato passam. Isso aciona o repair loop antes de DONE. Na criação de testes, uma execução no original evita aceitar testes que falham sempre; quatro execuções mutantes evitam aceitar asserts triviais. A refatoração inclui verificações estruturais e observação da chamada à função auxiliar, além dos resultados.

Os oráculos são públicos no repositório, mas não são apresentados pelas ferramentas do projeto-alvo. São dados de desenvolvimento e não constituem uma avaliação cega de generalização. Mudanças nos contratos ou nos oráculos exigem mudar a versão da suíte.

## Referências de implementação

O launcher usa APIs documentadas de [unittest.TestResult](https://docs.python.org/3/library/unittest.html#unittest.TestResult), [hooks do pytest](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_runtest_logreport) e o [modo isolado do Python](https://docs.python.org/3/using/cmdline.html#cmdoption-I). Os limites e as políticas adicionais são definidos pelo MiniCode.
