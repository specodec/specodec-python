from .ryu import float32_to_string, float64_to_string


def format_float32(value: float) -> str:
    return float32_to_string(value)


def format_float64(value: float) -> str:
    return float64_to_string(value)
