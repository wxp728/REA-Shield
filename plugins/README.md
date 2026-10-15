# plugins/：第三方 / 示例变换插件（SPI，ADR-005）

变换插件 SPI 契约：`engine/spi/transform_plugin.h`（`SPI_VERSION=1`）。
设计见 `docs/design/ddd/dd-03-llvm-transforms.md §9.2`、`docs/design/interfaces.md §5`（FR-C11）。

## 契约

插件以共享库形式提供两个 `extern "C"` 入口：

```cpp
int anti_rea_spi_version();                       // 返回编译期 SPI_VERSION
anti_rea::TransformPlugin *anti_rea_register_plugin();
```

`TransformPlugin` 声明 `capabilities()`（名称须与 `policy.strategies[]` 一致）、
`validate()`、`apply(llvm::Module&, Config, seed)`、`verify()`。

宿主（`engine/build/anti_rea_passes.so` 的 `external-transforms` 模块 Pass）在流水线末端
加载它们，**校验 `SPI_VERSION`**；不匹配或缺少入口即拒载（`E_PLUGIN_INCOMPATIBLE`），
不影响核心引擎与其余变换。

## 使用

```sh
ANTI_REA_EXTRA_PLUGINS=/abs/path/libmy_plugin.so \
ANTI_REA_STRATEGIES=my_strategy \
clang -O1 -fpass-plugin=engine/build/anti_rea_passes.so app.c -o app
```

经 CLI 流水线时，额外策略名用 `ANTI_REA_EXTRA_STRATEGIES` 追加（`ANTI_REA_EXTRA_PLUGINS`
经环境继承）：

```sh
ANTI_REA_EXTRA_PLUGINS=/abs/path/libmy_plugin.so \
ANTI_REA_EXTRA_STRATEGIES=my_strategy \
anti-rea protect policy.yaml --root src --source src/app.c -o out
```

## 示例

`plugins/example-transform/`：功能保持的"函数标记"示例（`example_marker`），
随 engine 构建为 `engine/build/libanti_rea_example_plugin.so`。测试见 `tests/test_spi.py`。
