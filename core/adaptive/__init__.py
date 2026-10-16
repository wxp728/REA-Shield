"""REA-Shield 自适应策略引擎（FR-F1…F4）。

- `evolve`：策略遗传进化（FR-F3）；
- `knowledge`：策略知识库与迁移推荐（FR-F4）；
- `weakness`：弱点记录与策略调整（FR-F2）；
- `multi_llm`：多模型探测与保守聚合（FR-F1，复用 `evaluate.metrics.aggregate`）。
"""
from .engine import evolve, export_policy  # noqa: F401
from . import genome, knowledge, weakness  # noqa: F401
