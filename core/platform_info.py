"""平台/目标环境探测（替换硬编码的 `linux-x86_64` 桩实现）。

优先使用调用方显式指定（`options["target_platform"]`），否则按主机探测；
无法判定时返回 `unknown-unknown`，**不谎报**为某个具体平台。
"""
from __future__ import annotations

import platform

_OS = {"linux": "linux", "darwin": "macos", "windows": "windows"}
_ARCH = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "arm64",
         "arm64": "arm64", "i386": "x86", "i686": "x86", "x86": "x86",
         "riscv64": "riscv64", "ppc64le": "ppc64le", "s390x": "s390x"}


def normalize(value: str | None) -> str | None:
    """把 `Linux/x86_64`、`Darwin/arm64` 等归一为 `os-arch`。"""
    if not value:
        return None
    v = str(value).strip().lower().replace(" ", "").replace("/", "-")
    if "-" in v:
        os_part, _, arch_part = v.partition("-")
        os_name = _OS.get(os_part, os_part) or "unknown"
        arch = _ARCH.get(arch_part, arch_part) or "unknown"
        return "%s-%s" % (os_name, arch)
    os_name = _OS.get(v, None)
    if os_name:
        return "%s-%s" % (os_name, normalize_arch(platform.machine()))
    return None


def normalize_arch(machine: str | None) -> str:
    m = (machine or "").strip().lower()
    return _ARCH.get(m, m or "unknown")


def host_platform() -> str:
    """当前主机平台，形如 `linux-x86_64` / `macos-arm64`。"""
    os_name = _OS.get(platform.system().strip().lower(), None)
    if os_name is None:
        return "unknown-%s" % normalize_arch(platform.machine())
    return "%s-%s" % (os_name, normalize_arch(platform.machine()))


def is_supported(platform_str: str | None = None) -> bool:
    """v1.0 实测支持：linux-x86_64（其余平台需自行验证，见兼容性矩阵）。"""
    p = platform_str or host_platform()
    return p == "linux-x86_64"
