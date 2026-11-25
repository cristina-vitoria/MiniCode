# Resultados da Parte 2

| Condição | Acertos | Acurácia | Inválidas |
|---|---:|---:|---:|
| base_test | 0/16 | 0.00% | 16 |
| lora_test | 12/16 | 75.00% | 1 |
| lora_no_context_test | 13/16 | 81.25% | 0 |

Diferença LoRA − base: +75.00 pontos percentuais.
Diferença contexto − sem contexto: -6.25 pontos percentuais.

Este é um piloto sintético com duas famílias de teste e templates compartilhados.
As decisões de uma família não são observações independentes. Não há evidência de generalização ampla.

| Agente | TaskSuccessRate | FirstAttemptSuccess | Iterações | Chamadas totais |
|---|---:|---:|---:|---:|
| qwen | 16.67% | 0.00% | 1.83 | 12.50 |
| qwen_lora | 0.00% | 0.00% | 1.00 | 23.50 |
| qwen_lora_no_context | 0.00% | 0.00% | 1.17 | 31.17 |

As seis tarefas são públicas e uma única repetição não estima variabilidade.
Chamadas totais incluem o seletor; falhas de infraestrutura permanecem no denominador.
