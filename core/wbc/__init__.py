"""白盒密码模块（FR-C10）。参见 dd-06-wbc.md。"""
from .wbc import generate, selftest, check_no_key_constant, derive_key  # noqa: F401

__all__ = ["generate", "selftest", "check_no_key_constant", "derive_key"]
