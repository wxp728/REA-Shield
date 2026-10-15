/*
 * PoC-1: LLVM Pass 可行性 —— 控制流平坦化（Control-Flow Flattening, CFF）
 * 关联：ADR-001 / FR-C1…C5 / docs/design/poc-plan.md §2
 *
 * 通过标准：对样例函数完成一次 CFF 式改写，且变换后可编译、可运行、单测全过。
 *
 * 实现要点：
 *   - New PM 插件（PassPlugin），同时支持
 *       * opt -passes='reg2mem,cff-flatten'
 *       * clang -fpass-plugin=...（经 OptimizerLast 扩展点自动挂载 reg2mem+cff）
 *   - 先用 reg2mem 把跨基本块的 SSA 值降级到内存：CFF 让派发块可绕过任意块，
 *     会破坏「支配」，故必须消除跨块 SSA 依赖；
 *   - 另在 pass 内将 PHI 降级为栈（内联实现），作为 opt 单跑路径的安全网；
 *   - 入口块不参与派发（否则入口块会出现前驱，违反 IR 约束）；
 *     入口块只负责写入初始状态并跳转到派发块；
 *   - 其余基本块 → 分配状态编号 → 派发块以 switch 调度；
 *     每个块的后继改写为「写入状态 → 跳回派发块」。
 *
 * 已知限制（PoC 范围内，见 poc-plan §6 结论）：不支持 invoke/callbr/
 * indirectbr/switch/EH 端子。命中则跳过该函数。
 */
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/Scalar/Reg2Mem.h"

#include <map>
#include <vector>

using namespace llvm;

namespace {

// 将函数内所有 PHI 节点降级为栈内存（等价于 reg2mem 的 PHI 部分）。
// 仅使用公开 API，避免依赖未随预编译包分发的内部头文件。
static void demotePHIsToStack(Function &F) {
  std::vector<PHINode *> Phis;
  for (BasicBlock &BB : F)
    for (Instruction &I : BB)
      if (auto *PN = dyn_cast<PHINode>(&I))
        Phis.push_back(PN);
  if (Phis.empty())
    return;

  Instruction *EntryIP = &*F.getEntryBlock().getFirstInsertionPt();
  IRBuilder<> EntryB(EntryIP);
  std::map<PHINode *, AllocaInst *> Allocas;
  for (PHINode *PN : Phis)
    Allocas[PN] = EntryB.CreateAlloca(PN->getType(), nullptr,
                                      PN->getName() + ".reg2mem");

  // 在每条入边末尾写入实参（自引用直接跳过，避免引入非支配的使用）
  for (PHINode *PN : Phis) {
    AllocaInst *A = Allocas[PN];
    for (unsigned i = 0, n = PN->getNumIncomingValues(); i < n; ++i) {
      Value *V = PN->getIncomingValue(i);
      if (V == PN)
        continue;
      IRBuilder<> SB(PN->getIncomingBlock(i)->getTerminator());
      SB.CreateStore(V, A);
    }
  }
  // 在原 PHI 位置插入 load 并替换所有使用
  for (PHINode *PN : Phis) {
    IRBuilder<> LB(PN);
    LoadInst *L =
        LB.CreateLoad(PN->getType(), Allocas[PN], PN->getName() + ".reload");
    PN->replaceAllUsesWith(L);
  }
  for (PHINode *PN : Phis)
    PN->eraseFromParent();
}

struct ControlFlowFlattening : public PassInfoMixin<ControlFlowFlattening> {

  static bool isUnsupportedTerminator(const Instruction *T) {
    return isa<InvokeInst>(T) || isa<CallBrInst>(T) ||
           isa<IndirectBrInst>(T) || isa<SwitchInst>(T) ||
           isa<CatchSwitchInst>(T) || isa<CleanupReturnInst>(T) ||
           isa<CatchReturnInst>(T) || isa<ResumeInst>(T);
  }

  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    if (F.isDeclaration() || F.size() < 2)
      return PreservedAnalyses::all();

    for (BasicBlock &BB : F)
      if (isUnsupportedTerminator(BB.getTerminator()))
        return PreservedAnalyses::all();

    // 1) 将 PHI 降级为栈，保证重定向边后 SSA 仍有效
    demotePHIsToStack(F);

    BasicBlock *Entry = &F.getEntryBlock();
    LLVMContext &Ctx = F.getContext();
    IntegerType *I32 = IntegerType::get(Ctx, 32);

    // 2) 收集参与派发的基本块（不含入口块）
    std::vector<BasicBlock *> Blocks;
    for (BasicBlock &BB : F)
      if (&BB != Entry)
        Blocks.push_back(&BB);

    // 3) 状态变量（置于入口）
    IRBuilder<> EntryB(&*Entry->getFirstInsertionPt());
    AllocaInst *State = EntryB.CreateAlloca(I32, nullptr, "cff.state");

    // 4) 派发块与默认（不可达）块
    BasicBlock *Dispatch = BasicBlock::Create(Ctx, "cff.dispatch", &F);
    BasicBlock *Unreachable = BasicBlock::Create(Ctx, "cff.unreachable", &F);
    new UnreachableInst(Ctx, Unreachable);

    // 5) 生成 switch 调度
    IRBuilder<> DB(Dispatch);
    LoadInst *Loaded = DB.CreateLoad(I32, State, "cff.state.v");
    SwitchInst *Switch = DB.CreateSwitch(Loaded, Unreachable, Blocks.size());
    for (size_t i = 0; i < Blocks.size(); i++)
      Switch->addCase(ConstantInt::get(I32, (uint64_t)(i + 1)), Blocks[i]);

    auto idOf = [&](BasicBlock *BB) -> ConstantInt * {
      for (size_t i = 0; i < Blocks.size(); i++)
        if (Blocks[i] == BB)
          return ConstantInt::get(I32, (uint64_t)(i + 1));
      return ConstantInt::get(I32, 0);
    };

    // 6) 改写端子：写入后继状态后跳回派发块
    auto rewrite = [&](BasicBlock *BB) {
      Instruction *T = BB->getTerminator();
      IRBuilder<> B(T);
      auto *Br = dyn_cast<BranchInst>(T);
      if (!Br)
        return; // 已在上层过滤：仅处理普通分支
      if (Br->isUnconditional()) {
        B.CreateStore(idOf(Br->getSuccessor(0)), State);
      } else {
        Value *Sel = B.CreateSelect(Br->getCondition(), idOf(Br->getSuccessor(0)),
                                    idOf(Br->getSuccessor(1)), "cff.sel");
        B.CreateStore(Sel, State);
      }
      B.CreateBr(Dispatch);
      T->eraseFromParent();
    };

    for (BasicBlock *BB : Blocks)
      if (isa<BranchInst>(BB->getTerminator()))
        rewrite(BB);

    // 入口块：写入初始状态并进入派发（入口块本身不作为派发目标）
    if (isa<BranchInst>(Entry->getTerminator()))
      rewrite(Entry);

    errs() << "[cff] flattened function: " << F.getName() << " ("
           << Blocks.size() << " blocks)\n";
    return PreservedAnalyses::none();
  }
};

} // namespace

extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "cff-flatten", LLVM_VERSION_STRING,
          [](PassBuilder &PB) {
            PB.registerPipelineParsingCallback(
                [](StringRef Name, FunctionPassManager &FPM,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (Name == "cff-flatten") {
                    FPM.addPass(ControlFlowFlattening());
                    return true;
                  }
                  return false;
                });
            PB.registerOptimizerLastEPCallback(
                [](ModulePassManager &MPM, OptimizationLevel) {
                  FunctionPassManager FPM;
                  // 先 reg2mem：把跨基本块的 SSA 值降级到内存，
                  // 否则派发块可绕过被支配块，破坏值的支配关系。
                  FPM.addPass(RegToMemPass());
                  FPM.addPass(ControlFlowFlattening());
                  MPM.addPass(
                      createModuleToFunctionPassAdaptor(std::move(FPM)));
                });
          }};
}
