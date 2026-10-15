/*
 * Anti-REA Transform Engine —— LLVM Pass 插件（R1 MVP）
 * 关联：FR-C1 CFF / FR-C2 MBA / FR-C3 不透明谓词 / FR-C6 选择性变换（白名单）
 * 设计：docs/design/ddd/dd-03-llvm-transforms.md
 *
 * 暴露的 pass：
 *   - cff-flatten       仅控制流平坦化
 *   - mba               仅非线性 MBA（加法/异或恒等式）
 *   - opaque-predicates 仅不透明谓词
 *   - anti-rea          按 -anti-rea-strategies 组合施加（默认 cff,mba,opaque）
 *
 * 白名单（FR-C6）：
 *   -anti-rea-whitelist=foo,bar   只变换列出的函数；空则不变换任何函数
 *   特殊值 "*" 表示变换全部函数（便于测试）
 *
 * 关键约束（见 dd-03 §2）：CFF 前须 reg2mem（消除跨块 SSA 支配依赖）；
 * 变换应在优化流水线末端执行。
 */
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/raw_ostream.h"
#include "llvm/Transforms/Scalar/Reg2Mem.h"

#include <cstdlib>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

using namespace llvm;

namespace {

// ------------------------- 配置（环境变量）-------------------------
// 注：clang -fpass-plugin 下插件 cl::opt 的注册晚于命令行解析，故改用环境变量。
static std::string envStr(const char *Key, const char *Def) {
  const char *v = std::getenv(Key);
  return v ? std::string(v) : std::string(Def);
}
static int envInt(const char *Key, int Def) {
  const char *v = std::getenv(Key);
  return v ? std::atoi(v) : Def;
}

// ------------------------- 工具 -------------------------
static std::set<std::string> splitCSV(const std::string &s) {
  std::set<std::string> out;
  std::string cur;
  for (char c : s) {
    if (c == ',') {
      if (!cur.empty()) out.insert(cur);
      cur.clear();
    } else if (c != ' ') {
      cur.push_back(c);
    }
  }
  if (!cur.empty()) out.insert(cur);
  return out;
}

static bool whitelisted(StringRef Name) {
  static std::set<std::string> WL = splitCSV(envStr("ANTI_REA_WHITELIST", ""));
  if (WL.empty()) return false;
  if (WL.count("*")) return true;
  return WL.count(Name.str()) > 0;
}
static std::set<std::string> &strategySet() {
  static std::set<std::string> S =
      splitCSV(envStr("ANTI_REA_STRATEGIES", "cff,mba,opaque"));
  return S;
}

static bool unsupportedTerminator(const Instruction *T) {
  return isa<InvokeInst>(T) || isa<CallBrInst>(T) || isa<IndirectBrInst>(T) ||
         isa<SwitchInst>(T) || isa<CatchSwitchInst>(T) ||
         isa<CleanupReturnInst>(T) || isa<CatchReturnInst>(T) ||
         isa<ResumeInst>(T);
}

// 将 PHI 降级为栈（等价 reg2mem 的 PHI 部分）
static void demotePHIsToStack(Function &F) {
  std::vector<PHINode *> Phis;
  for (BasicBlock &BB : F)
    for (Instruction &I : BB)
      if (auto *PN = dyn_cast<PHINode>(&I))
        Phis.push_back(PN);
  if (Phis.empty()) return;

  Instruction *EntryIP = &*F.getEntryBlock().getFirstInsertionPt();
  IRBuilder<> EntryB(EntryIP);
  std::map<PHINode *, AllocaInst *> Allocas;
  for (PHINode *PN : Phis)
    Allocas[PN] = EntryB.CreateAlloca(PN->getType(), nullptr,
                                      PN->getName() + ".reg2mem");
  for (PHINode *PN : Phis) {
    AllocaInst *A = Allocas[PN];
    for (unsigned i = 0, n = PN->getNumIncomingValues(); i < n; ++i) {
      Value *V = PN->getIncomingValue(i);
      if (V == PN) continue;
      IRBuilder<> SB(PN->getIncomingBlock(i)->getTerminator());
      SB.CreateStore(V, A);
    }
  }
  for (PHINode *PN : Phis) {
    IRBuilder<> LB(PN);
    LoadInst *L = LB.CreateLoad(PN->getType(), Allocas[PN], PN->getName() + ".reload");
    PN->replaceAllUsesWith(L);
  }
  for (PHINode *PN : Phis) PN->eraseFromParent();
}

// ------------------------- CFF（FR-C1）-------------------------
static bool applyCFF(Function &F, unsigned Seed) {
  if (F.isDeclaration() || F.size() < 2) return false;
  for (BasicBlock &BB : F)
    if (unsupportedTerminator(BB.getTerminator())) return false;
  if ((int)F.size() > envInt("ANTI_REA_MAX_BLOCKS", 256)) return false;

  demotePHIsToStack(F);

  BasicBlock *Entry = &F.getEntryBlock();
  LLVMContext &Ctx = F.getContext();
  IntegerType *I32 = IntegerType::get(Ctx, 32);

  std::vector<BasicBlock *> Blocks;
  for (BasicBlock &BB : F)
    if (&BB != Entry) Blocks.push_back(&BB);

  IRBuilder<> EntryB(&*Entry->getFirstInsertionPt());
  AllocaInst *State = EntryB.CreateAlloca(I32, nullptr, "cff.state");

  BasicBlock *Dispatch = BasicBlock::Create(Ctx, "cff.dispatch", &F);
  BasicBlock *Unreachable = BasicBlock::Create(Ctx, "cff.unreachable", &F);
  new UnreachableInst(Ctx, Unreachable);

  // 状态编号随机置换（P_seed）：index -> id
  std::vector<unsigned> ids(Blocks.size());
  for (size_t i = 0; i < Blocks.size(); ++i) ids[i] = (unsigned)(i + 1);
  // 简易确定性洗牌（xorshift32）
  uint32_t x = Seed ? (uint32_t)Seed : 0x9e3779b9u;
  auto next = [&x]() { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; };
  for (size_t i = ids.size(); i > 1; --i) {
    size_t j = next() % i;
    std::swap(ids[i - 1], ids[j]);
  }

  IRBuilder<> DB(Dispatch);
  LoadInst *Loaded = DB.CreateLoad(I32, State, "cff.state.v");
  SwitchInst *Switch = DB.CreateSwitch(Loaded, Unreachable, Blocks.size());
  for (size_t i = 0; i < Blocks.size(); ++i)
    Switch->addCase(ConstantInt::get(I32, ids[i]), Blocks[i]);

  auto idOf = [&](BasicBlock *BB) -> ConstantInt * {
    for (size_t i = 0; i < Blocks.size(); ++i)
      if (Blocks[i] == BB) return ConstantInt::get(I32, ids[i]);
    return ConstantInt::get(I32, 0);
  };

  auto rewrite = [&](BasicBlock *BB) {
    Instruction *T = BB->getTerminator();
    IRBuilder<> B(T);
    auto *Br = dyn_cast<BranchInst>(T);
    if (!Br) return;
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
    if (isa<BranchInst>(BB->getTerminator())) rewrite(BB);
  if (isa<BranchInst>(Entry->getTerminator())) rewrite(Entry);
  return true;
}

// ------------------------- MBA（FR-C2）-------------------------
static bool applyMBA(Function &F) {
  std::vector<BinaryOperator *> Targets;
  for (BasicBlock &BB : F)
    for (Instruction &I : BB)
      if (auto *BO = dyn_cast<BinaryOperator>(&I)) {
        if (!BO->getType()->isIntegerTy()) continue;
        if (BO->getOpcode() == Instruction::Add ||
            BO->getOpcode() == Instruction::Xor)
          Targets.push_back(BO);
      }

  for (BinaryOperator *BO : Targets) {
    IRBuilder<> B(BO);
    Value *X = BO->getOperand(0), *Y = BO->getOperand(1);
    Value *Res = nullptr;
    if (BO->getOpcode() == Instruction::Add) {
      // x + y = (x ^ y) + 2 * (x & y)
      Value *xy = B.CreateXor(X, Y, "mba.xor");
      Value *an = B.CreateAnd(X, Y, "mba.and");
      Value *two = ConstantInt::get(BO->getType(), 2);
      Value *t = B.CreateMul(an, two, "mba.mul");
      Res = B.CreateAdd(xy, t, "mba.add");
    } else if (BO->getOpcode() == Instruction::Xor) {
      // x ^ y = (x | y) - (x & y)
      Value *o = B.CreateOr(X, Y, "mba.or");
      Value *an = B.CreateAnd(X, Y, "mba.and");
      Res = B.CreateSub(o, an, "mba.sub");
    }
    if (Res) {
      BO->replaceAllUsesWith(Res);
      BO->eraseFromParent();
    }
  }
  return !Targets.empty();
}

// ------------------------- 不透明谓词（FR-C3）-------------------------
static GlobalVariable *getOpaqueGlobal(Module &M, int Seed) {
  if (GlobalVariable *G = M.getGlobalVariable("__anti_rea_opaque"))
    return G;
  LLVMContext &Ctx = M.getContext();
  auto *I32 = IntegerType::get(Ctx, 32);
  uint32_t v = 0x12345678u ^ (uint32_t)Seed;
  if (v == 0) v = 1;
  auto *Init = ConstantInt::get(I32, v);
  auto *G = new GlobalVariable(M, I32, /*isConstant=*/false,
                               GlobalValue::InternalLinkage, Init,
                               "__anti_rea_opaque");
  return G;
}

static bool applyOpaque(Function &F, int Seed) {
  Module *M = F.getParent();
  if (!M) return false;
  GlobalVariable *G = getOpaqueGlobal(*M, Seed);
  LLVMContext &Ctx = F.getContext();
  auto *I32 = IntegerType::get(Ctx, 32);
  auto *One = ConstantInt::get(I32, 1);
  auto *Zero = ConstantInt::get(I32, 0);

  // 生成恒真值（基于运行期不可静态证明的全局载入）
  auto opaqueTrue = [&](IRBuilder<> &B) -> Value * {
    LoadInst *L = B.CreateLoad(I32, G, "opq.v");
    Value *inc = B.CreateAdd(L, One, "opq.inc");
    Value *prod = B.CreateMul(L, inc, "opq.prod");      // 恒偶
    Value *lsb = B.CreateAnd(prod, One, "opq.lsb");     // 恒 0
    return B.CreateICmpEQ(lsb, Zero, "opq.t");          // 恒真
  };

  std::vector<BranchInst *> CondBrs;
  std::vector<SwitchInst *> Switches;
  for (BasicBlock &BB : F) {
    if (auto *Br = dyn_cast<BranchInst>(BB.getTerminator())) {
      if (Br->isConditional()) CondBrs.push_back(Br);
    } else if (auto *Sw = dyn_cast<SwitchInst>(BB.getTerminator())) {
      Switches.push_back(Sw);
    }
  }

  // 1) 条件分支：cond -> cond & opaque_true
  for (BranchInst *Br : CondBrs) {
    IRBuilder<> B(Br);
    Br->setCondition(B.CreateAnd(Br->getCondition(), opaqueTrue(B), "opq.c"));
  }

  // 2) switch（如 CFF 派发器）：用恒真守卫拆分 body / unreachable
  for (SwitchInst *Sw : Switches) {
    BasicBlock *BB = Sw->getParent();
    BasicBlock *Body = BasicBlock::Create(Ctx, "opq.body", &F);
    BasicBlock *Unr = BasicBlock::Create(Ctx, "opq.unreachable", &F);
    new UnreachableInst(Ctx, Unr);
    Sw->removeFromParent();
    Sw->insertInto(Body, Body->end());
    IRBuilder<> B(BB);
    B.CreateCondBr(opaqueTrue(B), Body, Unr);
  }
  return !CondBrs.empty() || !Switches.empty();
}

// ------------------------- 组合 Pass -------------------------
struct AntiReaPass : public PassInfoMixin<AntiReaPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    if (!whitelisted(F.getName())) return PreservedAnalyses::all();
    if (F.isDeclaration()) return PreservedAnalyses::all();

    static std::set<std::string> &S = strategySet();
    bool changed = false;
    if (S.count("cff")) changed |= applyCFF(F, (unsigned)envInt("ANTI_REA_SEED", 0));
    if (S.count("mba")) changed |= applyMBA(F);
    if (S.count("opaque")) changed |= applyOpaque(F, envInt("ANTI_REA_SEED", 0));
    return changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};

// 单策略 Pass
struct CFFPass : PassInfoMixin<CFFPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyCFF(F, (unsigned)envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
};
struct MBAPass : PassInfoMixin<MBAPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyMBA(F) ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
};
struct OpaquePass : PassInfoMixin<OpaquePass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyOpaque(F, envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
};

} // namespace

// ------------------------- 注册 -------------------------
extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
llvmGetPassPluginInfo() {
  return {LLVM_PLUGIN_API_VERSION, "anti-rea-engine", LLVM_VERSION_STRING,
          [](PassBuilder &PB) {
            PB.registerPipelineParsingCallback(
                [](StringRef Name, FunctionPassManager &FPM,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (Name == "cff-flatten") { FPM.addPass(CFFPass()); return true; }
                  if (Name == "mba") { FPM.addPass(MBAPass()); return true; }
                  if (Name == "opaque-predicates") { FPM.addPass(OpaquePass()); return true; }
                  if (Name == "anti-rea") { FPM.addPass(AntiReaPass()); return true; }
                  return false;
                });
            // clang -fpass-plugin 路径：在流水线末端挂 reg2mem + anti-rea
            PB.registerOptimizerLastEPCallback(
                [](ModulePassManager &MPM, OptimizationLevel) {
                  FunctionPassManager FPM;
                  FPM.addPass(RegToMemPass());
                  FPM.addPass(AntiReaPass());
                  MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
                });
          }};
}
