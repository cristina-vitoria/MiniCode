# Experimentos de seleção de ferramentas

`2026-11-22-seed-v1/` preserva o primeiro treinamento real e seu resultado negativo. Ele serve como
evidência histórica, não como resultado final, porque não houve baseline e o protocolo de inferência
divergia do treinamento.

O experimento final deve ser produzido pelo notebook com o dataset v2 e deve conter, no mínimo:

- `base_test_predictions.jsonl` e `base_test_report.json`;
- `lora_test_predictions.jsonl` e `lora_test_report.json`;
- `lora_no_context_test_predictions.jsonl` e respectivo relatório de ablação;
- adapter, estado do trainer e curvas de loss fora do GitHub, acompanhados de checksum;
- bateria end-to-end sem seletor e com seletor LoRA, no mesmo commit e configuração.

Nenhuma tabela final deve ser preenchida sem esses artefatos.

`2026-11-22-qwen-reference-v2/` contém a referência real Qwen-14B: 2/16 acertos e zero respostas
inválidas. O manifesto registra modelo, protocolo, dataset, limite de geração e chamadas.
`engineering-validation/` contém um smoke técnico com modelo aleatório; não é avaliação científica.

O notebook novo produz pastas separadas por execução e um manifesto. Depois de exportar adapter e
resultados, `scripts/run_part2_experiments.py` executa as três condições end-to-end com Docker;
`scripts/summarize_part2_results.py` recalcula as métricas locais e gera a tabela comparativa.
Consulte `docs/parte2.md` para os comandos completos e `docs/PLANO_PARTE2.md` para o estado atual.
