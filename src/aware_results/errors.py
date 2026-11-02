import re


class PipelineError(ValueError):
    """Only fixed machine-readable codes may reach public logs."""

    def __init__(self, code: str):
        if re.fullmatch(r"[a-z_]+", code) is None:
            code = "internal_error"
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PipelineError(code)
