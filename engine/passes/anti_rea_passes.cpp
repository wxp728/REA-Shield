/*
 * REA-Shield Transform Engine —— LLVM Pass 插件
 * 关联：FR-C1 CFF / FR-C2 MBA / FR-C3 不透明谓词 / FR-C6 选择性变换（白名单）
 *       FR-C7 代码虚拟化（R2）
 * 设计：docs/design/ddd/dd-03-llvm-transforms.md、dd-04-virtualization.md
 *
 * 暴露的 pass：
 *   - cff-flatten       仅控制流平坦化
 *   - mba               仅非线性 MBA（加法/异或恒等式）
 *   - opaque-predicates 仅不透明谓词
 *   - vm-virtualize     仅代码虚拟化（整型叶子函数 -> 自定义 ISA 字节码）
 *   - anti-rea          按 ANTI_REA_STRATEGIES 组合施加（默认 cff,mba,opaque）
 *
 * 配置（环境变量，见 engine/README.md；clang -fpass-plugin 下 cl::opt 注册晚于
 * 命令行解析，故不用 -mllvm）：
 *   ANTI_REA_WHITELIST      IR 变换白名单（FR-C6）
 *   ANTI_REA_VMP_WHITELIST  虚拟化白名单（命中者只做 VM）
 *   ANTI_REA_STRATEGIES     cff,mba,opaque,virtualize 子集
 *   ANTI_REA_SEED           随机种子（可复现）
 *
 * 关键约束（见 dd-03 §2）：CFF/VM 前须 reg2mem（消除跨块 SSA 支配依赖）；
 * 变换应在优化流水线末端执行。
 */
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DebugInfo.h"
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
#include "llvm/Transforms/Utils/CodeExtractor.h"

#include "spi/transform_plugin.h"
#include "vm_isa.h"

#include <cstdlib>
#include <dlfcn.h>
#include <functional>
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
static bool vmpWhitelisted(StringRef Name) {
  static std::set<std::string> WL = splitCSV(envStr("ANTI_REA_VMP_WHITELIST", ""));
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

// ------------------------- 虚拟化（FR-C7，R2）-------------------------
// 将整型叶子函数 lower 为自定义 ISA 字节码，函数体替换为调用 VM 解释器。
// 设计：docs/design/ddd/dd-04-virtualization.md §3/§4
// v0.1 边界：仅整型；无浮点/聚合/指针运算/函数调用；不支持者跳过并回退 IR 变换。

static bool isVMInt(Type *T) {
  return T->isIntegerTy() && T->getIntegerBitWidth() <= 64;
}

static bool vmEligible(Function &F) {
  if (F.isDeclaration()) return false;
  if (!isVMInt(F.getReturnType())) return false;
  for (Argument &A : F.args())
    if (!isVMInt(A.getType())) return false;
  for (BasicBlock &BB : F) {
    Instruction *T = BB.getTerminator();
    if (!(isa<BranchInst>(T) || isa<SwitchInst>(T) || isa<ReturnInst>(T) ||
          isa<UnreachableInst>(T)))
      return false;
    for (Instruction &I : BB) {
      if (isa<AllocaInst>(&I)) {
        auto *AI = cast<AllocaInst>(&I);
        if (!isVMInt(AI->getAllocatedType())) return false;
      } else if (auto *LI = dyn_cast<LoadInst>(&I)) {
        if (!isVMInt(LI->getType())) return false;
        if (!isa<AllocaInst>(LI->getPointerOperand())) return false;
      } else if (auto *SI = dyn_cast<StoreInst>(&I)) {
        if (!isVMInt(SI->getValueOperand()->getType())) return false;
        if (!isa<AllocaInst>(SI->getPointerOperand())) return false;
      } else if (auto *BO = dyn_cast<BinaryOperator>(&I)) {
        if (!isVMInt(BO->getType())) return false;
        switch (BO->getOpcode()) {
        case Instruction::Add: case Instruction::Sub: case Instruction::Mul:
        case Instruction::And: case Instruction::Or: case Instruction::Xor:
        case Instruction::Shl: case Instruction::LShr: case Instruction::AShr:
          break;
        default: return false;
        }
      } else if (auto *CI = dyn_cast<ICmpInst>(&I)) {
        if (!isVMInt(CI->getOperand(0)->getType())) return false;
        switch (CI->getPredicate()) {
        case CmpInst::ICMP_EQ: case CmpInst::ICMP_NE:
        case CmpInst::ICMP_SGT: case CmpInst::ICMP_SGE:
        case CmpInst::ICMP_SLT: case CmpInst::ICMP_SLE:
          break;
        default: return false;  // 暂不支持无符号比较
        }
      } else if (isa<TruncInst>(&I) || isa<ZExtInst>(&I) || isa<SExtInst>(&I)) {
        if (!isVMInt(I.getType())) return false;
      } else if (auto *Sel = dyn_cast<SelectInst>(&I)) {
        if (!isVMInt(Sel->getType())) return false;
      } else if (auto *BC = dyn_cast<BitCastInst>(&I)) {
        // 放行 no-op bitcast（reg2mem alloca point 标记）
        if (BC->getType() != BC->getOperand(0)->getType()) return false;
      } else if (isa<BranchInst>(&I) || isa<SwitchInst>(&I) ||
                 isa<ReturnInst>(&I) || isa<UnreachableInst>(&I)) {
        // 端子，单独处理
      } else {
        return false;  // 调用/PHI/GEP/Select/浮点等一律回退
      }
    }
  }
  return true;
}

static bool applyVM(Function &F, uint32_t Seed) {
  if (!vmEligible(F)) return false;

  LLVMContext &Ctx = F.getContext();
  unsigned NArgs = F.arg_size();

  // 寄存器分配：参数 -> 0..n-1；alloca -> 随后；临时值按需分配
  std::map<Value *, unsigned> Reg;
  unsigned Next = 0;
  for (Argument &A : F.args()) Reg[&A] = A.getArgNo();
  Next = NArgs;
  std::map<AllocaInst *, unsigned> Slot;
  for (BasicBlock &BB : F)
    for (Instruction &I : BB)
      if (auto *AI = dyn_cast<AllocaInst>(&I)) {
        Slot[AI] = Next++;
        Reg[&I] = Slot[AI];
      }

  // 字节码缓冲与编码表
  std::vector<unsigned char> Code;
  unsigned char Enc[32], Dec[32];
  anti_rea_vm_tables(Seed, Enc, Dec);
  auto op = [&](unsigned char real) { Code.push_back(Enc[real]); };
  auto u8 = [&](uint8_t v) { Code.push_back(v); };
  auto u16 = [&](uint16_t v) { u8(v & 0xff); u8((v >> 8) & 0xff); };
  auto u32 = [&](uint32_t v) { for (int i = 0; i < 4; i++) u8((v >> (8 * i)) & 0xff); };
  auto u64 = [&](uint64_t v) { for (int i = 0; i < 8; i++) u8((v >> (8 * i)) & 0xff); };

  std::map<BasicBlock *, uint32_t> Offset;
  std::vector<std::pair<size_t, BasicBlock *>> Fixups;
  bool Overflow = false;

  // 取寄存器（常量为即时数；其定义值须已在 Reg 中）
  std::function<unsigned(Value *)> R = [&](Value *V) -> unsigned {
    if (auto *CI = dyn_cast<ConstantInt>(V)) {
      if (Next >= ANTI_REA_VM_NREG) { Overflow = true; return 0; }
      unsigned r = Next++;
      op(OP_MOVI); u16((uint16_t)r); u64((uint64_t)CI->getSExtValue());
      return r;
    }
    auto it = Reg.find(V);
    return it == Reg.end() ? 0 : it->second;
  };
  auto sext32 = [&](unsigned r) {  // 符号扩展低 32 位（i32 不变量）
    op(OP_SHL); u16(r); u16(r); u8(32);
    op(OP_SRA); u16(r); u16(r); u8(32);
  };
  auto zext32 = [&](unsigned r) {
    op(OP_SHL); u16(r); u16(r); u8(32);
    op(OP_SHR); u16(r); u16(r); u8(32);
  };
  auto tmp = [&]() -> unsigned {
    if (Next >= ANTI_REA_VM_NREG) { Overflow = true; return 0; }
    return Next++;
  };

  for (BasicBlock &BB : F) {
    Offset[&BB] = (uint32_t)Code.size();
    for (Instruction &I : BB) {
      if (isa<AllocaInst>(&I) || isa<BranchInst>(&I) || isa<SwitchInst>(&I) ||
          isa<ReturnInst>(&I) || isa<UnreachableInst>(&I))
        continue;
      if (auto *LI = dyn_cast<LoadInst>(&I)) {
        unsigned d = tmp();
        op(OP_MOVE); u16((uint16_t)d);
        u16((uint16_t)Slot[cast<AllocaInst>(LI->getPointerOperand())]);
        Reg[&I] = d;
      } else if (auto *SI = dyn_cast<StoreInst>(&I)) {
        unsigned v = R(SI->getValueOperand());
        op(OP_MOVE);
        u16((uint16_t)Slot[cast<AllocaInst>(SI->getPointerOperand())]);
        u16((uint16_t)v);
      } else if (auto *BO = dyn_cast<BinaryOperator>(&I)) {
        unsigned a = R(BO->getOperand(0)), b = R(BO->getOperand(1)), d = tmp();
        unsigned char o = OP_ADD;
        switch (BO->getOpcode()) {
        case Instruction::Add: o = OP_ADD; break;
        case Instruction::Sub: o = OP_SUB; break;
        case Instruction::Mul: o = OP_MUL; break;
        case Instruction::And: o = OP_AND; break;
        case Instruction::Or:  o = OP_OR;  break;
        case Instruction::Xor: o = OP_XOR; break;
        case Instruction::Shl: o = OP_SHLV; break;
        case Instruction::LShr: o = OP_SHRV; break;
        case Instruction::AShr: o = OP_SRAV; break;
        default: break;
        }
        op(o); u16((uint16_t)d); u16((uint16_t)a); u16((uint16_t)b);
        if (BO->getType()->getIntegerBitWidth() == 32) sext32(d);
        Reg[&I] = d;
      } else if (auto *CI = dyn_cast<ICmpInst>(&I)) {
        unsigned a = R(CI->getOperand(0)), b = R(CI->getOperand(1)), d = tmp();
        unsigned char o = OP_CMPEQ;
        switch (CI->getPredicate()) {
        case CmpInst::ICMP_EQ:  o = OP_CMPEQ;  break;
        case CmpInst::ICMP_NE:  o = OP_CMPNE;  break;
        case CmpInst::ICMP_SLT: o = OP_CMPSLT; break;
        case CmpInst::ICMP_SLE: o = OP_CMPSLE; break;
        case CmpInst::ICMP_SGT: o = OP_CMPSGT; break;
        case CmpInst::ICMP_SGE: o = OP_CMPSGE; break;
        default: break;
        }
        op(o); u16((uint16_t)d); u16((uint16_t)a); u16((uint16_t)b);
        Reg[&I] = d;
      } else if (isa<TruncInst>(&I)) {
        unsigned a = R(I.getOperand(0)), d = tmp();
        op(OP_MOVE); u16((uint16_t)d); u16((uint16_t)a);
        if (I.getType()->getIntegerBitWidth() == 32) sext32(d);
        Reg[&I] = d;
      } else if (isa<ZExtInst>(&I)) {
        unsigned a = R(I.getOperand(0)), d = tmp();
        op(OP_MOVE); u16((uint16_t)d); u16((uint16_t)a);
        if (I.getOperand(0)->getType()->getIntegerBitWidth() == 32) zext32(d);
        Reg[&I] = d;
      } else if (isa<SExtInst>(&I)) {
        unsigned a = R(I.getOperand(0)), d = tmp();
        op(OP_MOVE); u16((uint16_t)d); u16((uint16_t)a);
        Reg[&I] = d;
      } else if (auto *Sel = dyn_cast<SelectInst>(&I)) {
        // 无分支 select：d = b ^ ((a ^ b) & (0 - (c != 0)))
        unsigned c = R(Sel->getCondition());
        unsigned a = R(Sel->getTrueValue()), b = R(Sel->getFalseValue());
        unsigned z = tmp();
        op(OP_MOVI); u16((uint16_t)z); u64(0);
        unsigned ne = tmp();
        op(OP_CMPNE); u16((uint16_t)ne); u16((uint16_t)c); u16((uint16_t)z);
        unsigned mask = tmp();
        op(OP_SUB); u16((uint16_t)mask); u16((uint16_t)z); u16((uint16_t)ne);
        unsigned xa = tmp();
        op(OP_XOR); u16((uint16_t)xa); u16((uint16_t)a); u16((uint16_t)b);
        unsigned t2 = tmp();
        op(OP_AND); u16((uint16_t)t2); u16((uint16_t)xa); u16((uint16_t)mask);
        unsigned d = tmp();
        op(OP_XOR); u16((uint16_t)d); u16((uint16_t)b); u16((uint16_t)t2);
        if (Sel->getType()->getIntegerBitWidth() == 32) sext32(d);
        Reg[&I] = d;
      } else if (auto *BC = dyn_cast<BitCastInst>(&I)) {
        (void)BC;
        Reg[&I] = R(I.getOperand(0));
      }
    }
    // 端子
    Instruction *T = BB.getTerminator();
    if (auto *RI = dyn_cast<ReturnInst>(T)) {
      unsigned r = RI->getReturnValue() ? R(RI->getReturnValue()) : 0;
      op(OP_RET); u16((uint16_t)r);
    } else if (auto *Br = dyn_cast<BranchInst>(T)) {
      if (Br->isUnconditional()) {
        op(OP_JMP);
        Fixups.push_back({Code.size(), Br->getSuccessor(0)}); u32(0);
      } else {
        unsigned c = R(Br->getCondition());
        op(OP_JNZ); u16((uint16_t)c);
        Fixups.push_back({Code.size(), Br->getSuccessor(0)}); u32(0);
        op(OP_JMP);
        Fixups.push_back({Code.size(), Br->getSuccessor(1)}); u32(0);
      }
    } else if (auto *Sw = dyn_cast<SwitchInst>(T)) {
      unsigned c = R(Sw->getCondition());
      for (auto &Case : Sw->cases()) {
        unsigned v = R(Case.getCaseValue());
        unsigned d = tmp();
        op(OP_CMPEQ); u16((uint16_t)d); u16((uint16_t)c); u16((uint16_t)v);
        op(OP_JNZ); u16((uint16_t)d);
        Fixups.push_back({Code.size(), Case.getCaseSuccessor()}); u32(0);
      }
      unsigned dd = tmp();
      op(OP_MOVI); u16((uint16_t)dd); u64(1);  // 无条件
      op(OP_JNZ); u16((uint16_t)dd);
      Fixups.push_back({Code.size(), Sw->getDefaultDest()}); u32(0);
    } else {  // unreachable
      op(OP_HALT);
    }
  }
  op(OP_HALT);

  if (Overflow) return false;

  // 回填跳转目标
  for (auto &fx : Fixups) {
    uint32_t t = Offset[fx.second];
    Code[fx.first + 0] = (unsigned char)(t & 0xff);
    Code[fx.first + 1] = (unsigned char)((t >> 8) & 0xff);
    Code[fx.first + 2] = (unsigned char)((t >> 16) & 0xff);
    Code[fx.first + 3] = (unsigned char)((t >> 24) & 0xff);
  }

  Module *M = F.getParent();
  Module &Mod = *M;
  auto *I8 = IntegerType::get(Ctx, 8);
  auto *I32 = IntegerType::get(Ctx, 32);
  auto *I64 = IntegerType::get(Ctx, 64);
  auto *PtrTy = PointerType::getUnqual(Ctx);
  auto *ArrTy = ArrayType::get(I8, Code.size());

  Constant *CDA = ConstantDataArray::get(Ctx, ArrayRef<uint8_t>(Code));
  auto *GV = new GlobalVariable(Mod, ArrTy, /*isConstant=*/true,
                                GlobalValue::PrivateLinkage, CDA,
                                "__anti_rea_vm_code_" + F.getName().str());

  FunctionCallee Run = Mod.getOrInsertFunction(
      "anti_rea_vm_run",
      FunctionType::get(I64, {PtrTy, I64, PtrTy, I32, I32, I32}, false));

  // 用「调用解释器」替换函数体
  BasicBlock *NewEntry = BasicBlock::Create(Ctx, "vm.entry", &F);
  IRBuilder<> B(NewEntry);
  unsigned ArrN = NArgs ? NArgs : 1;
  auto *ArgsTy = ArrayType::get(I64, ArrN);
  AllocaInst *ArgsArr = B.CreateAlloca(ArgsTy, nullptr, "vm.args");
  for (unsigned i = 0; i < NArgs; i++) {
    Value *A = F.getArg(i);
    Value *Ext = A;
    if (A->getType()->getIntegerBitWidth() < 64)
      Ext = B.CreateSExt(A, I64);
    Value *P = B.CreateGEP(ArgsTy, ArgsArr,
                           {ConstantInt::get(I32, 0), ConstantInt::get(I32, i)});
    B.CreateStore(Ext, P);
  }
  Value *CodeLen = ConstantInt::get(I64, (uint64_t)Code.size());
  Value *NArgsC = ConstantInt::get(I32, (uint32_t)NArgs);
  Value *SeedC = ConstantInt::get(I32, Seed);
  Value *NRegsC = ConstantInt::get(I32, Next);
  CallInst *Call = B.CreateCall(Run, {GV, CodeLen, ArgsArr, NArgsC, SeedC, NRegsC});
  Value *RV = Call;
  if (F.getReturnType()->getIntegerBitWidth() < 64)
    RV = B.CreateTrunc(Call, F.getReturnType());
  B.CreateRet(RV);

  std::vector<BasicBlock *> Old;
  for (BasicBlock &BB : F)
    if (&BB != NewEntry) Old.push_back(&BB);
  for (BasicBlock *BB : Old) BB->eraseFromParent();
  return true;
}

// ------------------------- 函数边界扰动（FR-C4）-------------------------
// 用 CodeExtractor 将单个非入口基本块外提为新函数，改变反编译器的函数识别数；
// 语义不变（由 CodeExtractor 构造保证，随后由验证层差分确认）。
// 前向声明：派生名（拆分/加密产物）在生成处即取不透明名，堵住「后缀保留原名」的泄漏。
static std::string opaqueName(StringRef Base, const char *Prefix, unsigned Seed);

static bool applyFuncSplit(Function &F, unsigned Seed) {
  if (F.isDeclaration() || F.size() < 3) return false;
  if (F.hasFnAttribute("anti-rea-nosplit")) return false;  // 防重复拆分（新增函数回访）
  if (unsupportedTerminator(F.getEntryBlock().getTerminator())) return false;

  BasicBlock *Cand = nullptr;
  unsigned idx = 0, pick = Seed % F.size();
  for (BasicBlock &BB : F) {
    if (&BB == &F.getEntryBlock()) continue;
    if (isa<PHINode>(BB.begin())) continue;
    auto *Br = dyn_cast<BranchInst>(BB.getTerminator());
    if (!Br || !Br->isUnconditional()) continue;
    if (idx++ == pick || !Cand) Cand = &BB;
  }
  if (!Cand) return false;
  if (unsupportedTerminator(Cand->getTerminator())) return false;

  CodeExtractorAnalysisCache CEAC(F);
  CodeExtractor Extractor({Cand});
  Function *NewF = Extractor.extractCodeRegion(CEAC);
  if (!NewF) return false;
  // CodeExtractor 默认命名为 "<原函数>.extracted"，会把原函数名写进符号表；改为不透明名。
  NewF->setName(opaqueName(F.getName(), "part", Seed));
  NewF->addFnAttr(Attribute::NoInline);
  NewF->addFnAttr("anti-rea-nosplit");
  F.addFnAttr("anti-rea-nosplit");
  return true;
}

// ------------------------- 数据流噪声（FR-C5）-------------------------
// 对整型二元运算注入无副作用冗余：v -> ((v + k) - k)，k 取自可变全局（不可常量折叠）。
static GlobalVariable *noiseGlobal(Module *M, Type *Ty) {
  std::string Name = "__anti_rea_noise_" +
                     std::to_string(Ty->getIntegerBitWidth());
  if (GlobalVariable *G = M->getGlobalVariable(Name)) return G;
  return new GlobalVariable(*M, Ty, /*isConstant=*/false,
                            GlobalValue::PrivateLinkage,
                            ConstantInt::get(Ty, 0x5bd1e995u), Name);
}

static bool applyNoise(Function &F, unsigned Seed) {
  double ratio = 1.0;
  if (const char *r = std::getenv("ANTI_REA_NOISE_RATIO")) ratio = std::atof(r);
  if (ratio <= 0.0) return false;

  unsigned long rng = Seed ? Seed : 0x2545F491u;
  auto next = [&]() { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; };

  Module *M = F.getParent();
  std::vector<BinaryOperator *> Targets;
  for (BasicBlock &BB : F)
    for (Instruction &I : BB)
      if (auto *BO = dyn_cast<BinaryOperator>(&I))
        if (BO->getType()->isIntegerTy() && !BO->getType()->isIntegerTy(1))
          Targets.push_back(BO);
  if (Targets.empty()) return false;

  bool changed = false;
  for (BinaryOperator *BO : Targets) {
    if (ratio < 1.0 && (double)(next() % 1000) / 1000.0 >= ratio) continue;
    Type *Ty = BO->getType();
    IRBuilder<> B(BO->getNextNode());
    GlobalVariable *G = noiseGlobal(M, Ty);
    LoadInst *K = B.CreateLoad(Ty, G, "noise.k");
    Value *Add = B.CreateAdd(BO, K, "noise.a");
    Value *Sub = B.CreateSub(Add, K, "noise.b");
    BO->replaceUsesWithIf(Sub, [&](Use &U) {
      auto *I = dyn_cast<Instruction>(U.getUser());
      return I != Add && I != Sub;
    });
    changed = true;
  }
  return changed;
}

// ------------------------- 标识符重命名（dd-03 §7）-------------------------
static uint64_t fnv1a(StringRef S, uint64_t Seed) {
  uint64_t H = 1469598103934665603ULL ^ Seed;
  for (unsigned char C : S) {
    H ^= C;
    H *= 1099511628211ULL;
  }
  return H;
}

static std::string opaqueName(StringRef Base, const char *Prefix, unsigned Seed) {
  char Buf[40];
  snprintf(Buf, sizeof(Buf), "%s_%016llx", Prefix,
           (unsigned long long)fnv1a(Base, Seed));
  return std::string(Buf);
}

// 将白名单内的定义函数改名为不透明符号，并按需剥离调试信息。
//   - main 永远保留；
//   - 内部链接（static/private）函数始终可安全改名；
//   - 外部链接函数由 ANTI_REA_RENAME_EXTERNAL 控制（默认 1）：其他编译单元/外部调用方
//     可能按原名引用它，而本 pass 经 clang -fpass-plugin 逐 TU 运行、无法改写那些引用，
//     改名会破坏多 TU 链接（实测 undefined reference）。故 protect 在多源构建时自动置 0。
static bool applyRename(Module &M, unsigned Seed) {
  bool Changed = false;
  const bool renameExternal = envInt("ANTI_REA_RENAME_EXTERNAL", 1) != 0;
  std::vector<Function *> Fs;
  for (Function &F : M)
    if (!F.isDeclaration()) Fs.push_back(&F);
  for (Function *F : Fs) {
    if (F->getName() == "main") continue;
    if (!whitelisted(F->getName())) continue;
    if (!F->hasLocalLinkage() && !renameExternal) continue;
    F->setName(opaqueName(F->getName(), "sub", Seed));
    Changed = true;
  }
  // 本地链接的数据全局（static 常量表/字符串）也是算法指纹（sm4_sbox/sm4_ck 一眼可辨）。
  // 本地链接仅本 TU 可见，改名安全（LLVM 自动改写 IR 内引用）；编码后的 .enc/.ks/.buf
  // 由字符串加密处理，此处跳过。
  std::vector<GlobalVariable *> Gs;
  for (GlobalVariable &G : M.globals())
    if (G.hasLocalLinkage() && !G.isDeclaration()) Gs.push_back(&G);
  for (GlobalVariable *G : Gs) {
    StringRef N = G->getName();
    if (N.empty() || N.starts_with("llvm.") || N.starts_with("__anti_rea")) continue;
    G->setName(opaqueName(N, "dat", Seed));
    Changed = true;
  }
  return Changed;
}

// 剥离调试信息（配合重命名，防止符号/行号恢复）
static bool stripDebug(Module &M) {
  bool Changed = false;
  for (Function &F : M) {
    if (stripDebugInfo(F)) Changed = true;
  }
  if (NamedMDNode *CU = M.getNamedMetadata("llvm.dbg.cu")) {
    CU->eraseFromParent();
    Changed = true;
  }
  return Changed;
}

// ------------------------- 字符串加密（dd-03 §7）-------------------------
// 密钥流：LCG 递推（编码端与运行期解码端使用同一递推，故密钥不以相邻常量出现）。
static constexpr uint64_t KS_A = 6364136223846793005ULL;
static constexpr uint64_t KS_B = 1442695040888963407ULL;
static constexpr unsigned KS_RUNTIME_MAX = 256; // 超过则退化为常量密钥（控制 IR 规模）

// 对"仅被白名单函数使用的本地整型常量数组"做异或编码，并在使用处插入运行期解码桩。
// 覆盖字节串，也覆盖算法常数表（SM4 的 S 盒 i8[256]、CK 轮常量 i32[32] 等）——
// 后者是算法身份的强指纹（经验记录 gap#7）。
static bool applyStringEncrypt(Module &M, unsigned Seed) {
  LLVMContext &Ctx = M.getContext();
  std::vector<GlobalVariable *> Targets;
  for (GlobalVariable &G : M.globals()) {
    if (!G.hasInitializer() || !G.hasLocalLinkage()) continue;
    if (G.getName().starts_with("enc_")) continue;   // 已编码（见 opaqueName）
    auto *CDA = dyn_cast<ConstantDataArray>(G.getInitializer());
    if (!CDA) continue;
    auto *ET = dyn_cast<IntegerType>(CDA->getElementType());
    if (!ET) continue;
    unsigned BW = ET->getBitWidth();
    if (BW != 8 && BW != 16 && BW != 32 && BW != 64) continue;
    if (G.use_empty()) continue;
    bool AllIn = true;
    for (User *U : G.users()) {
      auto *I = dyn_cast<Instruction>(U);
      if (!I || !whitelisted(I->getFunction()->getName())) { AllIn = false; break; }
    }
    if (AllIn) Targets.push_back(&G);
  }
  if (Targets.empty()) return false;

  bool Changed = false;
  for (GlobalVariable *G : Targets) {
    auto *CDA = cast<ConstantDataArray>(G->getInitializer());
    auto *ET = cast<IntegerType>(CDA->getElementType());
    unsigned W = ET->getBitWidth() / 8;   // 每元素字节数
    unsigned NE = (unsigned)CDA->getNumElements();
    StringRef Raw = CDA->getRawDataValues();
    unsigned N = (unsigned)Raw.size();    // 总字节数 = NE * W
    if (N == 0 || NE == 0 || N > 4096) continue;

    uint64_t St = fnv1a(G->getName(), Seed) | 1ULL;
    std::vector<uint8_t> Enc(N), Key(N);
    {
      uint64_t S = St;
      for (unsigned i = 0; i < N; ++i) {
        S = S * KS_A + KS_B;
        Key[i] = (uint8_t)(S >> 33);
        Enc[i] = (uint8_t)Raw[i] ^ Key[i];
      }
    }
    bool Runtime = (N <= KS_RUNTIME_MAX);
    Type *ArrTy = G->getValueType(); // [NE x ET]
    G->setInitializer(ConstantDataArray::getRaw(
        StringRef((const char *)Enc.data(), N), NE, ET));
    std::string NewName = opaqueName(G->getName(), "enc", Seed);
    G->setName(NewName);

    // 按使用函数分组，逐函数插入解码桩（逐元素）
    std::map<Function *, AllocaInst *> Bufs;
    std::vector<Instruction *> Users;
    for (User *U : G->users())
      if (auto *I = dyn_cast<Instruction>(U)) Users.push_back(I);

    IntegerType *I64 = IntegerType::get(Ctx, 64);
    for (Instruction *I : Users) {
      Function *F = I->getFunction();
      AllocaInst *Buf = nullptr;
      auto It = Bufs.find(F);
      if (It != Bufs.end()) {
        Buf = It->second;
      } else {
        IRBuilder<> B(&*F->getEntryBlock().getFirstInsertionPt());
        Buf = B.CreateAlloca(ArrTy, nullptr, G->getName() + ".buf");
        Value *Cur = nullptr;
        if (Runtime) {
          // 从可变全局加载种子（volatile 防常量折叠/GVN），运行期递推密钥流
          auto *KS = new GlobalVariable(
              M, I64, false, GlobalValue::PrivateLinkage,
              ConstantInt::get(I64, St), opaqueName(G->getName(), "ks", Seed));
          KS->setAlignment(Align(8));
          Cur = B.CreateLoad(I64, KS, /*isVolatile=*/true);
        }
        for (unsigned e = 0; e < NE; ++e) {
          Value *K;
          if (Runtime) {
            // 每个元素由 W 个密钥流字节按小端拼成
            Value *KV = ConstantInt::get(ET, 0);
            for (unsigned b = 0; b < W; ++b) {
              Cur = B.CreateAdd(B.CreateMul(Cur, ConstantInt::get(I64, KS_A)),
                                ConstantInt::get(I64, KS_B));
              // 密钥流每字节取 (S>>33) 的低 8 位（与编码端一致），再拼入元素
              Value *Byte = B.CreateAnd(
                  B.CreateLShr(Cur, ConstantInt::get(I64, 33)),
                  ConstantInt::get(I64, 0xFF));
              Value *KB = B.CreateTrunc(Byte, ET);
              if (b) KB = B.CreateShl(KB, ConstantInt::get(ET, 8 * b));
              KV = B.CreateOr(KV, KB);
            }
            K = KV;
          } else {
            uint64_t KE = 0;
            for (unsigned b = 0; b < W; ++b)
              KE |= (uint64_t)Key[e * W + b] << (8 * b);
            K = ConstantInt::get(ET, KE);
          }
          Value *Src = B.CreateGEP(ArrTy, G, {B.getInt64(0), B.getInt64(e)});
          LoadInst *L = B.CreateLoad(ET, Src);
          Value *X = B.CreateXor(L, K);
          Value *Dst = B.CreateGEP(ArrTy, Buf, {B.getInt64(0), B.getInt64(e)});
          B.CreateStore(X, Dst);
        }
        Bufs[F] = Buf;
      }
      I->replaceUsesOfWith(G, Buf);
    }
    Changed = true;
  }
  return Changed;
}

// 模块级变换 Pass
struct RenamePass : PassInfoMixin<RenamePass> {
  PreservedAnalyses run(Module &M, ModuleAnalysisManager &) {
    if (!strategySet().count("rename")) return PreservedAnalyses::all();
    bool Changed = applyRename(M, (unsigned)envInt("ANTI_REA_SEED", 0));
    if (envInt("ANTI_REA_STRIP_DEBUG", 1) != 0) Changed = stripDebug(M) || Changed;
    return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};
struct StringEncryptPass : PassInfoMixin<StringEncryptPass> {
  PreservedAnalyses run(Module &M, ModuleAnalysisManager &) {
    if (!strategySet().count("string_encrypt")) return PreservedAnalyses::all();
    return applyStringEncrypt(M, (unsigned)envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};

// ------------------------- 组合 Pass -------------------------
struct AntiReaPass : public PassInfoMixin<AntiReaPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    if (F.isDeclaration()) return PreservedAnalyses::all();
    static std::set<std::string> &S = strategySet();
    uint32_t seed = (uint32_t)envInt("ANTI_REA_SEED", 0);

    // 虚拟化：命中 VMP 白名单 -> 只做 VM，跳过 IR 变换（dd-04 §8）
    if (S.count("virtualize") && vmpWhitelisted(F.getName()))
      return applyVM(F, seed) ? PreservedAnalyses::none()
                              : PreservedAnalyses::all();

    if (!whitelisted(F.getName())) return PreservedAnalyses::all();
    bool changed = false;
    if (S.count("cff")) changed |= applyCFF(F, seed);
    if (S.count("mba")) changed |= applyMBA(F);
    if (S.count("opaque")) changed |= applyOpaque(F, (int)seed);
    if (S.count("func_split")) changed |= applyFuncSplit(F, seed);
    if (S.count("noise")) changed |= applyNoise(F, seed);
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
  static bool isRequired() { return true; }
};
struct MBAPass : PassInfoMixin<MBAPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyMBA(F) ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};
struct OpaquePass : PassInfoMixin<OpaquePass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyOpaque(F, envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};
struct VMPass : PassInfoMixin<VMPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyVM(F, (uint32_t)envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};
struct FuncSplitPass : PassInfoMixin<FuncSplitPass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyFuncSplit(F, (unsigned)envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};
struct NoisePass : PassInfoMixin<NoisePass> {
  PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
    return applyNoise(F, (unsigned)envInt("ANTI_REA_SEED", 0))
               ? PreservedAnalyses::none()
               : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
};

// ------------------------- 外部插件宿主（FR-C11 / ADR-005）-------------------------
// 读取 ANTI_REA_EXTRA_PLUGINS（逗号分隔 .so 路径），dlopen 后校验 anti_rea_spi_version()；
// 版本不匹配即拒载（E_PLUGIN_INCOMPATIBLE），不影响核心引擎。仅对 ANTI_REA_STRATEGIES
// 中请求的策略执行 apply()。
struct ExternalPluginPass : PassInfoMixin<ExternalPluginPass> {
  PreservedAnalyses run(Module &M, ModuleAnalysisManager &) {
    std::string list = envStr("ANTI_REA_EXTRA_PLUGINS", "");
    if (list.empty()) return PreservedAnalyses::all();

    std::set<std::string> Want = splitCSV(envStr("ANTI_REA_STRATEGIES", ""));
    uint64_t Seed = (uint64_t)envInt("ANTI_REA_SEED", 0);
    bool Changed = false;

    for (const std::string &Path : splitCSV(list)) {
      void *H = dlopen(Path.c_str(), RTLD_NOW | RTLD_LOCAL);
      if (!H) {
        errs() << "anti-rea: E_PLUGIN_INCOMPATIBLE: " << Path << ": "
               << (dlerror() ? dlerror() : "dlopen 失败") << "\n";
        continue;
      }
      auto Ver = (int (*)())dlsym(H, "anti_rea_spi_version");
      auto Reg = (anti_rea::TransformPlugin * (*)())
          dlsym(H, "anti_rea_register_plugin");
      if (!Ver || !Reg) {
        errs() << "anti-rea: E_PLUGIN_INCOMPATIBLE: " << Path
               << ": 缺少 anti_rea_spi_version/anti_rea_register_plugin\n";
        continue;
      }
      if (Ver() != anti_rea::SPI_VERSION) {
        errs() << "anti-rea: E_PLUGIN_INCOMPATIBLE: " << Path
               << ": spi=" << Ver() << " host=" << anti_rea::SPI_VERSION
               << "\n";
        continue;
      }
      anti_rea::TransformPlugin *P = Reg();
      if (!P) {
        errs() << "anti-rea: E_PLUGIN_INCOMPATIBLE: " << Path
               << ": register_plugin 返回空\n";
        continue;
      }
      anti_rea::TransformCapabilities Cap = P->capabilities();
      if (!Want.empty() && !Want.count(Cap.name)) continue; // 未请求该策略
      anti_rea::Config Cfg{"{}"};
      std::string Err;
      if (!P->validate(Cfg, Err)) {
        errs() << "anti-rea: E_PLUGIN_INCOMPATIBLE: " << Cap.name << ": " << Err
               << "\n";
        continue;
      }
      anti_rea::Result R = P->apply(M, Cfg, Seed);
      if (!R.ok) {
        errs() << "anti-rea: E_TRANSFORM_FAILED: " << Cap.name << ": " << R.detail
               << "\n";
        continue;
      }
      errs() << "anti-rea: 外部插件 " << Cap.name << " applied (" << R.detail
             << ")\n";
      Changed = true;
    }
    return Changed ? PreservedAnalyses::none() : PreservedAnalyses::all();
  }
  static bool isRequired() { return true; }
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
                  if (Name == "vm-virtualize") { FPM.addPass(VMPass()); return true; }
                  if (Name == "func-split") { FPM.addPass(FuncSplitPass()); return true; }
                  if (Name == "data-flow-noise") { FPM.addPass(NoisePass()); return true; }
                  if (Name == "anti-rea") { FPM.addPass(AntiReaPass()); return true; }
                  return false;
                });
            PB.registerPipelineParsingCallback(
                [](StringRef Name, ModulePassManager &MPM,
                   ArrayRef<PassBuilder::PipelineElement>) {
                  if (Name == "external-transforms") {
                    MPM.addPass(ExternalPluginPass());
                    return true;
                  }
                  if (Name == "string-encrypt") {
                    MPM.addPass(StringEncryptPass());
                    return true;
                  }
                  if (Name == "ident-rename") {
                    MPM.addPass(RenamePass());
                    return true;
                  }
                  return false;
                });
            // clang -fpass-plugin 路径：末端挂 [字符串加密] -> reg2mem+anti-rea -> [重命名] -> 外部插件
            PB.registerOptimizerLastEPCallback(
                [](ModulePassManager &MPM, OptimizationLevel) {
                  MPM.addPass(StringEncryptPass());
                  FunctionPassManager FPM;
                  FPM.addPass(RegToMemPass());
                  FPM.addPass(AntiReaPass());
                  MPM.addPass(createModuleToFunctionPassAdaptor(std::move(FPM)));
                  MPM.addPass(RenamePass());
                  MPM.addPass(ExternalPluginPass());
                });
          }};
}
