
import re


def camel_to_snake(name: str) -> str:
    """
    Mengonversi string dari camelCase ke snake_case.
    """
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
