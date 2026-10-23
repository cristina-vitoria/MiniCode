# Resultados das execuções Qwen

Todas as execuções planejadas são reportadas. Falhas permanecem no denominador. As categorias também registram ocorrências recuperadas durante tarefas bem-sucedidas.

| Execução | Tarefas | TaskSuccessRate | FirstAttemptSuccess | AverageIterations | AverageLLMCalls |
|---|---:|---:|---:|---:|---:|
| qwen-01 | 6 | 50.00% | 50.00% | 0.50 | 3.33 |
| qwen-02 | 6 | 0.00% | 0.00% | 0.67 | 2.67 |

## qwen-01

- factorial: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar uma função que calcula o fatorial de um número inteiro não negativo.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve retornar o valor correto para números não negativos.&quot;,&quot;A função deve lançar ValueError para números negativos.&quot;],&quot;assumptions&quot;:[&quot;A entrada será sempre um número inteiro.&quot;]}}</pre>
- mean: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar uma função que calcula a média aritmética de uma lista de valores.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve retornar a média correta para uma lista de números.&quot;,&quot;Para uma lista vazia, a função deve gerar um ValueError.&quot;],&quot;assumptions&quot;:[&quot;A lista de valores será composta por números inteiros ou decimais.&quot;]},&quot;implementation&quot;:&quot;def mean(values):\n    if len(values) == 0:\n        raise ValueError(&#x27;Lista vazia&#x27;)\n    return sum(values) / len(values)&quot;,&quot;test&quot;:&quot;import unittest\nfrom solution import mean\nclass TestMean(unittest.TestCase):\n    def test_mean(self):\n        self.assertEqual(mean([1, 2, 3, 4]), 2.5)\n        with self.assertRaises(ValueError):\n            mean([])\nif __name__ == &#x27;__main__&#x27;:\n    unittest.main()&quot;}</pre>
- health: DONE; sucesso independente=True; ferramenta recusada; sem erro fatal registrado.

  Chamada 5 — tool_rejected: Testes preexistentes são protegidos contra alteração

<pre>{
  &quot;tool&quot;: &quot;write_file&quot;,
  &quot;args&quot;: {
    &quot;path&quot;: &quot;tests/test_smoke.py&quot;,
    &quot;content&quot;: &quot;import unittest\nimport solution\nclass Smoke(unittest.TestCase):\n    def test_import(self):\n        self.assertIsNotNone(solution)\n    def test_health_route(self):\n        environ = {\n            &#x27;PATH_INFO&#x27;: &#x27;/health&#x27;\n        }\n        status, headers, response = solution.app(environ, lambda status, headers: (status, headers))\n        self.assertEqual(status, &#x27;200 OK&#x27;)\n        self.assertIn((&#x27;Content-Type&#x27;, &#x27;application/json&#x27;), headers)\n        self.assertDictEqual(response[0].decode(), &#x27;{\&quot;status\&quot;:\&quot;ok\&quot;}&#x27;)\n&quot;
  }
}</pre>
- tests: DONE; sucesso independente=True; formato/estrutura; sem erro fatal registrado.

  Chamada 1 — json_or_size: Extra data: line 3 column 1 (char 326)

<pre>{&quot;objective&quot;:&quot;Criar testes unitários para a função clamp&quot;,&quot;acceptance_criteria&quot;:[&quot;Testes que cobrem valores de entrada abaixo, dentro e acima dos limites.&quot;,&quot;Teste que gera ValueError quando low &gt; high.&quot;,&quot;Todos os testes devem passar.&quot;],&quot;assumptions&quot;:[&quot;A função clamp está corretamente implementada no arquivo solution.py.&quot;]}

{
  &quot;objective&quot;: &quot;Criar testes unitários para a função clamp&quot;,
  &quot;acceptance_criteria&quot;: [
    &quot;Testes que cobrem valores de entrada abaixo, dentro e acima dos limites.&quot;,
    &quot;Teste que gera ValueError quando low &gt; high.&quot;,
    &quot;Todos os testes devem passar.&quot;
  ],
  &quot;assumptions&quot;: [
    &quot;A função clamp está corretamente implementada no arquivo solution.py.&quot;
  ]
}</pre>
- validation: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar a função validate_age(value) que valida uma idade.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve aceitar apenas inteiros entre 0 e 130 (inclusive).&quot;,&quot;Para valores fora do intervalo ou tipos diferentes de int, deve ser lançada uma ValueError.&quot;],&quot;assumptions&quot;:[&quot;O valor passado para a função será um único argumento.&quot;]}}</pre>
- refactor: DONE; sucesso independente=True; ferramenta recusada; sem erro fatal registrado.

  Chamada 5 — tool_rejected: Testes preexistentes são protegidos contra alteração

<pre>{
  &quot;tool&quot;: &quot;write_file&quot;,
  &quot;args&quot;: {
    &quot;path&quot;: &quot;tests/test_smoke.py&quot;,
    &quot;content&quot;: &quot;import unittest\nimport solution\nclass Smoke(unittest.TestCase):\n    def test_import(self):\n        self.assertIsNotNone(solution)\n    def test_total_price(self):\n        items = [{&#x27;price&#x27;: 10, &#x27;quantity&#x27;: 2}, {&#x27;price&#x27;: 20, &#x27;quantity&#x27;: 3}]\n        self.assertEqual(solution.total_price(items), 90)\n    def test_subtotal(self):\n        item = {&#x27;price&#x27;: 10, &#x27;quantity&#x27;: 2}\n        self.assertEqual(solution.subtotal(item), 20)\nif __name__ == &#x27;__main__&#x27;:\n    unittest.main()\n&quot;
  }
}</pre>

## qwen-02

- factorial: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar uma função que calcula o fatorial de um número inteiro não negativo.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve retornar o valor correto para números inteiros não negativos.&quot;,&quot;A função deve gerar um ValueError para números inteiros negativos.&quot;],&quot;assumptions&quot;:[&quot;A entrada será sempre um número inteiro.&quot;]},&quot;implementation&quot;:&quot;def factorial(n):\n    if n &lt; 0:\n        raise ValueError(&#x27;Input must be a non-negative integer&#x27;)\n    result = 1\n    for i in range(1, n + 1):\n        result *= i\n    return result&quot;,&quot;test&quot;:&quot;import unittest\nfrom solution import factorial\nclass TestFactorial(unittest.TestCase):\n    def test_factorial_positive(self):\n        self.assertEqual(factorial(5), 120)\n        self.assertEqual(factorial(0), 1)\n    def test_factorial_negative(self):\n        with self.assertRaises(ValueError):\n            factorial(-1)&quot;}</pre>
- mean: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar uma função que calcula a média aritmética de uma lista de valores.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve retornar a média correta para uma lista de números.&quot;,&quot;Para uma lista vazia, a função deve gerar um ValueError.&quot;],&quot;assumptions&quot;:[&quot;A lista de valores será composta por números inteiros ou decimais.&quot;]}}</pre>
- health: DONE; sucesso independente=False; implementação/verificação; sem erro fatal registrado.
- tests: FAILED; sucesso independente=False; formato/estrutura; sem erro fatal registrado.

  Chamada 1 — json_or_size: Extra data: line 3 column 1 (char 294)

<pre>{&quot;objective&quot;:&quot;Criar testes unitários para a função clamp&quot;,&quot;acceptance_criteria&quot;:[&quot;Testes que cobrem valores de entrada abaixo, dentro e acima dos limites.&quot;,&quot;Teste que gera ValueError quando low &gt; high.&quot;],&quot;assumptions&quot;:[&quot;A função clamp está corretamente implementada no arquivo solution.py.&quot;]}

{
  &quot;objective&quot;: &quot;Criar testes unitários para a função clamp&quot;,
  &quot;acceptance_criteria&quot;: [
    &quot;Testes que cobrem valores de entrada abaixo, dentro e acima dos limites.&quot;,
    &quot;Teste que gera ValueError quando low &gt; high.&quot;
  ],
  &quot;assumptions&quot;: [
    &quot;A função clamp está corretamente implementada no arquivo solution.py.&quot;
  ]
}</pre>
- validation: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{&quot;specification&quot;:{&quot;objective&quot;:&quot;Implementar uma função que valide uma idade.&quot;,&quot;acceptance_criteria&quot;:[&quot;A função deve aceitar apenas inteiros entre 0 e 130.&quot;,&quot;Para valores fora do intervalo ou tipos diferentes de int, deve lançar ValueError.&quot;],&quot;assumptions&quot;:[&quot;A função será chamada com variáveis de tipos variados.&quot;]}}</pre>
- refactor: FAILED; sucesso independente=False; formato/estrutura; Especificação sem objetivo ou critérios verificáveis.

  Chamada 1 — specification: Especificação sem objetivo ou critérios verificáveis

<pre>{
  &quot;specification&quot;: {
    &quot;objective&quot;: &quot;Refatorar a função total_price para calcular o preço total de uma lista de itens, onde cada item possui um preço unitário e uma quantidade.&quot;,
    &quot;acceptance_criteria&quot;: [
      &quot;A função deve retornar o valor numérico correto para uma lista de itens.&quot;,
      &quot;A refatoração deve incluir funções auxiliares que calculam subtotais individuais.&quot;,
      &quot;A lista vazia deve retornar zero.&quot;
    ],
    &quot;assumptions&quot;: [
      &quot;Cada item na lista &#x27;items&#x27; terá chaves &#x27;price&#x27; e &#x27;quantity&#x27;.&quot;,
      &quot;A função total_price deve funcionar corretamente antes da refatoração.&quot;
    ]
  }
}</pre>

A rejeição de uma especificação indica falha de estrutura exigida pelo harness; as respostas brutas disponíveis nos rastros são apresentadas acima e preservadas em summary.json. Rastros antigos podem não conter esse campo. Zero iterações significa falha antes da implementação, não solução na primeira tentativa.

