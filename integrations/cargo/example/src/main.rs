fn secret_mix(x: i32) -> i32 {
    (x ^ (x << 3)).wrapping_add(5)
}

fn main() {
    println!("{}", secret_mix(9));
}
