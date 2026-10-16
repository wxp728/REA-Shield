#!/usr/bin/env node
/*
 * REA-Shield npm 构建集成（FR-D4）
 * 在 postbuild 阶段调用集成驱动（不内嵌引擎）。
 * 用法：node anti-rea-protect.js [--source src/app.c ...]
 */
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const root = process.env.ANTI_REA_ROOT || process.cwd();
const out = process.env.ANTI_REA_OUT || path.join(process.cwd(), "anti-rea");
const driver = process.env.ANTI_REA_DRIVER
  || path.join(__dirname, "..", "anti-rea");

const args = ["pipeline", "--root", root, "--out", out, ...process.argv.slice(2)];
const r = spawnSync(driver, args, { stdio: "inherit" });
process.exit(r.status === null ? 1 : r.status);
