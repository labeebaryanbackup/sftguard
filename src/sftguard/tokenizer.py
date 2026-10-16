"""Tokenizer-independent assistant-mask inspection contracts and fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

FIXTURE_FIELD = "_sftguard"


@dataclass(frozen=True)
class InspectionSignal:
    signal: str
    severity: str


@dataclass(frozen=True)
class MaskInspection:
    available: bool
    signals: tuple[InspectionSignal, ...] = ()
    reason: str | None = None


class MaskInspector(Protocol):
    def inspect(self, record: dict[str, Any]) -> MaskInspection:
        """Inspect rendered tokens without returning their text."""


class FixtureMaskInspector:
    """Inspect a deterministic token/mask fixture embedded in a JSONL record.

    Real tokenizer integrations can implement :class:`MaskInspector` and supply
    the same semantic output. The fixture deliberately contains token IDs and
    role labels only; audit artifacts never copy either.
    """

    _ROLES = {"system", "user", "assistant", "tool"}

    def inspect(self, record: dict[str, Any]) -> MaskInspection:
        raw = record.get(FIXTURE_FIELD)
        if raw is None:
            return MaskInspection(available=False, reason="assistant_mask_unavailable")
        if not isinstance(raw, dict):
            return MaskInspection(available=False, reason="mask_fixture_invalid")

        token_ids = raw.get("token_ids")
        token_roles = raw.get("token_roles")
        loss_mask = raw.get("loss_mask")
        eos_token_id = raw.get("eos_token_id")
        original_assistant_tokens = raw.get("original_assistant_tokens")
        truncated = raw.get("truncated", False)

        valid = (
            isinstance(token_ids, list)
            and isinstance(token_roles, list)
            and isinstance(loss_mask, list)
            and len(token_ids) == len(token_roles) == len(loss_mask)
            and all(isinstance(token, int) and not isinstance(token, bool) for token in token_ids)
            and all(isinstance(role, str) and role in self._ROLES for role in token_roles)
            and all(isinstance(masked, bool) for masked in loss_mask)
            and isinstance(eos_token_id, int)
            and not isinstance(eos_token_id, bool)
            and isinstance(original_assistant_tokens, int)
            and not isinstance(original_assistant_tokens, bool)
            and original_assistant_tokens >= 0
            and isinstance(truncated, bool)
        )
        if not valid:
            return MaskInspection(available=False, reason="mask_fixture_invalid")

        signals: set[InspectionSignal] = set()
        if any(
            masked and role != "assistant"
            for masked, role in zip(loss_mask, token_roles, strict=True)
        ):
            signals.add(InspectionSignal("prompt_token_supervised", "critical"))

        supervised_assistant = [
            index
            for index, (masked, role) in enumerate(zip(loss_mask, token_roles, strict=True))
            if masked and role == "assistant"
        ]
        assistant_positions = [
            index for index, role in enumerate(token_roles) if role == "assistant"
        ]
        if truncated and original_assistant_tokens > 0 and not supervised_assistant:
            signals.add(InspectionSignal("assistant_fully_truncated", "critical"))
        elif assistant_positions and token_ids[assistant_positions[-1]] != eos_token_id:
            signals.add(InspectionSignal("missing_eos", "error"))

        return MaskInspection(
            available=True,
            signals=tuple(sorted(signals, key=lambda item: (item.signal, item.severity))),
        )
