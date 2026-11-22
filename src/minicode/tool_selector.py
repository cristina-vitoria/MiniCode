"""Interface estreita para o modelo especializado de escolha de ferramenta.

O seletor só sugere um nome de ferramenta. Ele nunca recebe uma capacidade de
escrever arquivos, mudar o estado do agente ou executar comandos; as mesmas
validações do harness continuam sendo a autoridade para argumentos e transições.
"""
from __future__ import annotations

from dataclasses import dataclass

from .llm import ModelError
from .selector_protocol import TOOL_SET as TOOLS
from .selector_protocol import parse_tool_name, selector_messages


@dataclass(frozen=True)
class ToolDecision:
    tool: str
    source: str


class ToolSelector:
    """Protocol-like base class to keep the agent testable without ML packages."""
    def select(self, *, state: str, task: str, specification: dict | None,
               plan: dict | None, feedback: object) -> ToolDecision:
        raise NotImplementedError


class OpenAICompatibleToolSelector(ToolSelector):
    """Adapter for a Colab-served LoRA adapter (OpenAI Chat Completions API)."""
    def __init__(self, client, include_context=True):
        self.client = client
        self.include_context = include_context

    def select(self, *, state, task, specification, plan, feedback):
        # Keep the production input aligned with the published dataset schema and
        # deliberately cap feedback: logs are not trusted instructions.
        messages = selector_messages(
            state=state, task=task, specification=specification, plan=plan,
            feedback=feedback, include_context=self.include_context,
        )
        try:
            tool = parse_tool_name(self.client.complete(messages))
        except (ValueError, TypeError) as exc:
            raise ModelError("Resposta inválida do seletor especializado") from exc
        return ToolDecision(tool=tool, source="specialized")


class FixedToolSelector(ToolSelector):
    """Seletor determinístico para testes e para reproduzir avaliações locais."""
    def __init__(self, decisions):
        self._decisions = iter(decisions)

    def select(self, **_):
        tool = next(self._decisions)
        if tool not in TOOLS:
            raise ModelError("Ferramenta de fixture não permitida")
        return ToolDecision(tool=tool, source="fixture")
