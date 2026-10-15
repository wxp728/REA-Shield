// Anti-REA Cargo 构建集成（FR-D3）
//
// 放入 crate 根目录作为 `build.rs`；在构建时调用集成驱动施加保护（不内嵌引擎）。
// v1.0 范围：保护 crate 内的 C/FFI 源（`ANTI_REA_SOURCES`/`csrc/`）；Rust IR 级保护
// 见 `integrations/README.md` 的"已知限制"（后续增强）。
use std::path::PathBuf;
use std::process::Command;

fn main() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    println!("cargo:rerun-if-changed=csrc/secret.c");

    let out = manifest_dir.join("anti-rea");
    let driver = std::env::var("ANTI_REA_DRIVER").unwrap_or_else(|_| {
        manifest_dir
            .join("../../../integrations/anti-rea")
            .to_string_lossy()
            .into_owned()
    });
    let source = std::env::var("ANTI_REA_SOURCES")
        .unwrap_or_else(|_| manifest_dir.join("csrc/secret.c").to_string_lossy().into_owned());

    let status = Command::new(&driver)
        .args([
            "pipeline",
            "--root",
            manifest_dir.to_str().unwrap(),
            "--out",
            out.to_str().unwrap(),
            "--source",
            &source,
            "--abort-on-failure",
        ])
        .status()
        .expect("无法启动 Anti-REA 集成驱动");

    if !status.success() {
        panic!("Anti-REA 保护/验证失败，构建中止（FR-D7）");
    }
}
