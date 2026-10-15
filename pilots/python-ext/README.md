# 试点工程 3：python-ext（Python C 扩展 / build_ext / P2）

含 `secret_key_schedule` 的 Python C 扩展，经 `anti_rea_build_ext` 集成在
`build_ext` 阶段完成保护。

## 保护 + 构建

```sh
cd pilots/python-ext
ANTI_REA_PYTHON=/opt/anti-rea-toolchain/python3.11/bin/python3.11 \
ANTI_REA_DRIVER=../../integrations/anti-rea \
/opt/anti-rea-toolchain/python3.11/bin/python3.11 setup.py build_ext --inplace
/opt/anti-rea-toolchain/python3.11/bin/python3.11 -c "import pilotext; print(pilotext.transform(7))"
```
