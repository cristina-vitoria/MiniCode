# Seis tarefas de avaliação

Copie um dos blocos abaixo como prompt. Execute cada tarefa em uma cópia independente da versão inicial, com os mesmos limites de tentativas e chamadas. Os testes-base verificam a arquitetura existente; passar neles não comprova que uma lacuna foi resolvida.

## 01 — Implementação de função

```text
No projeto softwareteste, implemente calculate_discount(subtotal_cents, percentage) em app/cart_service.py, que atualmente lança NotImplementedError.

Retorne o VALOR do desconto em centavos, não o total após o desconto. Ambos os argumentos devem ser exatamente int, sem aceitar bool. subtotal_cents deve ser >= 0; percentage deve estar entre 0 e 100, inclusive. Violações geram ValueError. Use aritmética inteira, descartando frações de centavo: calculate_discount(1999, 15) retorna 299. Zero por cento retorna 0; 100 por cento retorna o subtotal.

Crie tests/test_cart_service.py com pytest, cobrindo valores usuais, truncamento, limites, zero, negativos, percentual acima de 100 e tipos inválidos, incluindo bool, float, str e None. Preserve a assinatura, os testes existentes e as demais pendências. Não acrescente dependências. Execute python -m pytest -q e apresente o resultado.
```

## 02 — Correção de bug

```text
No projeto softwareteste, investigue e corrija o erro lógico em calculate_tax(subtotal_cents, rate_percent), de app/tax_service.py.

A função deve calcular imposto percentual em centavos: calculate_tax(10000, 10) retorna 1000; calculate_tax(1999, 7) retorna 139. Use aritmética inteira e descarte frações de centavo. Preserve as validações existentes: subtotal exatamente int não negativo; alíquota exatamente int de 0 a 100; bool e outros tipos inválidos geram ValueError.

Crie tests/test_tax_service.py com testes pytest de regressão que falhem no cálculo original e passem após a correção. Cubra zero, 100%, truncamento, valores usuais e entradas inválidas. Preserve a assinatura, os testes existentes e as demais pendências. Não acrescente dependências. Execute python -m pytest -q e explique a causa do bug.
```

## 03 — Modificação de API: paginação

```text
No projeto softwareteste, adicione paginação a GET /products, mantendo a separação entre rotas, controllers e acesso aos dados.

Aceite page e page_size, com padrões 1 e 20. Ambos devem conter somente dígitos ASCII e representar inteiros positivos; page_size deve ser no máximo 100. Valores vazios, negativos, zero, decimais, letras e page_size acima de 100 retornam HTTP 400 com JSON contendo error com mensagem textual. Parâmetros não relacionados à paginação podem ser ignorados.

Retorne HTTP 200 e JSON no formato {"items": [...], "total": N, "page": P, "page_size": S, "total_pages": T}. total é a quantidade antes de paginar; total_pages é o teto de total/page_size, ou 0 para catálogo vazio. Preserve os campos dos itens e a ordem crescente de id. Página além da última retorna items vazio sem erro. Sem parâmetros, os 12 produtos iniciais continuam sendo retornados. Não modifique o catálogo ao paginar.

Crie tests/test_pagination.py com pytest e o cliente Flask, cobrindo padrões, primeira página, página intermediária, última página incompleta, página excedente, catálogo vazio e parâmetros inválidos. Preserve os testes existentes e as demais pendências. Não acrescente dependências. Execute python -m pytest -q.
```

## 04 — Criação de testes

```text
No projeto softwareteste, crie tests/test_services.py para as três funções já completas de app/services.py. Não modifique app/services.py nem outros arquivos da aplicação. Use pytest e parametrização quando apropriado. Não substitua por mocks as funções avaliadas.

Contratos:
- shipping_cost(subtotal_cents): retorna 1500 abaixo de 20000 centavos e 0 a partir de 20000, inclusive.
- loyalty_points(subtotal_cents): retorna um ponto por 1000 centavos completos, descartando a fração.
- Nas duas funções, subtotal deve ser exatamente int não negativo; bool, float, str, None e negativos geram ValueError.
- normalize_coupon(code): exige str, remove espaços nas extremidades e converte para maiúsculas. Depois dessa transformação, exige 3 a 12 caracteres ASCII alfanuméricos, sem espaços internos nem pontuação. Violações geram ValueError.

Cubra frete em 0, 19999, 20000 e 20001; pontos em 0, 999, 1000 e 1999; cupons com normalização, comprimentos válidos nas duas bordas, comprimentos inválidos, espaços internos, pontuação, caracteres não ASCII após normalização e tipos inválidos. Verifique valores e exceções específicos, sem asserts triviais. Os testes devem passar na implementação original e detectar mudanças erradas nos limites ou na normalização. Preserve os testes existentes e as demais pendências. Não acrescente dependências. Execute python -m pytest -q.
```

## 05 — Validação de dados

```text
No projeto softwareteste, valide os dados de POST /users antes de armazenar qualquer usuário. Centralize as regras em app/user_service.py e mantenha no controller a tradução de erros para HTTP.

Exija um objeto JSON contendo name, email e age. name deve ser str e ter de 2 a 80 caracteres após strip. email deve ser str, ter exatamente um @, partes não vazias antes e depois do @ e nenhum espaço em branco interno; remova espaços nas extremidades antes de validar e armazenar. Não é necessário validar DNS, exigir ponto no domínio, verificar unicidade nem aplicar a especificação completa de e-mail. age deve ser exatamente int entre 0 e 130, inclusive; não aceite bool, float ou str. Campos extras podem ser ignorados.

Campos ausentes ou inválidos devem retornar HTTP 400 com JSON contendo error com mensagem textual, sem inserir registros nem consumir o próximo ID. Um objeto válido retorna HTTP 201 com id, name e email normalizados com strip, e age. Preserve o tratamento HTTP atual de JSON malformado, corpo não objeto e Content-Type inadequado.

Crie tests/test_user_validation.py com pytest, cobrindo entradas válidas, limites, campos ausentes, strings vazias, idades negativas ou acima de 130, tipos incorretos, e-mails inválidos e ausência de efeitos no armazenamento após rejeição. Preserve os testes existentes e as demais pendências. Não acrescente dependências. Execute python -m pytest -q.
```

## 06 — Pequena refatoração

```text
No projeto softwareteste, refatore build_sales_report(orders) em app/report_service.py sem mudar seu comportamento público.

Substitua nomes como a, b, x, y e w por nomes expressivos, reduza o aninhamento usando condições de saída antecipada ou continue, e extraia para uma função auxiliar única o cálculo de receita e unidades dos itens. Reutilize essa função para os dois canais, eliminando a duplicação. Preserve a assinatura de build_sales_report e todas as chaves e tipos retornados.

Contrato: considere apenas pedidos com status paid e channel retail ou wholesale. revenue_cents soma price_cents * quantity dos itens com quantity > 0; units soma essas quantidades; orders conta cada pedido elegível, mesmo sem itens. by_channel sempre contém retail e wholesale, incluindo zeros. Itens gratuitos contam unidades, mas não receita. Ignore pedidos não pagos ou de outros canais. Não modifique a entrada. Assuma a estrutura e os tipos válidos descritos no módulo; não acrescente novas validações.

Preserve integralmente tests/test_reports.py e acrescente tests/test_report_refactor.py com múltiplos pedidos por canal, quantidades zero, itens gratuitos e verificação de que a entrada não muda. Preserve as demais pendências, não acrescente dependências, execute python -m pytest -q e descreva onde a lógica duplicada foi eliminada.
```

## Como avaliar

Uma tarefa conta como correta quando passa nos testes de aceitação independentes e nas restrições do prompt. Mantenha esses testes fora do diretório acessível ao agente. Na refatoração, confira também a extração e reutilização da função auxiliar: equivalência de saída não prova eliminação da duplicação.

Na criação de testes, execute a suíte criada no original e em cópias com mutações temporárias: trocar `>=` por `>` no frete; dividir pontos por 100 em vez de 1000; retirar `strip` ou `upper` do cupom. Os testes devem passar no original e detectar cada mutação. Não altere o projeto-base para realizar esse procedimento.

Registre por tarefa: ID, sucesso independente, tentativas, chamadas LLM e, opcionalmente, tempo em segundos. A primeira implementação conta como uma tentativa; falhas anteriores a ela contam como zero. Retentativas de resposta do modelo contam como chamadas.

| Métrica | Cálculo para a bateria completa |
| --- | --- |
| TaskSuccessRate | tarefas corretas / 6 |
| FirstAttemptSuccess | tarefas corretas na primeira tentativa / 6 |
| AverageIterations | soma das tentativas de todas as tarefas / 6 |
| AverageLLMCalls | soma das chamadas LLM de todas as tarefas / 6 |

Falhas operacionais permanecem no denominador. O MiniCode fornece o executor em `src/minicode/evaluator.py` e os oráculos independentes em `src/minicode/acceptance/`, fora deste projeto-alvo. Execute a bateria com `python -m minicode --evaluate /tmp/minicode-avaliacao-01` a partir da raiz do repositório.
