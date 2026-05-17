#!/usr/bin/env python3
"""Generate expanded Ryu tests — FULL version with 2687 test cases."""

from __future__ import annotations
import math, os, struct, random, sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(THIS_DIR, "expanded")
os.makedirs(OUT_DIR, exist_ok=True)

sys.path.insert(0, os.path.join(THIS_DIR, "..", "..", "src"))
from specodec.ryu import float32_to_string as f32_fmt
from specodec.ryu import float64_to_string as f64_fmt


def f32_bits(b):
    return struct.unpack("f", struct.pack("I", b & 0xFFFFFFFF))[0]


def f64_bits(b):
    return struct.unpack("d", struct.pack("Q", b))[0]


# ── CORE: Parse existing test file values ──


def parse_existing_input(path):
    """Read test_cases file, return list of float values."""
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                vals.append(float(line.split()[0]))
            except ValueError:
                if "nan" in line.lower():
                    vals.append(float("nan"))
                elif "inf" in line.lower():
                    vals.append(float("-inf" if line.startswith("-") else "inf"))
    return vals


def parse_existing_output(path):
    """Read expected file, return list of strings."""
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            vals.append(line.split()[0])
    return vals


def read_existing(path_in, path_out):
    """Read and zip input/expected pairs."""
    vin = parse_existing_input(path_in)
    vout = parse_existing_output(path_out)
    # Truncate longer list to match shorter (extra expected lines are comments/empty)
    n = min(len(vin), len(vout))
    if len(vin) != len(vout):
        print(f"  Note: trimming {path_in}: {len(vin)} vs {len(vout)}")
    return list(zip(vin[:n], vout[:n]))


# ── Collect all new test cases ──

cases = []  # list of (float_value, format_fn, description)


def add(v, fn, desc):
    cases.append((v, fn, desc))


# ---- FLOAT32 ----

# 1. Existing original + table coverage (already in files, skip - we merge at end)

# 2. IEEE 754 special bit patterns (NaN/Inf/0 variants)
for label, bits in [
    ("+0", 0x00000000),
    ("-0", 0x80000000),
    ("+Inf", 0x7F800000),
    ("-Inf", 0xFF800000),
    ("QNaN", 0x7FC00000),
    ("-QNaN", 0xFFC00000),
    ("SNaN", 0x7F800001),
    ("-SNaN", 0xFF800001),
    ("NaN_max_payload", 0x7FFFFFFF),
]:
    v = f32_bits(bits)
    add(v, f32_fmt, f"special: {label} 0x{bits:08X}")

# 3. Subnormal staircase
for bits in [
    0x00000001,
    0x00000002,
    0x00000003,
    0x0000000F,
    0x00000010,
    0x000000FF,
    0x00000100,
    0x00000FFF,
    0x00001000,
    0x000FFFFF,
    0x00100000,
    0x003FFFFF,
    0x00400000,
    0x007FFFFF,
]:
    v = f32_bits(bits)
    add(v, f32_fmt, f"subnormal: 0x{bits:08X}")

# 4. Normal range sweep (every 20th exponent, 3 mantissa values)
for exp in range(1, 255, 20):
    for mantissa in [0, 0x400000, 0x7FFFFF]:
        bits = (exp << 23) | mantissa
        v = f32_bits(bits)
        add(v, f32_fmt, f"normal: 0x{bits:08X}")
        add(f32_bits(bits | 0x80000000), f32_fmt, f"normal: 0x{bits | 0x80000000:08X}")

# 5. Rounding edges near powers of 10
for p10 in [1e-30, 1e-20, 1e-10, 1e0, 1e10, 1e20]:
    for sign in [1, -1]:
        v = p10 * sign
        add(v, f32_fmt, f"rounding: {v}")
        add(v + v * 1e-7, f32_fmt, f"rounding: {v}+eps")
        add(v - v * 1e-7, f32_fmt, f"rounding: {v}-eps")

# 6. BUGGY BRANCH TARGET: e2 >= 0, q <= 9, mv % 5 may be 0
# These are values that exercise the specific code path where
# C#/F#/C++/Dart have the accept_bounds bug
bug_vals = [
    1.0,
    2.0,
    3.0,
    5.0,
    7.0,
    10.0,
    11.0,
    13.0,
    17.0,
    19.0,
    25.0,
    100.0,
    125.0,
    625.0,
    1000.0,
    5000.0,
    10000.0,
    9.999999,
    9.9999999,
    10.000001,
    10.0000001,
    99.99999,
    100.00001,
    999.9999,
    1000.0001,
    9999.999,
    10000.001,
    1.25,
    2.5,
    5.0,
    125.0,
    0.625,
    0.3125,
    0.15625,
]
for v in bug_vals:
    add(v, f32_fmt, f"bugbranch: {v}")
    add(-v, f32_fmt, f"bugbranch: -{v}")

# 7. Integer sweep near buggy branch range (1 to 100000)
for i in (
    list(range(1, 100, 2))
    + list(range(100, 1000, 10))
    + list(range(1000, 10000, 50))
    + list(range(99900, 100001))
):
    add(float(i), f32_fmt, f"bugbranch_int: {i}")
    add(float(-i), f32_fmt, f"bugbranch_int: -{i}")

# 8. Digit boundary values
for n in [9, 99, 999, 9999, 99999, 999999, 9999999, 99999999, 999999999]:
    add(float(n), f32_fmt, f"digit_boundary: {n}")
    add(float(n + 1), f32_fmt, f"digit_boundary: {n + 1}")

# 9. Random f32 bit patterns (400)
random.seed(42)
for i in range(400):
    bits = random.randint(0, 0xFFFFFFFF)
    v = f32_bits(bits)
    if not (math.isnan(v) or math.isinf(v)):
        add(v, f32_fmt, f"random_f32: 0x{bits:08X}")

# 10. Near f32 max/min values
for delta in range(-5, 6):
    add(f32_bits(0x7F7FFFFF + delta), f32_fmt, f"f32_max: {delta:+d}")
    add(f32_bits(0x00800000 + delta), f32_fmt, f"f32_min_normal: {delta:+d}")

# ---- FLOAT64 ----

# 11. IEEE 754 special
for label, bits in [
    ("+0", 0x0000000000000000),
    ("-0", 0x8000000000000000),
    ("+Inf", 0x7FF0000000000000),
    ("-Inf", 0xFFF0000000000000),
    ("QNaN", 0x7FF8000000000000),
    ("-QNaN", 0xFFF8000000000000),
    ("SNaN", 0x7FF0000000000001),
    ("-SNaN", 0xFFF0000000000001),
]:
    v = f64_bits(bits)
    add(v, f64_fmt, f"f64_special: {label} 0x{bits:016X}")

# 12. f64 subnormal staircase
for bits in [
    0x0000000000000001,
    0x0000000000000002,
    0x000000000000000F,
    0x00000000000000FF,
    0x0000000000000FFF,
    0x000000000000FFFF,
    0x00000000000FFFFF,
    0x00000000FFFFFFFF,
    0x00000FFFFFFFFFFF,
    0x000FFFFFFFFFFFFF,
]:
    v = f64_bits(bits)
    add(v, f64_fmt, f"f64_subnormal: 0x{bits:016X}")

# 13. f64 normal sweep
for exp in range(1, 2047, 100):
    for mantissa in [0, 0x8000000000000, 0xFFFFFFFFFFFFF]:
        bits = (exp << 52) | mantissa
        add(f64_bits(bits), f64_fmt, f"f64_normal: 0x{bits:016X}")

# 14. f64 2^53 boundary (integer precision limit)
for delta in range(-10, 11):
    v = 9007199254740992.0 + delta
    add(v, f64_fmt, f"f64_2p53: +{delta}")

# 15. f64 rounding edges (powers of 10 across range)
for p10 in [1e-300, 1e-200, 1e-100, 1e-50, 1e0, 1e50, 1e100, 1e200, 1e300]:
    for sign in [1, -1]:
        v = p10 * sign
        add(v, f64_fmt, f"f64_rounding: {v}")
        add(v + abs(v) * 1e-15, f64_fmt, f"f64_rounding: {v}+eps")
        add(v - abs(v) * 1e-15, f64_fmt, f"f64_rounding: {v}-eps")

# 16. f64 digit boundary (17-digit)
for n in [9999999999999999, 10000000000000000, 99999999999999999]:
    add(float(n), f64_fmt, f"f64_digit_boundary: {n}")

# 17. Random f64 (300)
random.seed(456)
for i in range(300):
    bits = random.randint(0, 0xFFFFFFFFFFFFFFFF)
    v = f64_bits(bits)
    if not (math.isnan(v) or math.isinf(v)):
        add(v, f64_fmt, f"f64_random: 0x{bits:016X}")

# 18. f64 near max
for delta in range(-5, 6):
    add(f64_bits(0x7FEFFFFFFFFFFFFF + delta), f64_fmt, f"f64_max: {delta:+d}")
    add(f64_bits(0x0010000000000000 + delta), f64_fmt, f"f64_min_normal: {delta:+d}")

# 19. f64 near subnormal boundary
for delta in range(-3, 4):
    bits = 0x0010000000000000 + delta
    add(f64_bits(bits), f64_fmt, f"f64_subnormal_boundary: 0x{bits:016X}")

# ── Deduplicate (keep existing values as authoritative) ──

existing_f32 = read_existing(
    os.path.join(THIS_DIR, "test_cases_f32.txt"),
    os.path.join(THIS_DIR, "expected_f32.txt"),
)
existing_f32_table = read_existing(
    os.path.join(THIS_DIR, "test_cases_table_coverage.txt"),
    os.path.join(THIS_DIR, "expected_table_coverage.txt"),
)
existing_f64 = read_existing(
    os.path.join(THIS_DIR, "test_cases_f64.txt"),
    os.path.join(THIS_DIR, "expected_f64.txt"),
)
existing_f64_table = read_existing(
    os.path.join(THIS_DIR, "test_cases_f64_table_coverage.txt"),
    os.path.join(THIS_DIR, "expected_f64_table_coverage.txt"),
)


# Build set of existing values (using raw bits for dedup)
def key(f):
    if math.isnan(f):
        return ("nan", struct.pack("d", f))
    if f == 0.0:
        return struct.pack("d", f)  # distinguish +0 from -0
    return f


existing_keys = set()
for v, _ in existing_f32 + existing_f32_table + existing_f64 + existing_f64_table:
    existing_keys.add(key(v))

# Filter new cases
new_f32 = []
new_f64 = []
for v, fn, desc in cases:
    if key(v) in existing_keys:
        continue
    existing_keys.add(key(v))  # also dedup between new cases
    if fn is f32_fmt:
        new_f32.append((v, desc))
    else:
        new_f64.append((v, desc))

# ── Write output files ──


def write_file(path, pairs, fmt_fn):
    """Write test_cases and expected files — NO inline comments."""
    inp = os.path.join(OUT_DIR, path)
    exp = os.path.join(OUT_DIR, path.replace("test_cases_", "expected_"))
    with open(inp, "w") as fi, open(exp, "w") as fe:
        for v, desc in pairs:
            # Normalize NaN/Inf in input to standard case
            if math.isnan(v):
                fi.write("NaN\n")
            elif v == float("inf"):
                fi.write("Infinity\n")
            elif v == float("-inf"):
                fi.write("-Infinity\n")
            elif v == 0.0 and struct.pack("d", v) == b"\x00" * 8:
                fi.write("0.0\n")
            elif v == -0.0:
                fi.write("-0.0\n")
            else:
                fi.write(f"{v}\n")
            try:
                fe.write(f"{fmt_fn(v)}\n")
            except Exception:
                fe.write("NONE\n")


# Merge: existing → table coverage → new expanded
all_f32 = list(existing_f32)
all_f32.extend(existing_f32_table)
all_f32.extend([(v, desc) for v, desc in new_f32])
write_file("test_cases_f32_expanded.txt", all_f32, f32_fmt)

all_f64 = list(existing_f64)
all_f64.extend(existing_f64_table)
all_f64.extend([(v, desc) for v, desc in new_f64])
write_file("test_cases_f64_expanded.txt", all_f64, f64_fmt)

print(
    f"Float32: {len(existing_f32)} original + {len(existing_f32_table)} table + {len(new_f32)} new = {len(all_f32)} total"
)
print(
    f"Float64: {len(existing_f64)} original + {len(existing_f64_table)} table + {len(new_f64)} new = {len(all_f64)} total"
)
print(f"TOTAL: {len(all_f32) + len(all_f64)} tests")
print(f"\nFiles in {OUT_DIR}/")
for f in sorted(os.listdir(OUT_DIR)):
    lines = len(open(os.path.join(OUT_DIR, f)).readlines())
    print(f"  {f}: {lines} lines")
