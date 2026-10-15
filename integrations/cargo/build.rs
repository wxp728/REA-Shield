// Anti-REA Cargo 构建集成（FR-D3）
// 放入 crate 的 build.rs；在编译后调用集成驱动施加保护（不内嵌引擎）。
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=src/main.rs");

    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = manifest_dir.join("anti-rea");
    let driver = std::env::var("ANTI_REA_DRIVER").unwrap_or_else(|_| {
        // 默认：仓库根 integrations/anti-rea（相对于本 crate）
        manifest_dir
            .join("../../../integrations/anti-rea")
            .to_string_lossy()
            .into_owned()
    });

    let status = Command::new(&driver)
        .args([
            "pipeline",
            "--root",
            manifest_dir.to_str().unwrap(),
            "--out",
            out.to_str().unwrap(),
            "--source",
            manifest_dir.join("src/main.rs").to_str().unwrap(),
            "--abort-on-failure",
        ])
        .status()
        .expect("无法启动 Anti-REA 集成驱动");

    if !status.success() {
        panic!("Anti-REA 保护/验证失败，构建中止（FR-D7）");
    }
}
