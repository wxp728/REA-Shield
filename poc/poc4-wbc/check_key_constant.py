#!/usr/bin/env python3
"""静态检查：目标二进制中不得出现明文 AES 密钥常量（16 字节序列 00 01 .. 0f）。

退出码：0 = 未命中（PASS），1 = 命中（FAIL）。
"""
import sys

KEY = bytes(range(16))  # FIPS-197 示例密钥


def main() -> int:
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <binary>", file=sys.stderr)
        return 2
    with open(sys.argv[1], "rb") as fh:
        data = fh.read()
    if KEY in data:
        print("FAIL: 发现明文密钥常量", KEY.hex())
        return 1
    print("PASS: 未发现明文密钥常量")
    return 0


if __name__ == "__main__":
    sys.exit(main())
