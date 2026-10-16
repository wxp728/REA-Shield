# REA-Shield Skill —— 钉死的运行镜像（免手工拼装 LLVM18 + 插件）
#
# 构建：docker build -t anti-rea:1.0.0 .
# 运行：
#   docker run --rm -v "$PWD:/work" anti-rea:1.0.0 scan /work/your-project -o /work/out
#   docker run --rm -i anti-rea:1.0.0 mcp        # 以 MCP stdio 服务器方式运行
#
# 说明：v1.0 的变换引擎是 Linux 共享库插件，protect 仅支持 Linux。
# 本镜像固定 LLVM 18 + Python 3.11，开箱即用，无需在宿主机安装工具链。

FROM python:3.11-slim-bookworm

ARG LLVM_VERSION=18
ARG DEBIAN_FRONTEND=noninteractive

# ---- LLVM/clang 18 + 构建与核验工具 ----
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates wget gnupg lsb-release \
      build-essential cmake binutils file \
 && wget -qO- https://apt.llvm.org/llvm-snapshot.gpg.key \
      | tee /etc/apt/trusted.gpg.d/apt.llvm.org.asc >/dev/null \
 && echo "deb http://apt.llvm.org/bookworm/ llvm-toolchain-bookworm-${LLVM_VERSION} main" \
      > /etc/apt/sources.list.d/llvm.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      clang-${LLVM_VERSION} llvm-${LLVM_VERSION} llvm-${LLVM_VERSION}-dev \
      libclang-${LLVM_VERSION}-dev \
 && ln -sf /usr/bin/clang-${LLVM_VERSION} /usr/local/bin/clang \
 && ln -sf /usr/bin/clang++-${LLVM_VERSION} /usr/local/bin/clang++ \
 && ln -sf /usr/bin/opt-${LLVM_VERSION} /usr/local/bin/opt \
 && ln -sf /usr/bin/llvm-config-${LLVM_VERSION} /usr/local/bin/llvm-config \
 && rm -rf /var/lib/apt/lists/*

ENV ANTI_REA_LLVM=/usr/lib/llvm-18 \
    PATH=/usr/lib/llvm-18/bin:$PATH \
    PYTHONUNBUFFERED=1

# ---- 项目 ----
WORKDIR /opt/anti-rea
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# 构建 LLVM 变换插件（engine/build/anti_rea_passes.so）与 VM 解释器
RUN cmake -S engine -B engine/build \
      -DLLVM_DIR="$(llvm-config --cmakedir)" \
      -DCMAKE_BUILD_TYPE=Release \
 && cmake --build engine/build -j"$(nproc)"

# 镜像自检（构建期即可发现缺件）
RUN python -m core.cli doctor

# 默认进入回环脚本：可直接 `docker run ... scan ...`，或用 `mcp` 启动服务器
COPY deploy/entrypoint.sh /usr/local/bin/anti-rea-entrypoint
RUN chmod +x /usr/local/bin/anti-rea-entrypoint
ENTRYPOINT ["anti-rea-entrypoint"]
CMD ["doctor"]
