fn main() {
    let odds = [1, 3, 5, 7, 9, 11, 13, 15];
    for &n in &odds {
        println!("{}^2 = {}", n, n * n);
    }
}