/*
 * Anti-REA 示例变换插件（FR-C11 / ADR-005）
 *
 * 演示：无需改动核心引擎，仅实现 SPI 即可注册一个新变换。
 * 本插件是一个功能保持的"函数标记/重命名"示例：给每个非 main 的定义函数
 * 追加 `#0` 属性 `anti-rea-example`，并挂载模块命名元数据 `anti_rea.example`。
 *
 * 构建：随 engine 一同构建，产物 engine/build/libanti_rea_example_plugin.so
 * 使用：ANTI_REA_EXTRA_PLUGINS=<..>/libanti_rea_example_plugin.so \
 *       ANTI_REA_STRATEGIES=example_marker \
 *       clang -O1 -fpass-plugin=engine/build/anti_rea_passes.so x.c -o x
 */
#include "spi/transform_plugin.h"

#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Metadata.h"
#include "llvm/IR/Module.h"

#include <string>

namespace {

class ExampleMarkerPlugin : public anti_rea::TransformPlugin {
public:
  anti_rea::TransformCapabilities capabilities() const override {
    anti_rea::TransformCapabilities C;
    C.name = "example_marker";
    C.applies_to = {"ir"};
    C.supports_coverage = false;
    C.params_schema = "{}";
    C.predicted_overhead = 0.001;
    return C;
  }

  bool validate(const anti_rea::Config &, std::string &) const override {
    return true;
  }

  anti_rea::Result apply(llvm::Module &M, const anti_rea::Config &,
                         uint64_t Seed) override {
    anti_rea::Result R;
    unsigned N = 0;
    for (llvm::Function &F : M) {
      if (F.isDeclaration() || F.getName() == "main") continue;
      F.addFnAttr("anti-rea-example");
      ++N;
    }
    // 命名元数据，便于验证与溯源
    llvm::LLVMContext &Ctx = M.getContext();
    llvm::Metadata *Ops[] = {llvm::MDString::get(Ctx, "example_marker")};
    M.getOrInsertNamedMetadata("anti_rea.example")
        ->addOperand(llvm::MDNode::get(Ctx, Ops));
    R.ok = true;
    R.detail = "marked=" + std::to_string(N) + " seed=" + std::to_string(Seed);
    return R;
  }

  anti_rea::Result verify(const llvm::Module &, std::string &) const override {
    return {};
  }
};

} // namespace

extern "C" int anti_rea_spi_version() { return anti_rea::SPI_VERSION; }

extern "C" anti_rea::TransformPlugin *anti_rea_register_plugin() {
  static ExampleMarkerPlugin P;
  return &P;
}
