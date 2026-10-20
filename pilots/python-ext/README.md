# 试点工程 3：python-ext（Python C 扩展 / build_ext / P2）

含 `secret_key_schedule` 的 Python C 扩展，经 `anti_rea_build_ext` 集成在
`build_ext` 阶段完成保护。

## 保护 + 构建

```sh
cd pilots/python-ext
# 用你自己的 Python 3.11（在 PATH 中，或用 PYTHON= 指定）
PYTHON="${PYTHON:-python3.11}"
ANTI_REA_PYTHON="$PYTHON" \
ANTI_REA_DRIVER=../../integrations/anti-rea \
"$PYTHON" setup.py build_ext --inplace
"$PYTHON" -c "import pilotext; print(pilotext.transform(7))"
```
