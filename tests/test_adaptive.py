"""自适应引擎测试（FR-F1…F4）。"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import common  # noqa: E402
from core.adaptive import evolve, export_policy  # noqa: E402
from core.adaptive import genome, knowledge, weakness  # noqa: E402
from core.evaluate import metrics as M  # noqa: E402

ASSETS = [
    {"path": "src/crypto.c", "type": "crypto", "sensitivity": "P0"},
    {"path": "src/core.c", "type": "business_logic", "sensitivity": "P1"},
    {"path": "src/util.c", "type": "util", "sensitivity": "P3"},
]


class TestGenome(unittest.TestCase):
    def test_genome_len_and_decode(self):
        self.assertEqual(genome.genome_len(ASSETS), 15 * len(ASSETS))
        ind = [1.0] * genome.genome_len(ASSETS)
        decoded = genome.decode(ind, ASSETS)
        self.assertEqual(len(decoded), 3)
        self.assertEqual(len(decoded[0][1]), 11)          # 全部策略选中
        self.assertIn("coverage", decoded[0][2])

    def test_fitness_from_metrics(self):
        ind = [1.0] * genome.genome_len(ASSETS)
        fit = genome.fitness_from_metrics(ind, ASSETS,
                                          {"name_recovery_accuracy": 0.0,
                                           "bin_similarity": 0.0,
                                           "function_judgement_accuracy": 0.0,
                                           "vuln_discovery_rate": 0.0})
        self.assertGreater(fit[0], 0.9)                   # 全部达成目标


class TestEvolve(unittest.TestCase):
    def test_non_degrade_and_schema(self):
        res = evolve(ASSETS, seed=11, pop=24, gens=6)
        self.assertTrue(res["non_degrade"], res)
        self.assertGreaterEqual(res["best_fitness"], res["initial_fitness"])
        common.validate(res["best_policy"], "protection_policy.schema.json")
        self.assertEqual(len(res["best_policy"]["assets"]), 3)

    def test_determinism_same_seed(self):
        a = evolve(ASSETS, seed=42, pop=20, gens=5)
        b = evolve(ASSETS, seed=42, pop=20, gens=5)
        self.assertEqual(a["best_fitness"], b["best_fitness"])

    def test_export_policy_roundtrip(self):
        ind = [0.0] * genome.genome_len(ASSETS)
        ind[0] = 1.0                                      # 第一个策略：code_virtualization
        pol = export_policy(ind, ASSETS, seed=1)
        self.assertEqual(pol["schema_version"], "1.0")
        self.assertIn("code_virtualization", pol["assets"][0]["strategies"])


class TestKnowledge(unittest.TestCase):
    def test_signature_and_recommend(self):
        sig = knowledge.signature("c", ASSETS)
        self.assertEqual(sig, knowledge.signature("c", ASSETS))
        with tempfile.TemporaryDirectory() as t:
            kb = os.path.join(t, "kb.json")
            self.assertIsNone(knowledge.recommend(kb, sig))
            knowledge.save(kb, {"signature": sig, "seed": 1, "fitness": 0.3,
                                "policy": {"assets": []}})
            knowledge.save(kb, {"signature": sig, "seed": 2, "fitness": 0.9,
                                "policy": {"assets": []}})
            best = knowledge.recommend(kb, sig)
            self.assertEqual(best["seed"], 2)             # 迁移推荐取最高分


class TestWeakness(unittest.TestCase):
    def test_detect_and_adjust(self):
        w = weakness.detect({"name_recovery_accuracy": 0.6,
                             "bin_similarity": 0.9,
                             "function_judgement_accuracy": 0.0})
        metrics = {x["metric"] for x in w}
        self.assertEqual(metrics, {"name_recovery_accuracy", "bin_similarity"})

        policy = {"assets": [
            {"path": "a.c", "sensitivity": "P0", "strategies": ["non_linear_mba"]},
            {"path": "b.c", "sensitivity": "P3", "strategies": []},
        ]}
        adj = weakness.adjust(policy, w)
        self.assertIn("identifier_renaming", adj["assets"][0]["strategies"])
        self.assertEqual(adj["assets"][1]["strategies"], [])   # P3 不强化
        # 原策略不被改动
        self.assertNotIn("identifier_renaming", policy["assets"][0]["strategies"])

    def test_record_appends(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "wr.json")
            weakness.record(p, "run-1", [{"metric": "bin_similarity"}])
            weakness.record(p, "run-2", [{"metric": "bin_similarity"}])
            data = common.read_json(p)
            self.assertEqual(len(data["records"]), 2)


if __name__ == "__main__":
    unittest.main()
