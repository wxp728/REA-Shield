# 试点工程 2：protocol-svc（C++ / Make / P1）

含**协议帧解析**与**秘密帧解码**的 C++ 服务片段（受保护资产 P1）。

## 构建

```sh
make -C pilots/protocol-svc
pilots/protocol-svc/decode
```

## 保护闭环

见 `pilots/crypto-lib/README.md` 同款流程（`--root pilots/protocol-svc
--source pilots/protocol-svc/src/decode.cpp`）。
