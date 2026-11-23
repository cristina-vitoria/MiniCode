# Verificação NF4 em CPU interrompida

Bitsandbytes 0.48.2 conseguiu quantizar/dequantizar NF4 com double quant em CPU,
e carregar o checkpoint com adapter. A primeira predição levou aproximadamente
dois minutos; a execução foi interrompida com SIGINT por custo de tempo, sem
chegar às condições LoRA. O manifesto foi marcado incompleto após a interrupção.
Há somente uma predição base, não métricas comparativas.

Isso não reproduz nem refuta os resultados da T4/NF4. CPU/float32 foi avaliada
completamente na pasta vizinha. Para reproduzir a condição de treinamento,
preferir GPU com a mesma precisão e registrar as versões efetivamente carregadas.
