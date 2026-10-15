"""可复现性验证（NFR-04 / NFR-08）。

同输入 + 同种子连续保护两次，比对 `artifacts/` 与 `transform.log` 的逐位哈希。
`metadata.json` 的 `generated_at` 属时间戳，按 NFR-04 排除（其余字段应一致）。
"""
from __future__ import annotations

import copy
import hashlib
import os

from .. import transform


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _hashes(run_dir: str) -> dict:
    out = {}
    for root, _dirs, files in os.walk(run_dir):
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, run_dir)
            if rel == "metadata.json":
                continue  # 含 generated_at 时间戳
            out[rel] = _sha256(p)
    return out


_STABLE_META_FIELDS = ("seed", "engine_version", "strategies", "whitelist",
                       "vmp_whitelist", "input_fingerprint", "policy_hash",
                       "offline", "extra_plugins")


def _stable_meta(meta: dict) -> dict:
    """仅取与「可复现」相关的稳定字段（排除含绝对路径/时间戳的字段）。"""
    return {k: meta.get(k) for k in _STABLE_META_FIELDS}


def check(policy: dict, sources: list[str], root: str, seed: int,
          workdir: str, fixed_run_id: str = "run-repro") -> dict:
    """跑两次并比对；返回 `{identical, artifacts, metadata_fields_equal, diff}`。"""
    metas = []
    hashes = []
    for i in (1, 2):
        d = os.path.join(workdir, "repro-%d" % i)
        p = copy.deepcopy(policy)
        p["_run_id"] = fixed_run_id
        metas.append(transform.protect(p, sources, d, root=root, seed=seed))
        hashes.append(_hashes(d))

    keys = sorted(set(hashes[0]) | set(hashes[1]))
    diff = [k for k in keys if hashes[0].get(k) != hashes[1].get(k)]
    meta_equal = _stable_meta(metas[0]) == _stable_meta(metas[1])
    return {
        "identical": not diff and meta_equal,
        "artifacts_compared": len(keys),
        "artifact_diff": diff,
        "metadata_fields_equal": meta_equal,
        "seed": seed,
        "run_id": fixed_run_id,
    }
