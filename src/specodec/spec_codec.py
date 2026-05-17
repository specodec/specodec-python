from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

from .spec_reader import SpecReader
from .spec_writer import SpecWriter
from .json_reader import JsonReader
from .json_writer import JsonWriter
from .msgpack_reader import MsgPackReader
from .msgpack_writer import MsgPackWriter
from .gron_reader import GronReader
from .gron_writer import GronWriter

T = TypeVar("T")


@dataclass
class SpecCodec(Generic[T]):
    encode: Callable[[SpecWriter, T], None]
    decode: Callable[[SpecReader], T]


# ---------------------------------------------------------------------------
# FormatEntry
# ---------------------------------------------------------------------------
@dataclass
class FormatEntry:
    name: str  # e.g. "json", "msgpack", "gron"
    new_writer: Callable[..., SpecWriter]
    new_reader: Callable[[bytes], SpecReader]


# ---------------------------------------------------------------------------
# FormatRegistry
# ---------------------------------------------------------------------------
class FormatRegistry:
    def __init__(self) -> None:
        self._entries: list[FormatEntry] = []

    def register(self, entry: FormatEntry) -> "FormatRegistry":
        self._entries.append(entry)
        return self

    def match(self, format: str) -> FormatEntry:
        for e in self._entries:
            if e.name == format:
                return e
        return self._entries[0]


# ---------------------------------------------------------------------------
# Default registry
# ---------------------------------------------------------------------------
default_registry = FormatRegistry()
default_registry.register(FormatEntry("json", JsonWriter, JsonReader))  # type: ignore[arg-type]
default_registry.register(FormatEntry("msgpack", MsgPackWriter, MsgPackReader))  # type: ignore[arg-type]
default_registry.register(FormatEntry("gron", GronWriter, GronReader))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# dispatch / respond
# ---------------------------------------------------------------------------
def dispatch(
    codec: SpecCodec[T],
    body: bytes,
    format: str,
    registry: FormatRegistry | None = None,
) -> T:
    reg = registry or default_registry
    fmt = reg.match(format)
    return codec.decode(fmt.new_reader(body))


@dataclass
class RespondResult:
    body: bytes
    name: str  # format name: "json" | "msgpack" | "gron"


def respond(
    codec: SpecCodec[T], obj: T, format: str, registry: FormatRegistry | None = None
) -> RespondResult:
    reg = registry or default_registry
    fmt = reg.match(format)
    w = fmt.new_writer()
    codec.encode(w, obj)
    return RespondResult(body=w.to_bytes(), name=fmt.name)
