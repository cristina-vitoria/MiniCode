# Resultados e limites — 22/11/2026

## Evidência disponível

| Experimento | Dataset | Resultado | Interpretação |
|---|---|---|---|
| QLoRA inicial, Qwen2.5-0.5B | seed v1, teste de 4 exemplos | 0/4; 4 inválidas | Piloto negativo, sem baseline e com divergência de template |
| Qwen2.5-14B-Instruct-AWQ | v2, teste de 16 exemplos | 2/16 (12,5%); 0 inválidas | Referência adicional; respostas brutas e manifesto preservados |
| Qwen2.5-0.5B base | v2, 16 exemplos | 0/16; 16 inválidas | Não obedeceu ao formato restrito |
| Mesmo checkpoint + QLoRA | v2, 16 exemplos | 12/16 (75%); 1 inválida | Ganho local de 75 pontos percentuais |
| QLoRA sem spec/plano | v2, 16 exemplos | 13/16 (81,25%); 0 inválidas | Um acerto a mais; contexto não ajudou neste piloto |
| Agente Qwen × Qwen+LoRA × ablação | softwareteste | INCOMPLETO | Bateria interrompida após timeouts persistentes da API; comparação não concluída |

Fontes: `experiments/tool_selection/2026-11-22-seed-v1/` e
`experiments/tool_selection/2026-11-22-qwen-reference-v2/` e
`experiments/tool_selection/2026-11-22-v2-trained/`.
O teste de engenharia em `engineering-validation/smoke.json` executou SFT e LoRA de verdade,
mas num modelo Qwen2 minúsculo aleatório. Ele valida supervisão, três caminhos de inferência,
salvamento e recarga; sua loss não é resultado científico da especialização.

O piloto v1 terminou com loss treino 2,2577 e validação 2,176619, apesar de 0% de acurácia.
Isso ilustra que melhorar loss não demonstra escolha correta de ferramenta. Não comparar v1 e v2
como ablação: dataset e protocolo são diferentes.

## Limitações do protocolo v2

- Teste com somente 16 decisões em duas famílias; decisões correlacionadas e templates compartilhados.
- Rótulos são escolhas prescritas pelo gerador; algumas ações alternativas podem ser razoáveis.
- O feedback sintético revela grande parte da etapa. Remover spec/plano pode ter pouco efeito por redundância.
- Qwen-14B produziu somente ferramentas válidas, mas não seguiu a maioria dos rótulos prescritos.
  Isso não mede sua capacidade de gerar argumentos ou resolver programação.
- A referência HTTP usou temperatura zero e limite de 4096 tokens; o modelo pequeno usa greedy
  com 16 tokens. Essa diferença é registrada no manifesto e limita a comparação entre tamanhos.
- As tarefas end-to-end são públicas; não constituem teste cego de generalização.
- O novo teste já foi avaliado pela referência. O protocolo deve permanecer congelado e não ser
  ajustado em função desse resultado. Qualquer adaptação exige um novo teste final.

## Questões do enunciado

1. **LLM versus harness:** os testes mostram que o harness impõe gates e recusa ações inválidas.
   Quantificar o efeito causal exige comparação controlada; 3/6 da Parte 1 não isola esse efeito.
2. **Spec melhora as tarefas?** Ainda não demonstrado. A ablação proposta remove spec/plano da
   entrada do seletor, não remove Spec-Driven Development do agente inteiro.
3. **Prompt versus imposição programática:** a suíte verifica que transições e DONE inválidos
   são bloqueados. Isso comprova o mecanismo, não uma diferença percentual experimental.
4. **Feedback permite reparo?** O teste roteirizado de repair comprova funcionamento. A bateria
   histórica teve falhas após três tentativas; não há evidência de ganho causal do repair nessa bateria.
5. **Fine-tuning melhorou o modelo?** Sim neste piloto: 0/16 → 12/16, com forte melhora no
   cumprimento do formato. Isso não estabelece generalização fora dos templates sintéticos.
6. **Ganho local virou ganho no agente?** Pendente da avaliação end-to-end.
7. **Modelo pequeno compete com o maior?** No teste sintético, QLoRA pequeno teve 75% contra 12,5%
   da referência 14B. A diferença de protocolo de geração e a especialização nos templates limitam
   a conclusão; isso não demonstra superioridade geral em programação.
8. **Qual componente teve maior impacto?** Ainda não estabelecido. Uma ablação só pode estimar
   a contribuição do contexto do seletor no piloto, não ordenar todos os componentes do agente.

Use `scripts/summarize_part2_results.py` após exportar o experimento para gerar tabelas a partir
das predições, e então revise estas respostas conforme a evidência real.

## Tentativa end-to-end após o treinamento

A avaliação separada da recarga CPU/float32, registrada em
`experiments/tool_selection/2026-11-22-v2-cpu/`, teve base 0/16 (16 inválidas),
LoRA 8/16 (0 inválidas) e ablação 9/16 (0 inválidas). A perda de quatro acertos em
ambas as condições adaptadas mostra que os números da T4/NF4 não podem ser
atribuídos automaticamente ao deployment float32. Hardware, precisão e versões
diferem; essa observação não isola causalmente qual diferença explica a queda.

O adapter foi carregado em CPU/float32 e a primeira condição Qwen sem seletor foi iniciada.
`discount` falhou após três tentativas: o teste criado aceitava percentual decimal contrariando
o contrato. Em `tax`, ocorreram cinco retentativas por timeout no endpoint. A execução foi
interrompida durante a especificação de `pagination` para não acumular chamadas sem resposta.
Os demais casos permanecem PENDING; as condições com seletor não foram iniciadas.

Os checkpoints em `experiments/results/parte2-v2-e2e/` estão marcados `complete: false` e
`status: incomplete`. O zero do checkpoint parcial não deve ser apresentado como taxa final
da bateria, nem usado para comparar com os 3/6 históricos da Parte 1.

O servidor respondeu a DNS/TCP/TLS, mas a rota de geração não respondeu a uma consulta curta
de um token em 30 segundos. O usuário informou que o serviço está ativo; a causa da ausência
de resposta da API não foi determinada. Não é uma falha comprovada do modelo especializado.
