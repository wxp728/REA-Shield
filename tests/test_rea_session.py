"""独立会话攻击编排测试（FR-E3）。用假 `ANTI_REA_LLM_CMD` 离线可复现。"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.evaluate import rea_session  # noqa: E402
from core.evaluate.attack_sim import attack_sim  # noqa: E402

TARGETS = [
    {"symbol": "secret_schedule", "name": "secret_schedule",
     "category": "crypto", "secret": "3b7e1516"},
]


class TestScore(unittest.TestCase):
    def test_correct_recovery_hits_all_signals(self):
        out = json.dumps({"functions": [{"descriptor": "f1", "name": "secret_schedule",
                                         "category": "crypto"}],
                          "secrets": ["3b7e1516"], "notes": "x"})
        s = rea_session.score(out, TARGETS)
        self.assertEqual(s["name_recovery_accuracy"], 1.0)
        self.assertEqual(s["function_judgement_accuracy"], 1.0)
        self.assertTrue(s["signals"]["S1_function_judgement"])
        self.assertTrue(s["signals"]["S2_name_recovery"])
        self.assertTrue(s["signals"]["S4_secret_extraction"])
        self.assertTrue(s["rea_success"])

    def test_wrong_recovery_no_signal(self):
        out = json.dumps({"functions": [{"descriptor": "f1", "name": "sub_1234",
                                         "category": "other"}],
                          "secrets": [], "notes": "x"})
        s = rea_session.score(out, TARGETS)
        self.assertFalse(s["rea_success"])
        self.assertEqual(s["name_recovery_accuracy"], 0.0)

    def test_tolerates_code_fence_and_noise(self):
        out = "分析如下：\n```json\n{\"functions\": [{\"name\": \"secret_schedule\", " \
              "\"category\": \"crypto\"}], \"secrets\": []}\n```\n完毕"
        s = rea_session.score(out, TARGETS)
        self.assertTrue(s["signals"]["S2_name_recovery"])

    def test_parse_garbage(self):
        s = rea_session.score("no json here", TARGETS)
        self.assertFalse(s["rea_success"])


class TestSessionAndAttackSim(unittest.TestCase):
    def _fake_llm(self, d: str) -> str:
        """写一个假 LLM 钩子：读 stdin，按 FAKE_LLM_MODE 返回不同结果。"""
        path = os.path.join(d, "fake_llm.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                "import json, os, sys\n"
                "p = sys.stdin.read()\n"
                "mode = os.environ.get('FAKE_LLM_MODE', 'recover')\n"
                "if mode == 'recover':\n"
                "    payload = {'functions': [{'descriptor': 'x', 'name': 'secret_schedule',\n"
                "                'category': 'crypto'}], 'secrets': ['3b7e1516'], 'notes': 'n'}\n"
                "else:\n"
                "    payload = {'functions': [{'descriptor': 'x', 'name': 'func_9',\n"
                "                'category': 'other'}], 'secrets': [], 'notes': 'n'}\n"
                "print(json.dumps({'output': json.dumps(payload), 'tokens_used': len(p)}))\n"
            )
        return "%s %s" % (sys.executable, path)

    def _artifacts(self, d: str) -> str:
        """造一个最小 artifacts 目录（metadata + 两个伪产物）。"""
        out = os.path.join(d, "run")
        os.makedirs(os.path.join(out, "artifacts"))
        base = os.path.join(out, "artifacts", "baseline")
        prot = os.path.join(out, "artifacts", "protected")
        with open(base, "w", encoding="utf-8") as fh:
            fh.write("baseline binary placeholder\n")
        with open(prot, "w", encoding="utf-8") as fh:
            fh.write("protected binary placeholder\n")
        with open(os.path.join(out, "metadata.json"), "w", encoding="utf-8") as fh:
            json.dump({"run_id": "run-test", "baseline_exe": base,
                       "protected_exe": prot}, fh)
        return out

    def test_run_session_with_fake_llm(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["ANTI_REA_LLM_CMD"] = self._fake_llm(d)
            os.environ["FAKE_LLM_MODE"] = "recover"
            try:
                s = rea_session.run_session("/bin/true", TARGETS)
            finally:
                os.environ.pop("ANTI_REA_LLM_CMD", None)
            self.assertGreater(s["tokens"], 0)
            self.assertEqual(s["name_recovery_accuracy"], 1.0)
            self.assertTrue(s["rea_success"])

    def test_attack_sim_llm_recovered_fails(self):
        """假 LLM 成功恢复 -> REA 成功 -> verdict 不通过。"""
        with tempfile.TemporaryDirectory() as d:
            out = self._artifacts(d)
            os.environ["ANTI_REA_LLM_CMD"] = self._fake_llm(d)
            os.environ["FAKE_LLM_MODE"] = "recover"
            try:
                rep = attack_sim(out, benchmark=os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "benchmarks", "bench-crypto-001.yaml"), allow_llm=True)
            finally:
                os.environ.pop("ANTI_REA_LLM_CMD", None)
            self.assertIn("llm", rep)
            self.assertTrue(rep["metrics"]["rea_success"])
            self.assertFalse(rep["verdict"]["pass"])
            self.assertIn("token_ratio", rep["metrics"])
            self.assertIn("baseline", rep)
            self.assertIn("protected", rep)

    def test_attack_sim_llm_failed_passes(self):
        """假 LLM 未恢复、上下文未耗尽 -> verdict 通过。"""
        with tempfile.TemporaryDirectory() as d:
            out = self._artifacts(d)
            os.environ["ANTI_REA_LLM_CMD"] = self._fake_llm(d)
            os.environ["FAKE_LLM_MODE"] = "fail"
            try:
                rep = attack_sim(out, benchmark=os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "benchmarks", "bench-crypto-001.yaml"), allow_llm=True)
            finally:
                os.environ.pop("ANTI_REA_LLM_CMD", None)
            self.assertFalse(rep["metrics"]["rea_success"])
            self.assertTrue(rep["verdict"]["pass"])


if __name__ == "__main__":
    unittest.main()
