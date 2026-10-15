# Anti-REA Skill —— 顶层构建/测试入口
# 用法：make build / make test / make e2e / make ci / make clean

LLVM ?= /opt/anti-rea-toolchain/clang+llvm-18.1.8-x86_64-linux-gnu-ubuntu-18.04
PY   ?= /opt/anti-rea-toolchain/python3.11/bin/python3.11
OUT  ?= build/run
export PATH := $(LLVM)/bin:$(PATH)

.PHONY: build test e2e ci clean fmt

build: ## 构建 LLVM 变换插件
	cmake -S engine -B engine/build -DLLVM_DIR=$(LLVM)/lib/cmake/llvm -DCMAKE_BUILD_TYPE=Release
	cmake --build engine/build -j

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

fmt: ## 格式化（ruff + black + clang-format，若可用）
	-ruff format core tests
	-black --line-length=100 core tests
	-clang-format -i engine/passes/*.cpp

clean:
	rm -rf engine/build build
