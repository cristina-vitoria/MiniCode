"""Seis tarefas de desenvolvimento, cada uma com projeto e oráculo independente."""
CASES = [
    {"id": "factorial", "kind": "implementacao_funcao", "task": "Implemente factorial(n): fatorial de inteiro não negativo; negativos geram ValueError.",
     "source": "def factorial(n):\n    raise NotImplementedError\n",
     "checks": "self.assertEqual(m.factorial(0), 1)\n        self.assertEqual(m.factorial(5), 120)\n        with self.assertRaises(ValueError): m.factorial(-1)"},
    {"id": "mean", "kind": "correcao_bug", "task": "Corrija mean(values): média aritmética; lista vazia gera ValueError.",
     "source": "def mean(values):\n    return sum(values) / (len(values) + 1)\n",
     "checks": "self.assertEqual(m.mean([2, 4, 6]), 4)\n        self.assertEqual(m.mean([-2, 2]), 0)\n        with self.assertRaises(ValueError): m.mean([])"},
    {"id": "health", "kind": "modificacao_api", "task": "Adicione GET /health à aplicação WSGI app: HTTP 200, Content-Type application/json e corpo {\"status\":\"ok\"}. Outras rotas continuam retornando 404.",
     "source": "def app(environ, start_response):\n    start_response('404 Not Found', [('Content-Type', 'text/plain')])\n    return [b'not found']\n",
     "checks": "responses = []\n        body = b''.join(m.app({'PATH_INFO': '/health', 'REQUEST_METHOD': 'GET'}, lambda status, headers: responses.append((status, dict(headers)))))\n        self.assertTrue(responses[0][0].startswith('200'))\n        self.assertEqual(responses[0][1]['Content-Type'], 'application/json')\n        self.assertEqual(__import__('json').loads(body), {'status': 'ok'})\n        m.app({'PATH_INFO': '/missing', 'REQUEST_METHOD': 'GET'}, lambda status, headers: self.assertTrue(status.startswith('404')))"},
    {"id": "tests", "kind": "criacao_testes", "task": "Adicione tests/test_clamp.py com unittest para clamp(x, low, high). Cubra x abaixo, dentro e acima dos limites e low > high gerando ValueError. Preserve a função.",
     "source": "def clamp(x, low, high):\n    if low > high:\n        raise ValueError('invalid bounds')\n    return max(low, min(x, high))\n",
     "checks": "self.assertEqual(m.clamp(-1, 0, 10), 0)\n        self.assertEqual(m.clamp(5, 0, 10), 5)\n        self.assertEqual(m.clamp(11, 0, 10), 10)\n        with self.assertRaises(ValueError): m.clamp(0, 5, 1)"},
    {"id": "validation", "kind": "validacao_dados", "task": "Implemente validate_age(value): aceite apenas int de 0 a 130, rejeite bool, strings e demais valores com ValueError; retorne a idade aceita.",
     "source": "def validate_age(value):\n    return value\n",
     "checks": "self.assertEqual(m.validate_age(0), 0)\n        self.assertEqual(m.validate_age(130), 130)\n        for value in [-1, 131, True, '20', 2.5, None]:\n            with self.assertRaises(ValueError): m.validate_age(value)"},
    {"id": "refactor", "kind": "refatoracao", "task": "Refatore total_price(items) extraindo subtotal(item), sem mudar resultados. Cada item tem price e quantity. Lista vazia retorna zero.",
     "source": "def total_price(items):\n    total = 0\n    for item in items:\n        total += item['price'] * item['quantity']\n    return total\n",
     "checks": "self.assertEqual(m.subtotal({'price': 3, 'quantity': 2}), 6)\n        self.assertEqual(m.total_price([]), 0)\n        self.assertEqual(m.total_price([{'price': 3, 'quantity': 2}, {'price': 2, 'quantity': 4}]), 14)"},
]


def test_source(checks):
    return "import unittest\nimport solution as m\n\nclass Acceptance(unittest.TestCase):\n    def test_acceptance(self):\n        " + checks + "\n"
