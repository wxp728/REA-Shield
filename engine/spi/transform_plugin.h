/*
 * REA-Shield 变换插件 SPI（进程内，ADR-005 / FR-C11）
 * 契约见 docs/design/interfaces.md §5、dd-03-llvm-transforms.md §9.2。
 *
 * 第三方变换以共享库形式提供：
 *   - 导出 anti_rea_spi_version() -> int        返回编译期 SPI_VERSION
 *   - 导出 anti_rea_register_plugin() -> TransformPlugin*
 * 宿主（engine/build/anti_rea_passes.so）在模块级加载它们，校验 SPI_VERSION 与
 * 能力声明；不兼容则拒载（E_PLUGIN_INCOMPATIBLE）而不影响核心引擎。
 */
#ifndef ANTI_REA_TRANSFORM_PLUGIN_H
#define ANTI_REA_TRANSFORM_PLUGIN_H

#include <cstdint>
#include <string>
#include <vector>

namespace llvm {
class Module;
}

namespace anti_rea {

// 破坏性变更时 +1；宿主拒绝不匹配的插件。
static constexpr int SPI_VERSION = 1;

// 插件能力声明（对应 policy.strategies[] 中的名称）。
struct TransformCapabilities {
  std::string name;                       // 与 policy.strategies[] 一致
  std::vector<std::string> applies_to;    // {"ir","binary"}
  bool supports_coverage = false;
  std::string params_schema;              // 参数 JSON Schema（可空）
  double predicted_overhead = 0.0;        // 开销估计（供预算预测器）
};

// 宿主注入的配置：参数 JSON + 随机种子（NFR-04 可复现）。
struct Config {
  std::string json;   // 参数（JSON 字符串，默认为 "{}"）
};

struct Result {
  bool ok = true;
  std::string detail;
};

class TransformPlugin {
public:
  virtual ~TransformPlugin() = default;
  virtual TransformCapabilities capabilities() const = 0;
  virtual bool validate(const Config &cfg, std::string &err) const = 0;
  virtual Result apply(llvm::Module &m, const Config &cfg, uint64_t seed) = 0;
  virtual Result verify(const llvm::Module &m, std::string &err) const = 0;
};

} // namespace anti_rea

// ------------------------- 插件导出入口（C ABI）-------------------------
extern "C" {
// 返回编译插件时使用的 SPI_VERSION。
int anti_rea_spi_version();
// 返回插件单例（宿主拥有调用期，不做释放）。
anti_rea::TransformPlugin *anti_rea_register_plugin();
}

#endif // ANTI_REA_TRANSFORM_PLUGIN_H
