from __future__ import annotations

import struct


class GronReader:
    def __init__(self, data: bytes):
        self._lines: list[tuple[str, str]] = []
        self._cursor: int = 0
        self._ctx: list[dict] = []
        text = data.decode("utf-8")
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            eq = line.find(" = ")
            if eq < 0:
                continue
            path = line[:eq]
            val = line[eq + 3 :]
            if val.endswith(";"):
                val = val[:-1]
            self._lines.append((path, val))

    @staticmethod
    def _unescape(s: str) -> str:
        if len(s) < 2 or s[0] != '"' or s[-1] != '"':
            raise ValueError("gron: expected quoted string")
        r = []
        i = 1
        while i < len(s) - 1:
            if s[i] == "\\":
                i += 1
                c = s[i]
                if c == '"':
                    r.append('"')
                elif c == "\\":
                    r.append("\\")
                elif c == "/":
                    r.append("/")
                elif c == "b":
                    r.append("\b")
                elif c == "f":
                    r.append("\f")
                elif c == "n":
                    r.append("\n")
                elif c == "r":
                    r.append("\r")
                elif c == "t":
                    r.append("\t")
                elif c == "u":
                    r.append(chr(int(s[i + 1 : i + 5], 16)))
                    i += 4
            else:
                r.append(s[i])
            i += 1
        return "".join(r)

    @staticmethod
    def _b64(s: str) -> bytes:
        import base64

        return base64.b64decode(s)

    def read_string(self) -> str:
        v = self._unescape(self._lines[self._cursor][1])
        self._cursor += 1
        return v

    def read_bool(self) -> bool:
        v = self._lines[self._cursor][1] == "true"
        self._cursor += 1
        return v

    def read_int32(self) -> int:
        v = int(self._lines[self._cursor][1])
        self._cursor += 1
        return v

    def read_int64(self) -> int:
        v = int(self._unescape(self._lines[self._cursor][1]))
        self._cursor += 1
        return v

    def read_uint32(self) -> int:
        v = int(self._lines[self._cursor][1])
        self._cursor += 1
        return v

    def read_uint64(self) -> int:
        v = int(self._unescape(self._lines[self._cursor][1]))
        self._cursor += 1
        return v

    def read_float32(self) -> float:
        v = self._lines[self._cursor][1]
        self._cursor += 1
        if v == '"NaN"':
            return float("nan")
        if v == '"Infinity"':
            return float("inf")
        if v == '"-Infinity"':
            return float("-inf")
        f = float(v)
        return struct.unpack("f", struct.pack("f", f))[0]

    def read_float64(self) -> float:
        v = self._lines[self._cursor][1]
        self._cursor += 1
        if v == '"NaN"':
            return float("nan")
        if v == '"Infinity"':
            return float("inf")
        if v == '"-Infinity"':
            return float("-inf")
        return float(v)

    def read_null(self):
        v = self._lines[self._cursor][1]
        self._cursor += 1
        if v != "null":
            raise ValueError("gron: expected null")

    def read_bytes(self) -> bytes:
        v = self._b64(self._unescape(self._lines[self._cursor][1]))
        self._cursor += 1
        return v

    def begin_object(self):
        line = self._lines[self._cursor]
        self._cursor += 1
        self._ctx.append({"prefix": line[0], "type": "object"})

    def has_next_field(self) -> bool:
        if self._cursor >= len(self._lines):
            return False
        pfx = self._ctx[-1]["prefix"] + "."
        p = self._lines[self._cursor][0]
        if not p.startswith(pfx):
            return False
        rem = p[len(pfx) :]
        return "." not in rem and "[" not in rem

    def read_field_name(self) -> str:
        pfx = self._ctx[-1]["prefix"] + "."
        return self._lines[self._cursor][0][len(pfx) :]

    def end_object(self):
        self._ctx.pop()

    def begin_array(self):
        line = self._lines[self._cursor]
        self._cursor += 1
        self._ctx.append({"prefix": line[0], "type": "array", "index": -1})

    def has_next_element(self) -> bool:
        if self._cursor >= len(self._lines):
            return False
        arr = self._ctx[-1]
        ni = arr["index"] + 1
        exp = f"{arr['prefix']}[{ni}]"
        p = self._lines[self._cursor][0]
        has_next = p == exp or p.startswith(exp + ".") or p.startswith(exp + "[")
        if has_next:
            arr["index"] = ni
        return has_next

    def end_array(self):
        self._ctx.pop()

    def is_null(self) -> bool:
        return (
            self._cursor < len(self._lines) and self._lines[self._cursor][1] == "null"
        )

    def skip(self):
        sp = self._lines[self._cursor][0]
        self._cursor += 1
        while self._cursor < len(self._lines):
            np = self._lines[self._cursor][0]
            if len(np) > len(sp) and (
                np.startswith(sp + ".") or np.startswith(sp + "[")
            ):
                self._cursor += 1
            else:
                break
