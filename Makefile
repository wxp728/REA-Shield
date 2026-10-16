# REA-Shield Skill —— 顶层构建/测试入口
# 用法：make doctor / make install / make build / make test / make e2e / make ci / make clean
#
# 工具链定位优先级：环境变量 > PATH > 常见安装目录（不再写死路径）。
#   LLVM=<LLVM 前缀>  或  ANTI_REA_LLVM=<前缀>   # 例：/usr/lib/llvm-18
#   PY=<python 可执行>                            # 例：python3.11
# 未显式指定时，Makefile 会用 llvm-config / 常见目录自动探测。

LLVM ?= $(shell \
  if [ -n "$$ANTI_REA_LLVM" ]; then echo "$$ANTI_REA_LLVM"; \
  elif command -v llvm-config >/dev/null 2>&1; then dirname "$$(dirname "$$(command -v llvm-config)")"; \
  else ls -d /opt/anti-rea-toolchain/clang+llvm-* /opt/anti-rea-toolchain/llvm* /usr/lib/llvm-* 2>/dev/null | sort | tail -1; fi)
PY   ?= $(shell command -v python3.11 2>/dev/null || command -v python3 2>/dev/null || command -v python)
LLVM_CMAKE_DIR ?= $(shell llvm-config --cmakedir 2>/dev/null || echo "$(LLVM)/lib/cmake/llvm")
OUT  ?= build/run

ifneq ($(strip $(LLVM)),)
export PATH := $(LLVM)/bin:$(PATH)
endif

.PHONY: build test e2e doctor install ci fmt clean docker

build: ## 构建 LLVM 变换插件 + VM 解释器
	cmake -S engine -B engine/build -DLLVM_DIR=$(LLVM_CMAKE_DIR) -DCMAKE_BUILD_TYPE=Release
	cmake --build engine/build -j

install: ## 安装 Python 依赖
	$(PY) -m pip install -r requirements.txt

doctor: ## 环境自检
	$(PY) -m core.cli doctor

test: build ## 单元 + 集成测试
	$(PY) -m unittest discover -s tests -v

e2e: build ## 端到端：scan -> plan -> protect -> verify
	rm -rf $(OUT) && mkdir -p $(OUT)
	$(PY) -m core.cli scan tests/samples -o $(OUT)
	$(PY) -m core.cli plan $(OUT)/asset_manifest.json -o $(OUT)
	$(PY) -m core.cli protect $(OUT)/protection_policy.yaml --root tests/samples \
	    --source tests/samples/hello.c -o $(OUT)
	$(PY) -m core.cli verify $(OUT)

ci: ## 完整 CI 门禁
	bash ci/ci.sh

docker: ## 构建容器镜像
	docker build -t anti-rea:1.0.0 .

fmt: ## 格式化（ruff + black + clang-format，若可用）
	-ruff format core tests
	-black --line-length=100 core tests
	-clang-format -i engine/passes/*.cpp

clean:
	rm -rf engine/build build
