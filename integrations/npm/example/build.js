// 最简"构建"步骤：编译 app.c 为对象文件（供 postbuild 保护样例运行）。
"use strict";

const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const outDir = path.join(__dirname, "build");
fs.mkdirSync(outDir, { recursive: true });
const cc = process.env.CC || "cc";
const r = spawnSync(cc, ["-c", "src/app.c", "-o", path.join(outDir, "app.o")],
                    { stdio: "inherit" });
process.exit(r.status === null ? 1 : r.status);
