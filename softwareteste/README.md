# SoftwareTeste — API para avaliação de agente

API Flask de uma pequena loja, preparada com **seis pendências intencionais**. A arquitetura e os testes-base funcionam. Os prompts em [TASKS.md](TASKS.md) completam ou melhoram pontos específicos. Este é um ambiente de avaliação, não uma aplicação de produção.

## Executar

Requer Python 3.11 ou superior. Dentro de `softwareteste`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

A API fica em `http://127.0.0.1:5000`. Alternativa: `flask --app main run`.

```bash
curl http://127.0.0.1:5000/health
curl http://127.0.0.1:5000/products
curl -X POST http://127.0.0.1:5000/users \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ana","email":"ana@example.com","age":25}'
```

## Testar

```bash
python -m pytest -q
```

Os testes usam o cliente Flask, sem abrir servidor ou conexão de rede. Cada instância da aplicação recebe armazenamento novo com 12 produtos. Usuários ficam em memória e são perdidos ao reiniciar o processo.

A suíte inicial cobre rotas funcionais, isolamento de instâncias e o comportamento do relatório. Não exige corrigir as lacunas. `tests/test_services.py` foi deliberadamente omitido; nenhuma função de `app/services.py` é coberta pelos testes-base.

## Estrutura

```text
softwareteste/
  main.py                    Entrada da API
  requirements.txt           Flask e pytest
  pytest.ini                 Configuração dos testes
  TASKS.md                   Seis prompts e protocolo de avaliação
  app/
    __init__.py              create_app e tratamento de erros HTTP
    config.py                Configuração
    routes.py                Registro de rotas
    controllers.py           Entrada e saída HTTP
    models.py                Product e User
    repositories.py          Armazenamento em memória
    cart_service.py          Desconto incompleto
    tax_service.py           Imposto com bug intencional
    services.py              Três regras completas sem testes
    user_service.py          Cadastro sem validação dos campos
    report_service.py        Relatório correto com dívida técnica
  tests/
    conftest.py              Fixtures app e client
    test_api.py              Contratos-base da API
    test_reports.py          Preservação do relatório
```

O fluxo é `rotas → controllers → serviços/repositório → modelos`. As funções de cálculo independem do Flask. `create_app` permite estado e configuração isolados por teste, conforme os padrões de [application factories](https://flask.palletsprojects.com/en/stable/patterns/appfactories/) e [testes do Flask](https://flask.palletsprojects.com/en/stable/testing/).

## Pendências preservadas

| Tarefa | Local | Estado inicial |
| --- | --- | --- |
| 01 | cart_service.py | calculate_discount lança NotImplementedError |
| 02 | tax_service.py | Escala incorreta no cálculo do imposto |
| 03 | GET /products | Retorna todos os itens e ignora paginação |
| 04 | services.py | Frete, pontos e cupom corretos, sem testes |
| 05 | POST /users | Aceita idade negativa, e-mail inválido e campos ausentes |
| 06 | report_service.py | Nomes ruins, aninhamento e lógica duplicada |

O desconto incompleto não é chamado pelas rotas-base. O POST rejeita JSON malformado e corpo não objeto, mas ainda não valida campos. Assim, a API funciona enquanto as seis tarefas permanecem abertas.

## Preparar uma avaliação

Guarde uma cópia intacta. Prepare uma cópia independente por prompt, sem copiar `.venv`, caches ou soluções anteriores. Registre o estado inicial, versões efetivas de Python e dependências e limites do agente. `requirements.txt` contém faixas de versões, não um lock completo: registre `python -m pip freeze` para reproduzir o ambiente.

O arquivo `requirements.lock` registra as versões utilizadas nesta verificação, feita com Python 3.12. Para reproduzi-las, instale com `python -m pip install -r requirements.lock`. A versão inicial passou nos 16 testes-base, mantendo as pendências intencionais.

O agente precisa executar `python -m pytest -q` com Flask e pytest instalados. O MiniCode agora oferece perfil pytest e imagem Docker com essas dependências. Use `--task-id` para selecionar o enunciado e a aceitação independente; consulte o [README principal](../README.md).

O conjunto é público e serve para tarefas de desenvolvimento conhecidas. Sucesso depende dos testes independentes e das restrições dos prompts, não apenas da declaração do agente ou da aprovação nos testes-base.
