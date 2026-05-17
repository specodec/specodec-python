import struct
from .tables_f64 import DOUBLE_POW5_INV_SPLIT, DOUBLE_POW5_SPLIT
from .ryu_math import (
    log10_pow2,
    log10_pow5,
    pow5bits,
    mul_shift_64,
    multiple_of_power_of_5_64,
    multiple_of_power_of_2_64,
    decimal_length17,
)

DOUBLE_MANTISSA_BITS = 52
DOUBLE_BIAS = 1023
DOUBLE_POW5_INV_BITCOUNT = 125
DOUBLE_POW5_BITCOUNT = 125


def float64_to_string(d):
    bits = struct.unpack(">Q", struct.pack(">d", d))[0]

    sign = (bits >> 63) != 0
    ieee_mantissa = bits & 0xFFFFFFFFFFFFF
    ieee_exponent = (bits >> 52) & 0x7FF

    if ieee_exponent == 0x7FF:
        if ieee_mantissa == 0:
            return "-Infinity" if sign else "Infinity"
        return "NaN"
    if ieee_exponent == 0 and ieee_mantissa == 0:
        return "-0E0" if sign else "0E0"

    if ieee_exponent == 0:
        e2 = 1 - DOUBLE_BIAS - DOUBLE_MANTISSA_BITS - 2
        m2 = ieee_mantissa
    else:
        e2 = ieee_exponent - DOUBLE_BIAS - DOUBLE_MANTISSA_BITS - 2
        m2 = (1 << DOUBLE_MANTISSA_BITS) | ieee_mantissa

    even = (m2 & 1) == 0
    accept_bounds = even

    mv = 4 * m2
    mp = 4 * m2 + 2
    mm_shift = 1 if (ieee_mantissa != 0 or ieee_exponent <= 1) else 0
    mm = 4 * m2 - 1 - mm_shift

    vr_is_trailing_zeros = False
    vm_is_trailing_zeros = False
    last_digit = 0

    if e2 >= 0:
        q = log10_pow2(e2)
        e10 = q
        k = DOUBLE_POW5_INV_BITCOUNT + pow5bits(q) - 1
        i = -e2 + q + k

        vr = mul_shift_64(mv, DOUBLE_POW5_INV_SPLIT[q], i)
        vp = mul_shift_64(mp, DOUBLE_POW5_INV_SPLIT[q], i)
        vm = mul_shift_64(mm, DOUBLE_POW5_INV_SPLIT[q], i)

        if q != 0 and (vp - 1) // 10 <= vm // 10:
            l = DOUBLE_POW5_INV_BITCOUNT + pow5bits(q - 1) - 1
            last_digit = (
                mul_shift_64(mv, DOUBLE_POW5_INV_SPLIT[q - 1], -e2 + q - 1 + l) % 10
            )

        if q <= 21:
            if mv % 5 == 0:
                vr_is_trailing_zeros = multiple_of_power_of_5_64(mv, q)
            elif accept_bounds:
                vm_is_trailing_zeros = multiple_of_power_of_5_64(mm, q)
            else:
                if multiple_of_power_of_5_64(mp, q):
                    vp -= 1
    else:
        q = log10_pow5(-e2)
        e10 = q + e2
        i = -e2 - q
        k = pow5bits(i) - DOUBLE_POW5_BITCOUNT
        j = q - k

        vr = mul_shift_64(mv, DOUBLE_POW5_SPLIT[i], j)
        vp = mul_shift_64(mp, DOUBLE_POW5_SPLIT[i], j)
        vm = mul_shift_64(mm, DOUBLE_POW5_SPLIT[i], j)

        if q != 0 and (vp - 1) // 10 <= vm // 10:
            j = q - 1 - (pow5bits(i + 1) - DOUBLE_POW5_BITCOUNT)
            last_digit = mul_shift_64(mv, DOUBLE_POW5_SPLIT[i + 1], j) % 10

        if q <= 1:
            vr_is_trailing_zeros = True
            if accept_bounds:
                vm_is_trailing_zeros = mm_shift == 1
            else:
                vp -= 1
        elif q < 63:
            vr_is_trailing_zeros = multiple_of_power_of_2_64(mv, q - 1)
            if accept_bounds:
                vm_is_trailing_zeros = multiple_of_power_of_5_64(mm, q)
            else:
                if multiple_of_power_of_5_64(mp, q):
                    vp -= 1

    removed = 0
    vr2, vp2, vm2 = vr, vp, vm

    if vm_is_trailing_zeros or vr_is_trailing_zeros:
        while vp2 // 10 > vm2 // 10:
            vm_is_trailing_zeros = vm_is_trailing_zeros and (vm2 % 10 == 0)
            vr_is_trailing_zeros = vr_is_trailing_zeros and (last_digit == 0)
            last_digit = vr2 % 10
            vr2 //= 10
            vp2 //= 10
            vm2 //= 10
            removed += 1

        if vm_is_trailing_zeros:
            while vm2 % 10 == 0:
                vr_is_trailing_zeros = vr_is_trailing_zeros and (last_digit == 0)
                last_digit = vr2 % 10
                vr2 //= 10
                vp2 //= 10
                vm2 //= 10
                removed += 1

        if vr_is_trailing_zeros and last_digit == 5 and vr2 % 2 == 0:
            last_digit = 4

        round_up = (
            vr2 == vm2 and (not accept_bounds or not vm_is_trailing_zeros)
        ) or last_digit >= 5
        output = vr2 + (1 if round_up else 0)
    else:
        while vp2 // 10 > vm2 // 10:
            last_digit = vr2 % 10
            vr2 //= 10
            vp2 //= 10
            vm2 //= 10
            removed += 1
        output = vr2 + (1 if (vr2 == vm2 or last_digit >= 5) else 0)

    exp = e10 + removed
    olength = decimal_length17(output)

    result = "-" if sign else ""
    digits = str(output)
    if olength == 1:
        result += digits
    else:
        result += digits[0] + "." + digits[1:]

    result += "E"
    final_exp = exp + olength - 1
    result += str(final_exp)

    return result
