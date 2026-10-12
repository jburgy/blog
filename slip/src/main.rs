use std::io::{self, BufRead, Write};

use slip::eliza::Eliza;

fn main() {
    let mut eliza = Eliza::new();
    println!("HOW DO YOU DO. PLEASE TELL ME YOUR PROBLEM");
    for line in io::stdin().lock().lines().map_while(Result::ok) {
        if matches!(
            line.trim().to_uppercase().as_str(),
            "BYE" | "GOODBYE" | "QUIT"
        ) {
            break;
        }
        println!("{}", eliza.reply(&line));
        io::stdout().flush().ok();
    }
    println!("GOODBYE. THANK YOU FOR TALKING TO ME");
}
