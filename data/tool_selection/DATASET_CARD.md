# Dataset de seleção de ferramentas — versão 2

## Objetivo

Classificar a próxima ferramenta segura do MiniCode a partir do estado do agente, tarefa,
especificação, plano e feedback da ação anterior. O rótulo contém apenas o nome da ferramenta;
argumentos e autorização de execução permanecem sob controle do harness.

## Origem e curadoria

Os 96 exemplos são cenários sintéticos gerados de forma determinística por
`scripts/build_tool_selection_dataset.py`. Eles foram escritos a partir da interface real da Parte 1,
mas não foram gerados por teacher model e não contêm credenciais, código executável ou argumentos de
ferramentas. A proveniência legada de cada linha é `human_curated_scenario_v2`, mas não existe
registro de revisão humana independente. A expansão foi produzida com assistência de IA;
esse campo não comprova curadoria humana. Os bytes permanecem congelados para preservar o hash.

Cada exemplo representa uma decisão operacional plausível: inventariar arquivos, buscar símbolos, ler
produção/testes, editar, criar teste, executar testes ou paginar o log de uma falha. Todos usam o estado
`IMPLEMENTING`, que é o estado no qual o seletor é realmente consultado pela integração.

## Splits congelados

| Split | Exemplos | Famílias |
|---|---:|---:|
| treino | 64 | 8 |
| validação | 16 | 2 |
| teste | 16 | 2 |

A família pertence a exatamente um split. As famílias finais de teste são `retry_timeout` e
`audit_logging`; elas não correspondem às seis tarefas públicas usadas na avaliação da Parte 1.
Depois de congelada esta versão, o teste não deve orientar prompts, hiperparâmetros ou nova curadoria.

SHA-256 de `examples.jsonl`: `42393f6ea6e93432c0a7dccca2b7f4700cced33b59a6732fb6065521c81bf3a1`.

## Limitações

- O dataset ainda é pequeno e sintético; ganho local deve ser confirmado end-to-end.
- Os mesmos templates de feedback atravessam os splits. Separar famílias evita repetição da
  tarefa, mas não elimina a similaridade de linguagem nem prova generalização para trajetórias reais.
- Algumas classes não aparecem no teste; reportar também contagens por classe e saídas inválidas.
- As trajetórias seguem o harness atual e não representam todos os projetos possíveis.
- Os rótulos expressam a ação pretendida pelo gerador, não uma prova de decisão globalmente ótima.
- Acurácia mede apenas o nome da ferramenta, não a qualidade dos argumentos ou do patch.

## Validação

```bash
python3 scripts/build_tool_selection_dataset.py
python3 scripts/validate_tool_selection_dataset.py data/tool_selection/examples.jsonl
```
