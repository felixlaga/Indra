"""ERLA source package.

Root exports are resolved lazily so importing lightweight packages such as
``src.domain`` does not initialize API clients or optional network dependencies.
"""

__all__ = [
    "summarize_paper",
    "summarize_papers",
    "summarize_paper_validated",
]


def __getattr__(name: str):
    if name in __all__:
        from . import summarize

        return getattr(summarize, name)
    raise AttributeError(f"module 'src' has no attribute {name!r}")
