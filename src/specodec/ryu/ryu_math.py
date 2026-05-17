def pow5bits(e):
    return ((e * 1217359) // 524288) + 1


def log10_pow2(e):
    return (e * 78913) // 262144


def log10_pow5(e):
    return (e * 732923) // 1048576


def decimal_length9(v):
    if v >= 100000000:
        return 9
    if v >= 10000000:
        return 8
    if v >= 1000000:
        return 7
    if v >= 100000:
        return 6
    if v >= 10000:
        return 5
    if v >= 1000:
        return 4
    if v >= 100:
        return 3
    if v >= 10:
        return 2
    return 1


def decimal_length17(v):
    if v >= 10000000000000000:
        return 17
    if v >= 1000000000000000:
        return 16
    if v >= 100000000000000:
        return 15
    if v >= 10000000000000:
        return 14
    if v >= 1000000000000:
        return 13
    if v >= 100000000000:
        return 12
    if v >= 10000000000:
        return 11
    if v >= 1000000000:
        return 10
    if v >= 100000000:
        return 9
    if v >= 10000000:
        return 8
    if v >= 1000000:
        return 7
    if v >= 100000:
        return 6
    if v >= 10000:
        return 5
    if v >= 1000:
        return 4
    if v >= 100:
        return 3
    if v >= 10:
        return 2
    return 1


def mul_shift_32(m, factor, shift):
    factor_lo = factor & 0xFFFFFFFF
    factor_hi = factor >> 32

    bits0 = m * factor_lo
    bits1 = m * factor_hi

    sum_val = (bits0 >> 32) + bits1
    return (sum_val >> (shift - 32)) & 0xFFFFFFFF


def mul_shift_64(m, mul, shift):
    # Correct implementation matching C version:
    # const uint128_t b0 = ((uint128_t) m) * mul[0];
    # const uint128_t b2 = ((uint128_t) m) * mul[1];
    # return (uint64_t) (((b0 >> 64) + b2) >> (shift - 64));

    b0 = m * mul[0]
    b2 = m * mul[1]

    # b0 >> 64 means taking the high 64 bits of b0
    b0_hi = b0 >> 64

    # (b0_hi + b2) >> (shift - 64)
    sum_val = b0_hi + b2
    return (sum_val >> (shift - 64)) & 0xFFFFFFFFFFFFFFFF


def multiple_of_power_of_5_32(value, q):
    if q == 0:
        return True
    if q >= 32:
        return value == 0
    pow5 = 5**q
    return (value % pow5) == 0


def multiple_of_power_of_2_32(value, q):
    if q == 0:
        return True
    if q >= 32:
        return value == 0
    return (value & ((1 << q) - 1)) == 0


def multiple_of_power_of_5_64(value, q):
    if q == 0:
        return True
    if q >= 64:
        return value == 0
    pow5 = 5**q
    return (value % pow5) == 0


def multiple_of_power_of_2_64(value, q):
    if q == 0:
        return True
    if q >= 64:
        return value == 0
    return (value & ((1 << q) - 1)) == 0
