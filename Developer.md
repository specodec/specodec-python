# Python Runtime — Developer Reference

> **Emitter**: `/home/ytr/Specodec/typespec-emitter-python/src/index.ts`

---

## 1. Type Mapping Table

| TypeSpec Type | Python Type | Notes |
|---|---|---|
| `string` | `str` | |
| `boolean` | `bool` | |
| `int8`, `int16`, `int32`, `int64` | `int` | Python `int` is unbounded; all map to same type |
| `uint8`, `uint16`, `uint32`, `uint64` | `int` | Same — no unsigned distinction at type level |
| `float32` | `float` | Truncated via `struct.pack('f', v)` / `struct.unpack('f', ...)` |
| `float64`, `float`, `decimal` | `float` | |
| `bytes` | `bytes` | |
| `integer` | `int` | |
| Enum | `str` | read/written as `w.write_enum(str_value)` |
| Array `<T>` | `list[T]` | |
| Record `<V>` | `dict[str, V]` | |
| Model | `@dataclass` class | |
| Union | `Union[Variant1, ...]` | typing.Union |

---

## 2. Model Representation

Models use `@dataclass`:

```python
@dataclass
class MyModel:
    name: str
    age: int
    tags: list[str] = field(default_factory=list)
```

**Required fields MUST appear before optional fields** in the dataclass definition (Python enforces this at runtime via `__init__` parameter order).

---

## 3. Optional / Nullable

- Optional: `Optional[Type] = None` (i.e., `str | None = None`)
- Required fields come first, then optional fields with defaults.
- Nullable is indistinguishable from Optional in Python type system.

---

## 4. Union Representation

Discriminated unions use `typing.Union[Variant1, Variant2, ...]`. The emitter generates per-variant `@dataclass` classes:

```python
@dataclass
class VariantA:
    _tag: ClassVar[str] = "variantA"
    value: int

MyUnion = Union[VariantA, VariantB, None]
```

Accessors are emitted as standalone functions rather than methods on the union (since Union is not a class).

---

## 5. Enum Representation

Treated as plain `str` at the type level. Enum values are written via `w.write_enum(str_value)` and read as strings. No native Python `Enum` is generated.

---

## 6. Ryu Implementation

- **Bit extraction**: `struct.pack('>f', f)` + `struct.unpack('>I', ...)` for f32; `struct.pack('>d', d)` + `struct.unpack('>Q', ...)` for f64. All big-endian.
- **`mul_shift_64`**: Implements the C algorithm manually since Python has no native 128-bit:
  1. `b0 = m * mul[0]` (Python big ints)
  2. `b0_hi = b0 >> 64` (high 64 bits)
  3. `sum_val = b0_hi + b2`
  4. `return (sum_val >> (shift - 64)) & 0xFFFFFFFFFFFFFFFF`
- **`mul_shift_32`**: Splits factor into lo/hi halves:
  ```python
  factor_lo = factor & 0xFFFFFFFF
  factor_hi = factor >> 32
  bits0 = m * factor_lo; bits1 = m * factor_hi
  sum_val = (bits0 >> 32) + bits1
  return (sum_val >> (shift - 32)) & 0xFFFFFFFF
  ```
- **Tables**: Python ints in list literals (same values as TypeScript/Go).
- **`pow5bits`**: Uses integer floor division `//`.
- **Output format**: Scientific notation `"1.234E2"`, identical to reference.

---

## 7. MsgPack Reader/Writer

**Reader** (`MsgPackReader`):
- Accumulates over `bytes` data with `_pos` cursor.
- Uses `struct.unpack_from(">H", buf, pos)` for u16, `>I` for u32, `>Q` for u64.
- `read_float32()`: calls `read_float()` then round-trips through `struct.pack('f', v)` + `struct.unpack('f', ...)`.
- `read_float64()`: returns `float(self.read_float())`.
- NaN/Infinity: passed through native float representation (msgpack native encoding).
- Container tracking: `_container_count: list[int]` for map/array nesting.

**Writer** (`MsgPackWriter`):
- Accumulates via `bytearray` + `extend(struct.pack(...))`.
- `write_int64` / `write_uint64`: uses `struct.pack(">Q", value & 0xFFFFFFFFFFFFFFFF)` for 64-bit boundary.
- `write_float32`: `struct.pack(">f", value)`.
- String encoding: `value.encode("utf-8")` for length calculation.

---

## 8. JSON Reader/Writer

**Reader** (`JsonReader`):
- Decodes bytes to `str` with `data.decode("utf-8")`.
- `_parse_string`: Handles `\uXXXX` escapes **including surrogate pairs** (`0xD800`-`0xDBFF` + `0xDC00`-`0xDFFF` → `chr(cp)` with combined codepoint calculation: `cp = 0x10000 + (cp - 0xD800) * 0x400 + (low - 0xDC00)`).
- NaN/Infinity: Detected as quoted strings → `float("nan")`, `float("inf")`, `float("-inf")`.
- `int64`/`uint64`: Supports both bare numbers and quoted string encoding.
- `read_bytes()`: Uses `base64.b64decode(s)`.
- Skipping: recursive skip for objects/arrays; string skip tracks escape sequences.

**Writer** (`JsonWriter`):
- Accumulates into `list[str]` (`_parts`), joined on `to_bytes()`.
- NaN detection: `f32 != f32` (Python's IEEE NaN comparison quirk).
- Infinity: `value == float("inf")` and `value == float("-inf")`.
- `int64`/`uint64`: emitted as quoted strings.
- `write_float32`: round-trips through `struct.pack/unpack('f')` before formatting.
- Uses `format_float32`/`format_float64` from `float_fmt.py` (Ryu).

---

## 9. Gron Reader/Writer

**Reader** (`GronReader`):
- Parses `path = value;` lines (semicolon stripped).
- Context stack: `_ctx: list[dict]` with keys `prefix`, `type`, `index`.
- `_unescape`: handles `\uXXXX` via `chr(int(s[i+1:i+5], 16))` — **no surrogate pair support**.
- `is_null()`: compares raw value to `"null"`.
- **Note**: `read_float64` is defined **twice** in the file (lines 85-93 and 95-97). The second definition overwrites the first, making NaN/Infinity handling unreachable for gron f64 reads. The effective `read_float64` only handles `"-0"` specially: `return -0.0 if v == "-0" else float(v)`.

**Writer** (`GronWriter`):
- Accumulates `list[str]` lines, path stack `_segments: list[str]` starting with `["json"]`.
- `_nesting: list[dict]` with `depth` and `array_index`.
- `beginObject` emits `path = {};`, `beginArray` emits `path = [];`.
- `int64`/`uint64`: emitted as quoted decimal strings.
- NaN/Infinity: quoted `"NaN"`, `"Infinity"`, `"-Infinity"`.
- Uses `format_float32`/`format_float64` for non-special floats.

---

## 10. State Management

- **Mutable** class-based state.
- Readers mutate `_pos` and `_first_field`/`_first_elem` stacks.
- Writers mutate internal `_parts`/`_buf` arrays.
- No immutable patterns — everything is in-place mutation.

---

## 11. SpecReader / SpecWriter Interfaces

### SpecReader (Protocol)

```python
@runtime_checkable
class SpecReader(Protocol):
    def begin_object(self) -> None: ...
    def has_next_field(self) -> bool: ...
    def read_field_name(self) -> str: ...
    def end_object(self) -> None: ...
    def begin_array(self) -> None: ...
    def has_next_element(self) -> bool: ...
    def end_array(self) -> None: ...
    def read_string(self) -> str: ...
    def read_bool(self) -> bool: ...
    def read_int32(self) -> int: ...
    def read_int64(self) -> int: ...
    def read_uint32(self) -> int: ...
    def read_uint64(self) -> int: ...
    def read_float32(self) -> float: ...
    def read_float64(self) -> float: ...
    def read_null(self) -> None: ...
    def read_bytes(self) -> bytes: ...
    def read_enum(self) -> str: ...
    def is_null(self) -> bool: ...
    def skip(self) -> None: ...
```

### SpecWriter (ABC)

```python
class SpecWriter(ABC):
    @abstractmethod
    def write_string(self, value: str) -> None: ...
    @abstractmethod
    def write_bool(self, value: bool) -> None: ...
    @abstractmethod
    def write_int32(self, value: int) -> None: ...
    @abstractmethod
    def write_int64(self, value: int) -> None: ...
    @abstractmethod
    def write_uint32(self, value: int) -> None: ...
    @abstractmethod
    def write_uint64(self, value: int) -> None: ...
    @abstractmethod
    def write_float32(self, value: float) -> None: ...
    @abstractmethod
    def write_float64(self, value: float) -> None: ...
    @abstractmethod
    def write_null(self) -> None: ...
    @abstractmethod
    def write_bytes(self, value: bytes) -> None: ...
    @abstractmethod
    def write_enum(self, value: str) -> None: ...
    @abstractmethod
    def begin_object(self, field_count: int) -> None: ...
    @abstractmethod
    def write_field(self, name: str) -> None: ...
    @abstractmethod
    def end_object(self) -> None: ...
    @abstractmethod
    def begin_array(self, element_count: int) -> None: ...
    @abstractmethod
    def next_element(self) -> None: ...
    @abstractmethod
    def end_array(self) -> None: ...
    @abstractmethod
    def to_bytes(self) -> bytes: ...
```

---

## 12. Emitter Generation Pattern

### Model encode
```python
def encode_MyModel(w: SpecWriter, obj: MyModel) -> None:
    w.begin_object(2)
    w.write_field("name")
    w.write_string(obj.name)
    w.write_field("age")
    w.write_int32(obj.age)
    w.end_object()
```

### Model decode
```python
def decode_MyModel(r: SpecReader) -> MyModel:
    r.begin_object()
    _name: str = ""
    _age: int = 0
    while r.has_next_field():
        match r.read_field_name():
            case "name":
                _name = r.read_string()
            case "age":
                _age = r.read_int32()
            case _:
                r.skip()
    r.end_object()
    return MyModel(name=_name, age=_age)
```

---

## 13. Known Quirks / Bugs

- **`gron_reader.py`**: `read_float64` defined twice (lines 85-93 for NaN/Inf, then overwritten at lines 95-97). The effective implementation only handles `"-0"` → `-0.0` and plain floats. NaN/Infinity strings in gron will cause `ValueError` (`float("NaN")` would work but the first definition is dead code).
- **`SpecCodec`** is a `@dataclass` containing callables, not a class with methods — callables are assigned during codec construction.
- `SpecReader` is a `Protocol` (structural subtyping), not an ABC — runtime checkable but no abstract enforcement.
- `SCodecError` is defined separately in `json_reader.py` and `msgpack_reader.py` (duplicate class definition — each file defines its own copy).
- `multiple_of_power_of_5_64` in ryu_math computes `5 ** q` via `**` operator (Python big ints), which is fine but slower than the iterative approach used in compiled languages.
- Gron unescape lacks surrogate pair handling (same as TypeScript baseline).

---

## 14. DevContainer

- **Base image**: `dev:all`
- **Tooling**: Python via `mise` shims (includes mypy, ruff, pytest via pip install in base image)
- **Build**: Compiles `__init__.py` and individual modules with `python -m py_compile`, then runs `python -m compileall src/specodec/`
- **Output** (`FROM scratch`): copies `/app/src/` to `/out/`
