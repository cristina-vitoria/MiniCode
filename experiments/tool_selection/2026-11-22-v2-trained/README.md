# Execução Colab v2 validada

Origem: `minicode-experiments-20261122T223042Z-1-001.zip`, fornecido pelo usuário em 22/11/2026.
SHA-256 do ZIP: `0478d9abab825b64df513318dad573fe5792c2ad368a476d013c3c63fc425764`.
Execução: `v2-20261122T222705957216Z`, Tesla T4, cinco épocas, 40 passos, seed 42.

Os hashes de todos os arquivos declarados no manifesto e de todos os arquivos do adapter
foram conferidos antes da importação. O dataset e os módulos de protocolo/inferência são
idênticos aos locais. As três métricas foram recalculadas a partir das predições.

| Condição | Acertos | Acurácia | Saídas inválidas |
|---|---:|---:|---:|
| Qwen2.5-0.5B base NF4 | 0/16 | 0% | 16 |
| Mesmo modelo + QLoRA | 12/16 | 75% | 1 |
| Mesmo QLoRA sem spec/plano | 13/16 | 81,25% | 0 |

LoRA melhora 75 pontos percentuais neste piloto sintético. A ablação sem contexto acerta um
exemplo a mais; não há evidência de benefício do contexto neste teste. Com duas famílias e
templates compartilhados, não extrapolar para projetos reais sem avaliação end-to-end.

Treino levou 147,4477 s; loss média de treino 0,57796046; loss final de validação 0,20560047.
Foram treinados 2.162.688 parâmetros de 496.195.456 (aproximadamente 0,436%).

Este diretório contém os artefatos pequenos. A cópia completa está em `artifacts/colab-v2/`,
incluindo `adapter/adapter_model.safetensors`; pesos e estados do otimizador não são versionados.
Não foi necessário desserializar arquivos pickle (`.pt`, `.bin`, `.pth`) para validar ou usar o adapter.

Limite de reprodutibilidade: `environment.txt` registra PEFT 0.18.0, mas `adapter_config.json`
declara `peft_version` 0.22.0. Isso sugere diferença entre pacote instalado e módulo carregado no
runtime; não é possível reconstruir essa condição apenas com pip freeze. O carregador local
0.18.0 aceita o adapter clássico e avisa que ignora campos novos, todos nulos neste arquivo.
Essa divergência deve constar da análise, sem alterar o export original.
