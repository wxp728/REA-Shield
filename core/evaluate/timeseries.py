"""指标时间序列库（FR-E6）。

以 SQLite 存档每次攻击模拟/回归的指标，用于趋势追踪与回归检测（FR-E8）。
单文件、无外部依赖。
"""
from __future__ import annotations

import os
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
  run_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  asset TEXT NOT NULL DEFAULT '',
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  target REAL,
  PRIMARY KEY (run_id, asset, metric)
);
CREATE INDEX IF NOT EXISTS idx_metrics_metric ON metrics(metric, ts);
"""


def _connect(db: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript(_SCHEMA)
    return con


# 目标值（用于趋势对比；方向：为真表示"越大越好"）
_TARGETS = {
    "token_ratio": 100.0,
    "time_ratio": 10.0,
    "name_recovery_accuracy": 0.20,
    "function_judgement_accuracy": 0.30,
    "vuln_discovery_rate": 0.10,
    "bin_similarity": 0.55,
    "session_context_used_ratio": 0.90,
}


def record(db: str, run_id: str, ts: str, metrics: dict,
           asset: str = "") -> int:
    """写入一份指标，返回写入条数。"""
    con = _connect(db)
    n = 0
    with con:
        for k, v in metrics.items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            con.execute(
                "INSERT OR REPLACE INTO metrics(run_id, ts, asset, metric, value, target)"
                " VALUES (?,?,?,?,?,?)",
                (run_id, ts, asset, k, float(v), _TARGETS.get(k)))
            n += 1
    con.close()
    return n


def history(db: str, metric: str, limit: int = 50) -> list[tuple]:
    """按时间倒序返回某指标的 (ts, run_id, value)。"""
    con = _connect(db)
    rows = con.execute(
        "SELECT ts, run_id, value FROM metrics WHERE metric=? ORDER BY ts DESC LIMIT ?",
        (metric, limit)).fetchall()
    con.close()
    return rows


def latest(db: str, metric: str) -> float | None:
    rows = history(db, metric, 1)
    return rows[0][2] if rows else None
