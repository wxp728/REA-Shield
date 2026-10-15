"""对抗性诱导生成器（FR-C9）。参见 dd-05-adversarial.md。"""
from .generator import generate_variants, build_variant  # noqa: F401

__all__ = ["generate_variants", "build_variant"]
