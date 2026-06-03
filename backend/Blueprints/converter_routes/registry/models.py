from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SimpleConverterRoute:
    blueprint_name: str
    url_rule: str
    allowed_extensions: tuple[str, ...]
    convert_function: Callable
    output_extension: str
    tool_name: str

    @property
    def endpoint(self):
        return self.blueprint_name
