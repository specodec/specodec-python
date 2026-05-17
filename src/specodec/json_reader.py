from __future__ import annotations

import base64
import struct


class SCodecError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class JsonReader:
    def __init__(self, data: bytes) -> None:
        self._src = data.decode("utf-8")
        self._pos = 0
        self._first_field: list[bool] = []
        self._first_elem: list[bool] = []

    @property
    def pos(self) -> int:
        return self._pos

    def _ws(self) -> None:
        while self._pos < len(self._src):
            c = ord(self._src[self._pos])
            if c in (0x20, 0x09, 0x0A, 0x0D):
                self._pos += 1
            else:
                break

    def _peek(self) -> str:
        self._ws()
        if self._pos >= len(self._src):
            raise SCodecError("internal", "json: unexpected end of input")
        return self._src[self._pos]

    def _read(self) -> str:
        self._ws()
        if self._pos >= len(self._src):
            raise SCodecError("internal", "json: unexpected end of input")
        c = self._src[self._pos]
        self._pos += 1
        return c

    def _expect(self, ch: str) -> None:
        got = self._read()
        if got != ch:
            raise SCodecError(
                "internal", f"json: expected '{ch}', got '{got}' at {self._pos - 1}"
            )

    def _parse_string(self) -> str:
        self._expect('"')
        parts: list[str] = []
        while self._pos < len(self._src):
            c = self._src[self._pos]
            code = ord(c)
            if code == 0x22:
                self._pos += 1
                return "".join(parts)
            if code == 0x5C:
                self._pos += 1
                if self._pos >= len(self._src):
                    raise SCodecError(
                        "internal", "json: unexpected end of string escape"
                    )
                esc = self._src[self._pos]
                esc_code = ord(esc)
                if esc_code == 0x22:
                    parts.append('"')
                    self._pos += 1
                elif esc_code == 0x5C:
                    parts.append("\\")
                    self._pos += 1
                elif esc_code == 0x2F:
                    parts.append("/")
                    self._pos += 1
                elif esc_code == 0x62:
                    parts.append("\b")
                    self._pos += 1
                elif esc_code == 0x66:
                    parts.append("\f")
                    self._pos += 1
                elif esc_code == 0x6E:
                    parts.append("\n")
                    self._pos += 1
                elif esc_code == 0x72:
                    parts.append("\r")
                    self._pos += 1
                elif esc_code == 0x74:
                    parts.append("\t")
                    self._pos += 1
                elif esc_code == 0x75:
                    self._pos += 1
                    if self._pos + 4 > len(self._src):
                        raise SCodecError("internal", "json: incomplete unicode escape")
                    hex_str = self._src[self._pos : self._pos + 4]
                    try:
                        cp = int(hex_str, 16)
                    except ValueError:
                        raise SCodecError(
                            "internal", f"json: invalid unicode escape \\u{hex_str}"
                        )
                    self._pos += 4
                    if 0xD800 <= cp <= 0xDBFF:
                        if (
                            self._pos + 6 <= len(self._src)
                            and self._src[self._pos] == "\\"
                            and self._src[self._pos + 1] == "u"
                        ):
                            self._pos += 2
                            hex2 = self._src[self._pos : self._pos + 4]
                            try:
                                low = int(hex2, 16)
                            except ValueError:
                                raise SCodecError(
                                    "internal", f"json: invalid low surrogate \\u{hex2}"
                                )
                            self._pos += 4
                            if 0xDC00 <= low <= 0xDFFF:
                                cp = 0x10000 + (cp - 0xD800) * 0x400 + (low - 0xDC00)
                            else:
                                raise SCodecError(
                                    "internal",
                                    "json: expected low surrogate after high surrogate",
                                )
                        else:
                            raise SCodecError(
                                "internal",
                                "json: expected low surrogate after high surrogate",
                            )
                    parts.append(chr(cp))
                else:
                    raise SCodecError(
                        "internal", f"json: invalid escape character '\\{esc}'"
                    )
            elif code < 0x20:
                raise SCodecError(
                    "internal", f"json: unescaped control character U+{code:04X}"
                )
            else:
                parts.append(c)
                self._pos += 1
        raise SCodecError("internal", "json: unterminated string")

    def _parse_number_raw(self) -> str:
        self._ws()
        start = self._pos
        if self._pos < len(self._src) and self._src[self._pos] == "-":
            self._pos += 1
        if self._pos >= len(self._src):
            raise SCodecError("internal", "json: unexpected end of number")
        if self._src[self._pos] == "0":
            self._pos += 1
        elif "1" <= self._src[self._pos] <= "9":
            self._pos += 1
            while self._pos < len(self._src) and "0" <= self._src[self._pos] <= "9":
                self._pos += 1
        else:
            raise SCodecError("internal", "json: invalid number")
        if self._pos < len(self._src) and self._src[self._pos] == ".":
            self._pos += 1
            if self._pos >= len(self._src) or not ("0" <= self._src[self._pos] <= "9"):
                raise SCodecError("internal", "json: invalid number fraction")
            while self._pos < len(self._src) and "0" <= self._src[self._pos] <= "9":
                self._pos += 1
        if self._pos < len(self._src) and self._src[self._pos] in ("e", "E"):
            self._pos += 1
            if self._pos < len(self._src) and self._src[self._pos] in ("+", "-"):
                self._pos += 1
            if self._pos >= len(self._src) or not ("0" <= self._src[self._pos] <= "9"):
                raise SCodecError("internal", "json: invalid number exponent")
            while self._pos < len(self._src) and "0" <= self._src[self._pos] <= "9":
                self._pos += 1
        return self._src[start : self._pos]

    def read_string(self) -> str:
        return self._parse_string()

    def read_bool(self) -> bool:
        ch = self._peek()
        if ch == "t":
            for c in "true":
                if self._read() != c:
                    raise SCodecError("internal", "json: expected 'true'")
            return True
        if ch == "f":
            for c in "false":
                if self._read() != c:
                    raise SCodecError("internal", "json: expected 'false'")
            return False
        raise SCodecError("internal", f"json: expected bool, got '{ch}'")

    def read_int32(self) -> int:
        raw = self._parse_number_raw()
        try:
            v = int(raw)
        except ValueError:
            raise SCodecError("internal", f"json: invalid int32: {raw}")
        if v < -2147483648 or v > 2147483647:
            raise SCodecError("internal", f"json: int32 overflow: {raw}")
        return v

    def read_int64(self) -> int:
        ch = self._peek()
        if ch == '"':
            s = self._parse_string()
            try:
                return int(s)
            except ValueError:
                raise SCodecError("internal", f"json: invalid int64: {s}")
        raw = self._parse_number_raw()
        try:
            return int(raw)
        except ValueError:
            raise SCodecError("internal", f"json: invalid int64: {raw}")

    def read_uint32(self) -> int:
        raw = self._parse_number_raw()
        try:
            v = int(raw)
        except ValueError:
            raise SCodecError("internal", f"json: invalid uint32: {raw}")
        if v < 0 or v > 4294967295:
            raise SCodecError("internal", f"json: uint32 overflow: {raw}")
        return v

    def read_uint64(self) -> int:
        ch = self._peek()
        if ch == '"':
            s = self._parse_string()
            try:
                return int(s)
            except ValueError:
                raise SCodecError("internal", f"json: invalid uint64: {s}")
        raw = self._parse_number_raw()
        try:
            return int(raw)
        except ValueError:
            raise SCodecError("internal", f"json: invalid uint64: {raw}")

    def read_float32(self) -> float:
        ch = self._peek()
        if ch == '"':
            s = self._parse_string()
            if s == "NaN":
                return float("nan")
            if s == "Infinity":
                return float("inf")
            if s == "-Infinity":
                return float("-inf")
            try:
                v = float(s)
                return struct.unpack("f", struct.pack("f", v))[0]
            except ValueError:
                raise SCodecError("internal", f"json: invalid float32: {s}")
        raw = self._parse_number_raw()
        try:
            v = float(raw)
            return struct.unpack("f", struct.pack("f", v))[0]
        except ValueError:
            raise SCodecError("internal", f"json: invalid float32: {raw}")

    def read_float64(self) -> float:
        ch = self._peek()
        if ch == '"':
            s = self._parse_string()
            if s == "NaN":
                return float("nan")
            if s == "Infinity":
                return float("inf")
            if s == "-Infinity":
                return float("-inf")
            try:
                return float(s)
            except ValueError:
                raise SCodecError("internal", f"json: invalid float64: {s}")
        raw = self._parse_number_raw()
        try:
            return float(raw)
        except ValueError:
            raise SCodecError("internal", f"json: invalid float64: {raw}")

    def read_null(self) -> None:
        for c in "null":
            if self._read() != c:
                raise SCodecError("internal", "json: expected 'null'")

    def read_bytes(self) -> bytes:
        s = self._parse_string()
        return base64.b64decode(s)

    def read_enum(self) -> str:
        return self._parse_string()

    def begin_object(self) -> None:
        self._expect("{")
        self._first_field.append(True)

    def has_next_field(self) -> bool:
        ch = self._peek()
        if ch == "}":
            self._first_field.pop()
            return False
        if not self._first_field[-1]:
            if ch != ",":
                raise SCodecError("internal", f"json: expected ',' or '}}', got '{ch}'")
            self._pos += 1
        else:
            self._first_field[-1] = False
        return True

    def read_field_name(self) -> str:
        key = self._parse_string()
        self._ws()
        if self._pos < len(self._src) and self._src[self._pos] == ":":
            self._pos += 1
        else:
            raise SCodecError(
                "internal", f"json: expected ':' after field name '{key}'"
            )
        self._ws()
        return key

    def end_object(self) -> None:
        self._expect("}")

    def begin_array(self) -> None:
        self._expect("[")
        self._first_elem.append(True)

    def has_next_element(self) -> bool:
        ch = self._peek()
        if ch == "]":
            self._first_elem.pop()
            return False
        if not self._first_elem[-1]:
            if ch != ",":
                raise SCodecError("internal", f"json: expected ',' or ']', got '{ch}'")
            self._pos += 1
        else:
            self._first_elem[-1] = False
        return True

    def end_array(self) -> None:
        self._expect("]")

    def is_null(self) -> bool:
        ch = self._peek()
        return ch == "n"

    def skip(self) -> None:
        self._ws()
        if self._pos >= len(self._src):
            raise SCodecError("internal", "json: unexpected end of input")
        ch = self._src[self._pos]
        if ch == '"':
            self._pos += 1
            while self._pos < len(self._src):
                code = ord(self._src[self._pos])
                if code == 0x5C:
                    self._pos += 2
                elif code == 0x22:
                    self._pos += 1
                    return
                else:
                    self._pos += 1
            raise SCodecError("internal", "json: unterminated string in skip")
        elif ch == "{":
            self.begin_object()
            while self.has_next_field():
                self.read_field_name()
                self.skip()
            self.end_object()
        elif ch == "[":
            self.begin_array()
            while self.has_next_element():
                self.skip()
            self.end_array()
        elif ch == "t":
            for c in "true":
                if self._read() != c:
                    raise SCodecError("internal", "json: skip expected true")
        elif ch == "f":
            for c in "false":
                if self._read() != c:
                    raise SCodecError("internal", "json: skip expected false")
        elif ch == "n":
            for c in "null":
                if self._read() != c:
                    raise SCodecError("internal", "json: skip expected null")
        elif ("0" <= ch <= "9") or ch == "-":
            self._parse_number_raw()
        else:
            raise SCodecError("internal", f"json: unexpected '{ch}' in skip")
