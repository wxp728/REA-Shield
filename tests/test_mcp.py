"""MCP Server 测试（FR-D6）：协议 + Agent 端到端场景（SRS §4.2，e2e-scenario §4）。"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mcp import handle, serve, TOOLS  # noqa: E402
from core.transform import _clang, _find_plugin  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(REPO, "tests", "samples")
P0_SECRET = os.path.join(SAMPLES, "p0_secret.c")
BENCH = os.path.join(REPO, "benchmarks", "bench-crypto-001.yaml")

EXPECTED = ["anti_rea.scan", "anti_rea.plan", "anti_rea.protect", "anti_rea.verify",
            "anti_rea.attack_sim", "anti_rea.report", "anti_rea.evolve"]


def _have_toolchain() -> bool:
    try:
        _find_plugin()
        _clang()
        return True
    except Exception:
        return False


def _call(name, arguments):
    resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}})
    assert resp is not None
    content = resp["result"]
    assert not content.get("isError"), content
    return json.loads(content["content"][0]["text"])


class TestProtocol(unittest.TestCase):
    def test_initialize(self):
        r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(r["result"]["serverInfo"]["name"], "anti-rea-mcp")
        self.assertIn("tools", r["result"]["capabilities"])

    def test_tools_list(self):
        r = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = [t["name"] for t in r["result"]["tools"]]
        self.assertEqual(names, EXPECTED)
        for t in r["result"]["tools"]:
            self.assertEqual(t["inputSchema"]["type"], "object")   # 每个工具暴露 JSON Schema

    def test_unknown_method_and_tool(self):
        r = handle({"jsonrpc": "2.0", "id": 3, "method": "nope", "params": {}})
        self.assertEqual(r["error"]["code"], -32601)
        r = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": "x", "arguments": {}}})
        self.assertEqual(r["error"]["code"], -32602)

    def test_notification_no_reply(self):
        self.assertIsNone(handle({"jsonrpc": "2.0",
                                  "method": "notifications/initialized"}))

    def test_serve_loop_handles_parse_error(self):
        stdin = io.StringIO("{bad json}\n" +
                            json.dumps({"jsonrpc": "2.0", "id": 5, "method": "ping"}) + "\n")
        stdout = io.StringIO()
        serve(stdin=stdin, stdout=stdout)
        lines = [json.loads(x) for x in stdout.getvalue().strip().splitlines()]
        self.assertEqual(lines[0]["error"]["code"], -32700)
        self.assertEqual(lines[1]["id"], 5)


@unittest.skipUnless(_have_toolchain(), "需要已构建的 engine 插件与 clang")
class TestAgentScenario(unittest.TestCase):
    def test_full_agent_flow(self):
        """Agent 可完成 scan→plan→protect→verify→attack_sim→report→evolve。"""
        with tempfile.TemporaryDirectory() as out:
            manifest = _call("anti_rea.scan", {"path": SAMPLES})
            self.assertTrue(manifest["assets"])

            policy = _call("anti_rea.plan", {"manifest": manifest,
                                             "budget": {"max_overhead": 0.5}, "seed": 7})

            result = _call("anti_rea.protect", {"policy": policy, "root": SAMPLES,
                                                "sources": [P0_SECRET], "out": out,
                                                "seed": 7})
            self.assertTrue(os.path.isdir(os.path.join(out, "artifacts")))
            self.assertTrue(result["metadata"]["strategies"])

            vr = _call("anti_rea.verify", {"artifacts": out})
            self.assertTrue(vr["functional_pass"], vr)

            er = _call("anti_rea.attack_sim", {"artifacts": out, "benchmark": BENCH})
            self.assertIn("verdict", er)

            rep = _call("anti_rea.report", {"run": out, "format": "md"})
            self.assertTrue(os.path.exists(rep["path"]))

            ev = _call("anti_rea.evolve", {"manifest": manifest, "seed": 3,
                                           "pop": 16, "gens": 4})
            self.assertTrue(ev["non_degrade"])
            self.assertTrue(ev["best_policy"]["assets"])


if __name__ == "__main__":
    unittest.main()
