"""评估验证层测试（FR-E1…E7、FR-G1…G3、OI-07 判定）。

含纯函数判定（OI-07 D3/D4/D5）与端到端攻击模拟（工具链可用时）。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core import report  # noqa: E402
from core.scanner import scan  # noqa: E402
from core.strategy import plan  # noqa: E402
from core.transform import protect, _clang, _find_plugin  # noqa: E402
from core.evaluate import verify, attack_sim  # noqa: E402
from core.evaluate import metrics as M  # noqa: E402
from core.evaluate import static_features as SF  # noqa: E402
from core.evaluate import timeseries as TS  # noqa: E402
from core.evaluate import regression as RG  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
P0_SECRET = os.path.join(SAMPLES, "p0_secret.c")
BENCH = os.path.join(REPO, "benchmarks", "bench-crypto-001.yaml")


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


class TestJudge(unittest.TestCase):
    """OI-07 D3/D4/D5 判定口径。"""

    def test_success_fails_regardless_of_ratio(self):
        v = M.judge({"bin_similarity": 0.1}, ratio=0.99, rea_success=True)
        self.assertFalse(v["pass"])

    def test_unsuccess_with_full_context_passes(self):
        v = M.judge({"bin_similarity": 0.1}, ratio=0.95, rea_success=False)
        self.assertTrue(v["pass"])

    def test_unsuccess_early_termination_passes_with_note(self):
        v = M.judge({"bin_similarity": 0.1}, ratio=0.10, rea_success=False)
        self.assertTrue(v["pass"])
        self.assertTrue(any("提前结束" in r for r in v["reasons"]))

    def test_static_only_uses_thresholds(self):
        ok = M.judge({"name_recovery_accuracy": 0.0,
                      "function_judgement_accuracy": 0.0,
                      "bin_similarity": 0.4}, static_only=True)
        self.assertTrue(ok["pass"])
        bad = M.judge({"name_recovery_accuracy": 0.8,
                       "function_judgement_accuracy": 0.0,
                       "bin_similarity": 0.4}, static_only=True)
        self.assertFalse(bad["pass"])

    def test_multi_model_conservative_aggregation(self):
        agg = M.aggregate([{"pass": True, "reasons": []},
                           {"pass": False, "reasons": ["S1"]}])
        self.assertFalse(agg["pass"])            # D4：任一成功即不通过

    def test_signals_from_session(self):
        gt = {"targets": [{"symbol": "f1", "name": "crc", "category": "crypto"},
                          {"symbol": "f2", "name": "main", "category": "ui"}]}
        out = {"recovered_names": {"f1": "crc", "f2": "nope"},
               "judged_category": {"f1": "crypto", "f2": "ui"},
               "secret_hits": []}
        s = M.signals_from(out, gt)
        self.assertTrue(s["S1"])
        self.assertTrue(s["S2"])                 # 1/2 名称恢复 > 0.2
        self.assertTrue(s["rea_success"])


class TestStaticFeatures(unittest.TestCase):
    def test_jaccard_and_self_similarity(self):
        self.assertEqual(SF._jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(SF._jaccard({"a"}, {"b"}), 0.0)

    def test_name_recovery(self):
        self.assertEqual(SF.name_recovery_accuracy(["a", "b"], {"a"}), 0.5)
        self.assertEqual(SF.name_recovery_accuracy([], set()), 0.0)

    def test_crt_filter(self):
        self.assertTrue(SF._is_crt("_start"))
        self.assertTrue(SF._is_crt("frame_dummy"))
        self.assertTrue(SF._is_crt("register_tm_clones"))
        self.assertFalse(SF._is_crt("secret_schedule"))


class TestTimeseries(unittest.TestCase):
    def test_record_and_history(self):
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, "m.db")
            n = TS.record(db, "run-1", "2026-10-16T00:00:00+00:00",
                          {"bin_similarity": 0.4, "name_recovery_accuracy": 0.0})
            self.assertEqual(n, 2)
            self.assertEqual(TS.latest(db, "bin_similarity"), 0.4)
            self.assertEqual(len(TS.history(db, "bin_similarity")), 1)


class TestRegression(unittest.TestCase):
    def test_compare_detects_regression(self):
        prev = {"bin_similarity": 0.30, "name_recovery_accuracy": 0.0,
                "token_ratio": 150.0}
        curr = {"bin_similarity": 0.60, "name_recovery_accuracy": 0.4,
                "token_ratio": 120.0}
        r = RG.compare(curr, prev)
        regs = {x["metric"] for x in r["regressions"]}
        self.assertEqual(regs, {"bin_similarity", "name_recovery_accuracy",
                                "token_ratio"})
        self.assertTrue(r["degraded"])
        # bin_similarity 0.60 > 目标 0.55 -> 未达标告警
        self.assertIn("bin_similarity",
                      {x["metric"] for x in r["target_violations"]})

    def test_compare_no_regression_when_improved(self):
        prev = {"bin_similarity": 0.60}
        curr = {"bin_similarity": 0.40}
        r = RG.compare(curr, prev)
        self.assertFalse(r["regressions"])
        self.assertFalse(r["degraded"])

    def test_previous_metrics_empty(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(RG.previous_metrics(os.path.join(t, "none.db"), "x"), {})


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestEvaluationPipeline(unittest.TestCase):
    def _run(self, out: str) -> str:
        manifest = scan(SAMPLES)
        policy = plan(manifest, {"max_overhead": 0.5}, seed=7)
        policy["_run_id"] = manifest["run_id"]
        os.makedirs(out, exist_ok=True)
        common.write_yaml(os.path.join(out, "protection_policy.yaml"),
                          {k: v for k, v in policy.items() if not k.startswith("_")})
        protect(policy, [P0_SECRET], out, root=SAMPLES, seed=7)
        vr = verify(out)
        common.write_json(os.path.join(out, "verification_report.json"), vr)
        return manifest["run_id"]

    def test_attack_sim_and_metrics(self):
        with tempfile.TemporaryDirectory() as out:
            self._run(out)
            rep = attack_sim(out, benchmark=BENCH, db=os.path.join(out, "m.db"))
            common.validate(rep, "eval_report.schema.json")
            m = rep["metrics"]
            self.assertEqual(m["name_recovery_accuracy"], 0.0)   # 符号已移除
            self.assertLessEqual(m["bin_similarity"], M.TH["bin_similarity_max"])
            self.assertIn("verdict", rep)

    def test_metrics_discriminate_baseline(self):
        """未保护产物应判定不通过（名称全存活、相似度=1）。"""
        with tempfile.TemporaryDirectory() as out:
            self._run(out)
            base = os.path.join(out, "artifacts", "baseline")
            met = M.compute_static(base, base, ["secret_schedule", "secret_roundtrip"])
            self.assertEqual(met["name_recovery_accuracy"], 1.0)
            self.assertEqual(met["bin_similarity"], 1.0)
            self.assertFalse(M.judge(met, static_only=True)["pass"])

    def test_report_three_formats_and_diff(self):
        with tempfile.TemporaryDirectory() as out:
            self._run(out)
            attack_sim(out, benchmark=BENCH)
            for fmt, name in (("md", "report.md"), ("json", "report.json"),
                              ("html", "report.html")):
                report.generate(out, fmt)
                self.assertTrue(os.path.exists(os.path.join(out, name)), name)
            layout = report.layout_ok(out)
            for key in ("metadata.json", "protection_policy.yaml", "artifacts",
                        "verification_report.json", "eval_report.json"):
                self.assertTrue(layout[key], key)
            d = report.diff(out, out)
            self.assertIn("strategies", d)
            self.assertEqual(d["artifacts"]["changed"], [])
            model = common.read_json(os.path.join(out, "report.json"))["model"]
            self.assertTrue(model["input_fingerprint"])
            self.assertTrue(model["policy_hash"])

    def test_dynamic_and_crossver_degrade(self):
        with tempfile.TemporaryDirectory() as out:
            self._run(out)
            rep = attack_sim(out, benchmark=BENCH, mode="all")
            common.validate(rep, "eval_report.schema.json")
            joined = " ".join(rep["verdict"]["reasons"])
            self.assertTrue("跨版本" in joined)     # 无上一版本 -> 未执行

    def test_regression_runner(self):
        """FR-E8：回归检测跑通并落 regression_report.json（首次无历史 -> 不退化）。"""
        with tempfile.TemporaryDirectory() as out:
            self._run(out)
            res = RG.regress(out, os.path.join(out, "m.db"), BENCH)
            self.assertFalse(res["degraded"], res)
            self.assertTrue(os.path.exists(
                os.path.join(out, "regression_report.json")))


if __name__ == "__main__":
    unittest.main()
