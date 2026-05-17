import sys, os, math

BASE = os.path.dirname(__file__)
SRC = os.path.join(BASE, "..", "..", "src")
sys.path.insert(0, SRC)

from specodec.ryu.ryu_f32 import float32_to_string
from specodec.ryu.ryu_f64 import float64_to_string


def load_tests(filename):
    with open(os.path.join(BASE, filename)) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def load_expected(filename):
    with open(os.path.join(BASE, filename)) as f:
        return [l.strip() for l in f if l.strip()]


def load_coverage(filename):
    with open(os.path.join(BASE, filename)) as f:
        return [l.strip() for l in f if l.strip() and l[0].isdigit()]


passed = 0
failed = 0

print("=== Float32 Original (125 tests) ===")
f32_in = load_tests("test_cases_f32.txt")
f32_exp = load_expected("expected_f32.txt")
for i in range(min(len(f32_in), len(f32_exp))):
    result = float32_to_string(float(f32_in[i]))
    if result == f32_exp[i]:
        passed += 1
    else:
        failed += 1
        if failed <= 5:
            print(f"FAIL: {f32_in[i]} => {result} (expected {f32_exp[i]})")
print(f"{passed}/{len(f32_in)}\n")

print("=== Float64 Original (102 tests) ===")
f64_in = load_tests("test_cases_f64.txt")
f64_exp = load_expected("expected_f64.txt")
f64_pass = 0
for i in range(min(len(f64_in), len(f64_exp))):
    result = float64_to_string(float(f64_in[i]))
    if result == f64_exp[i]:
        f64_pass += 1
        passed += 1
    else:
        failed += 1
        if failed <= 5:
            print(f"FAIL: {f64_in[i]} => {result} (expected {f64_exp[i]})")
print(f"{f64_pass}/{len(f64_in)}\n")

print("=== Float32 Coverage (78 tests) ===")
cov32_in = load_coverage("test_cases_table_coverage.txt")
cov32_exp = load_expected("expected_table_coverage.txt")
cov32_pass = 0
for i in range(min(len(cov32_in), len(cov32_exp))):
    val = float(cov32_in[i].split("#")[0].strip())
    result = float32_to_string(val)
    if result == cov32_exp[i]:
        cov32_pass += 1
        passed += 1
    else:
        failed += 1
        if failed <= 5:
            print(
                f"FAIL: {cov32_in[i].split('#')[0].strip()} => {result} (expected {cov32_exp[i]})"
            )
print(f"{cov32_pass}/{min(len(cov32_in), len(cov32_exp))}\n")

print("=== Float64 Coverage (616 tests) ===")
cov64_in = load_coverage("test_cases_f64_table_coverage.txt")
cov64_exp = load_expected("expected_f64_table_coverage.txt")
cov64_pass = 0
for i in range(min(len(cov64_in), len(cov64_exp))):
    val = float(cov64_in[i].split("#")[0].strip())
    result = float64_to_string(val)
    if result == cov64_exp[i]:
        cov64_pass += 1
        passed += 1
    else:
        failed += 1
        if failed <= 5:
            print(
                f"FAIL: {cov64_in[i].split('#')[0].strip()} => {result} (expected {cov64_exp[i]})"
            )
print(f"{cov64_pass}/{min(len(cov64_in), len(cov64_exp))}\n")

print(f"=== TOTAL: {passed}/{passed + failed} ===")
sys.exit(1 if failed > 0 else 0)
