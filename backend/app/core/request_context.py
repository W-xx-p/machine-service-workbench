from __future__ import annotations

from contextvars import ContextVar, Token


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(value: str) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()
