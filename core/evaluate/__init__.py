"""Anti-REA 评估验证层。

- `verify`：功能保持 + 性能基准（FR-E1/E2）；
- `attack_sim`：攻击模拟（FR-E3/E4/E5）+ 六项指标（FR-E6）+ 判定（OI-07）；
- `metrics` / `timeseries`：指标计算与时间序列库。
"""
from .evaluate import verify  # noqa: F401
from .attack_sim import attack_sim  # noqa: F401
from . import metrics, timeseries, static_features, llm, regression  # noqa: F401
