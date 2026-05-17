import struct
from .tables_f32 import FLOAT_POW5_INV_SPLIT, FLOAT_POW5_SPLIT
from .ryu_math import (
    log10_pow2,
    log10_pow5,
    pow5bits,
    mul_shift_32,
    multiple_of_power_of_5_32,
    multiple_of_power_of_2_32,
    decimal_length9,
)

FLOAT_MANTISSA_BITS = 23
FLOAT_BIAS = 127
FLOAT_POW5_INV_BITCOUNT = 59
FLOAT_POW5_BITCOUNT = 61


def float32_to_string(f):
    bits = struct.unpack(">I", struct.pack(">f", f))[0]

    sign = (bits >> 31) != 0
    ieee_mantissa = bits & 0x7FFFFF
    ieee_exponent = (bits >> 23) & 0xFF

    if ieee_exponent == 255:
        if ieee_mantissa == 0:
            return "-Infinity" if sign else "Infinity"
        return "NaN"
    if ieee_exponent == 0 and ieee_mantissa == 0:
        return "-0E0" if sign else "0E0"

    if ieee_exponent == 0:
        e2 = 1 - FLOAT_BIAS - FLOAT_MANTISSA_BITS - 2
        m2 = ieee_mantissa
    else:
        e2 = ieee_exponent - FLOAT_BIAS - FLOAT_MANTISSA_BITS - 2
        m2 = (1 << FLOAT_MANTISSA_BITS) | ieee_mantissa

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
        k = FLOAT_POW5_INV_BITCOUNT + pow5bits(q) - 1
        i = -e2 + q + k

        vr = mul_shift_32(mv, FLOAT_POW5_INV_SPLIT[q] + 1, i)
        vp = mul_shift_32(mp, FLOAT_POW5_INV_SPLIT[q] + 1, i)
        vm = mul_shift_32(mm, FLOAT_POW5_INV_SPLIT[q] + 1, i)

        if q != 0 and (vp - 1) // 10 <= vm // 10:
            l = FLOAT_POW5_INV_BITCOUNT + pow5bits(q - 1) - 1
            last_digit = (
                mul_shift_32(mv, FLOAT_POW5_INV_SPLIT[q - 1] + 1, -e2 + q - 1 + l) % 10
            )

        if q <= 9:
            if mv % 5 == 0:
                vr_is_trailing_zeros = multiple_of_power_of_5_32(mv, q)
            elif accept_bounds:
                vm_is_trailing_zeros = multiple_of_power_of_5_32(mm, q)
            else:
                if multiple_of_power_of_5_32(mp, q):
                    vp -= 1
    else:
        q = log10_pow5(-e2)
        e10 = q + e2
        i = -e2 - q
        k = pow5bits(i) - FLOAT_POW5_BITCOUNT
        j = q - k

        vr = mul_shift_32(mv, FLOAT_POW5_SPLIT[i], j)
        vp = mul_shift_32(mp, FLOAT_POW5_SPLIT[i], j)
        vm = mul_shift_32(mm, FLOAT_POW5_SPLIT[i], j)

        if q != 0 and (vp - 1) // 10 <= vm // 10:
            j = q - 1 - (pow5bits(i + 1) - FLOAT_POW5_BITCOUNT)
            last_digit = mul_shift_32(mv, FLOAT_POW5_SPLIT[i + 1], j) % 10

        if q <= 1:
            vr_is_trailing_zeros = True
            if accept_bounds:
                vm_is_trailing_zeros = mm_shift == 1
            else:
                vp -= 1
        elif q < 31:
            vr_is_trailing_zeros = multiple_of_power_of_2_32(mv, q - 1)
            if accept_bounds:
                vm_is_trailing_zeros = multiple_of_power_of_5_32(mm, q)
            else:
                if multiple_of_power_of_5_32(mp, q):
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
    olength = decimal_length9(output)

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
