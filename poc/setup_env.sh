#!/usr/bin/env bash
# 记录/复现 PoC 环境安装步骤（适用于 RHEL 系 Linux）。
# 该脚本为「记录性脚本」：供新环境参考，非一键幂等安装。执行前请自行确认权限与网络。
#
# 关键点：发行版源仅提供 LLVM/clang 10、Python 3.7，均不满足需求，
#         故 LLVM 18 / Ghidra / JDK21 / Python3.11 均采用官方预编译包或源码编译。
#         默认安装到用户目录（免 sudo）；也可 PREFIX=/opt/<toolchain> 指定其它前缀。
set -euo pipefail

PREFIX=${PREFIX:-$HOME/.local/anti-rea-toolchain}
DL=${DL:-$HOME/.cache/anti-rea-dl}

# 1) 系统开发依赖（需 sudo）
sudo dnf install -y gcc gcc-c++ make ncurses ncurses-compat-libs ncurses-devel \
    zlib zlib-devel openssl-devel libffi-devel bzip2 bzip2-devel sqlite sqlite-devel \
    readline-devel xz xz-devel tk-devel libuuid-devel unzip which patch file

# 2) LLVM 18（官方预编译，锁版本）
mkdir -p "$DL" "$PREFIX"
curl -fL -o "$DL/llvm-18.tar.xz" \
  "https://github.com/llvm/llvm-project/releases/download/llvmorg-18.1.8/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04.tar.xz"
tar xf "$DL/llvm-18.tar.xz" -C "$PREFIX"
# -> $PREFIX/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04/bin/{clang,llvm-config,...}

# 3) JDK 21（Temurin，供 Ghidra）
curl -fL -o "$DL/jdk21.tar.gz" \
  "https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse"
tar xzf "$DL/jdk21.tar.gz" -C "$PREFIX"

# 4) Ghidra（锁定版本，供 PoC-2）
curl -fL -o "$DL/ghidra.zip" \
  "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.4_build/ghidra_12.1.4_PUBLIC_20260921.zip"
unzip -q "$DL/ghidra.zip" -d "$PREFIX"

# 5) Python 3.11（源码编译，供 DEAP）
curl -fL -o "$DL/Python-3.11.9.tgz" "https://mirrors.aliyun.com/python-release/source/Python-3.11.9.tgz"
tar xf "$DL/Python-3.11.9.tgz" -C /tmp
( cd /tmp/Python-3.11.9 && \
  ./configure --prefix="$PREFIX/python3.11" --with-ensurepip=install && \
  make -j"$(nproc)" && make install )
"$PREFIX/python3.11/bin/python3.11" -m pip install \
  -i https://mirrors.aliyun.com/pypi/simple/ deap numpy jsonschema pyyaml

# 6) 自检
"$PREFIX/python3.11/bin/python3.11" -c "import deap, jsonschema; print('python ready')"
echo "完成。请将 clang/llvm-config 与 Ghidra/JDK 路径写入 PATH（参考 docs/STATUS.md §7）。"
