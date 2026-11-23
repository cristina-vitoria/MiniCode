# Checkpoint incompleto, não resultado final

Cópia pequena de `experiments/results/parte2-v2-e2e/`, iniciada após importar o
treinamento v2. O manifesto preserva identidade do adapter, código e configuração.
As três condições foram planejadas, mas somente Qwen sem seletor foi iniciada.

- `discount`: FAILED após três tentativas; teste gerado conflita com o contrato.
- `tax`: falha após cinco timeouts; não comprova incapacidade do modelo na tarefa.
- `pagination`: interrompida; restantes PENDING.
- Condições com seletor não executadas; não há comparação end-to-end.

O usuário confirmou o serviço ativo, mas as consultas mínimas de geração também
expiraram em 30 e 20 segundos. DNS, conexão e TLS funcionaram; causa da falta de
resposta HTTP não determinada. Nenhum segredo foi incluído nestes arquivos.
O zero do checkpoint não deve ser usado como TSR final. Retomar em pasta nova,
preservando esta tentativa e o dataset congelado.
