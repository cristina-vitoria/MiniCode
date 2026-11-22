# Plano de conclusão da Parte 2

Plano iniciado em 2026-11-22. Conclusão depende de artefatos de execução, não apenas código.

1. **Protocolo e treinamento:** usar exatamente as mesmas mensagens em treino, inferência e agente;
   incluir o rótulo supervisionado; calcular loss somente na resposta; validar a máscara de labels;
   avaliar o checkpoint base antes de treinar e salvar adapter recarregável.
2. **Dados e metodologia:** preservar o teste v2 e o resultado negativo v1; registrar origem sintética,
   limitações dos templates, hashes, seed, versão do modelo e ambiente; não ajustar após consultar teste.
3. **Avaliação local:** executar base, LoRA e ablação sem spec/plano; guardar saídas brutas,
   acurácia, respostas inválidas e resultado por exemplo. Resultado negativo também conclui a experiência.
4. **Integração e avaliação end-to-end:** carregar o adapter efetivo, manter gates e Docker, contar
   chamadas dos dois modelos e executar condições comparáveis na mesma suíte/revisão.
5. **Entrega:** publicar resultados pequenos, instruções reproduzíveis, análise das oito questões,
   explicação de LoRA/QLoRA e roteiro do vídeo. Pesos ficam fora do Git com checksum.

## Critérios de fechamento

- [x] Testes de protocolo, supervisão, integração e métricas aprovados: 105 testes, incluindo Docker.
- [ ] Notebook executado do início ao fim em runtime limpo com GPU.
- [ ] Manifesto, losses, adapter e três relatórios locais presentes.
- [ ] Três baterias end-to-end completas e comparáveis.
- [ ] Análise escrita a partir dos resultados, incluindo limites e falhas.
- [ ] Vídeo gravado e link registrado.

O dataset v2 tem apenas duas famílias de teste e feedbacks derivados dos mesmos templates.
O resultado local deve ser apresentado como piloto sintético, sem alegar generalização ampla.
Não transformar fixtures ou smoke tests em resultados de modelo.

## Execução deste plano

- Protocolo compartilhado e targets de treinamento corrigidos; loss apenas na resposta e máscara
  verificada antes de treinar. Notebook sem outputs atribuídos a uma execução ainda não feita.
- Smoke SFT/LoRA executado em CPU: supervisão, três condições, salvamento/recarga e cliente direto aprovados.
- Chamadas do seletor entram no orçamento global e nas métricas; regressões verificadas.
- Executor de três condições, validação de hashes e gerador de tabelas implementados e testados.
- Referência Qwen-14B executada: 2/16 (12,5%), zero saídas inválidas, 16 chamadas.
- Dataset v2 congelado permanece com SHA-256 original; origem sintética e ausência de revisão humana
  independente esclarecidas no card, sem alterar os dados após o teste.
- AI_USAGE.md, análise das oito questões, roteiro de vídeo e pacote Colab preparados.

**Dependência externa atual:** não há GPU CUDA local. Nenhuma sessão Colab está disponível nos
navegadores acessíveis e a busca no Drive conectado não encontrou o notebook. É necessário abrir
a sessão Colab com GPU ou fornecer seu link/acesso para executar o treinamento real v2.
Ainda não existe adapter v2 validado; portanto a bateria end-to-end com esse adapter não foi iniciada.

O trabalho não está marcado como concluído. Atualizar este checklist somente quando os arquivos
previstos e o vídeo existirem e tiverem sido conferidos.
