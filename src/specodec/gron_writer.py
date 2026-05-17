from __future__ import annotations
import struct

from .float_fmt import format_float32, format_float64


class GronWriter:
    def __init__(self):
        self._lines: list[str] = []
        self._segments: list[str] = ["json"]
        self._nesting: list[dict] = []

    def _build_path(self) -> str:
        r = self._segments[0]
        for s in self._segments[1:]:
            if s.startswith("["):
                r += s
            else:
                r += "." + s
        return r

    @staticmethod
    def _escape(s: str) -> str:
        r = []
        for c in s:
            o = ord(c)
            if o == 0x22:
                r.append('\\"')
            elif o == 0x5C:
                r.append("\\\\")
            elif o == 0x08:
                r.append("\\b")
            elif o == 0x0C:
                r.append("\\f")
            elif o == 0x0A:
                r.append("\\n")
            elif o == 0x0D:
                r.append("\\r")
            elif o == 0x09:
                r.append("\\t")
            elif o < 0x20:
                r.append(f"\\u{o:04x}")
            else:
                r.append(c)
        return "".join(r)

    @staticmethod
    def _b64(buf: bytes) -> str:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        s = []
        i = 0
        while i < len(buf):
            b0 = buf[i]
            b1 = buf[i + 1] if i + 1 < len(buf) else 0
            b2 = buf[i + 2] if i + 2 < len(buf) else 0
            s.append(chars[b0 >> 2])
            s.append(chars[((b0 & 3) << 4) | (b1 >> 4)])
            s.append(chars[((b1 & 0xF) << 2) | (b2 >> 6)] if i + 1 < len(buf) else "=")
            s.append(chars[b2 & 0x3F] if i + 2 < len(buf) else "=")
            i += 3
        return "".join(s)

    def _emit(self, raw: str):
        self._lines.append(f"{self._build_path()} = {raw};")

    def write_string(self, value: str):
        self._emit(f'"{self._escape(value)}"')

    def write_bool(self, value: bool):
        self._emit("true" if value else "false")

    def write_int32(self, value: int):
        self._emit(str(value))

    def write_int64(self, value: int):
        self._emit(f'"{value}"')

    def write_uint32(self, value: int):
        self._emit(str(value))

    def write_uint64(self, value: int):
        self._emit(f'"{value}"')

    def write_float32(self, value: float):
        f32 = struct.unpack("f", struct.pack("f", value))[0]
        if f32 != f32:
            self._emit('"NaN"')
        elif f32 == float("inf"):
            self._emit('"Infinity"')
        elif f32 == float("-inf"):
            self._emit('"-Infinity"')
        else:
            self._emit(format_float32(value))

    def write_float64(self, value: float):
        if value != value:
            self._emit('"NaN"')
        elif value == float("inf"):
            self._emit('"Infinity"')
        elif value == float("-inf"):
            self._emit('"-Infinity"')
        else:
            self._emit(format_float64(value))

    def write_null(self):
        self._emit("null")

    def write_bytes(self, value: bytes):
        self._emit(f'"{self._b64(value)}"')

    def begin_object(self, field_count: int):
        self._lines.append(f"{self._build_path()} = {{}};")
        self._nesting.append({"depth": len(self._segments)})

    def write_field(self, name: str):
        top = self._nesting[-1]
        if len(self._segments) > top["depth"]:
            self._segments[-1] = name
        else:
            self._segments.append(name)

    def end_object(self):
        info = self._nesting.pop()
        self._segments = self._segments[: info["depth"]]

    def begin_array(self, element_count: int):
        self._lines.append(f"{self._build_path()} = [];")
        self._nesting.append({"depth": len(self._segments), "array_index": -1})

    def next_element(self):
        info = self._nesting[-1]
        info["array_index"] += 1
        seg = f"[{info['array_index']}]"
        if len(self._segments) > info["depth"]:
            self._segments[-1] = seg
        else:
            self._segments.append(seg)

    def end_array(self):
        info = self._nesting.pop()
        self._segments = self._segments[: info["depth"]]

    def write_enum(self, value: str) -> None:
        self._emit(f'"{self._escape(value)}"')

    def to_bytes(self) -> bytes:
        return "\n".join(self._lines).encode("utf-8") + b"\n"
