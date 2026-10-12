// Exercises slip's Sublist + Reader on the classic Weizenbaum DOCTOR rule
// "I NEED X" -> "WHAT WOULD IT MEAN TO YOU IF YOU GOT X": the captured
// fragment X is spliced into the reassembly template as a nested sublist,
// and Reader::next auto-descends into it while flattening the reply --
// exactly the trick ELIZA's own SLIP-based reassembly rules relied on. See
// ../../lisp/eliza.lisp for a from-scratch Lisp ELIZA with a different rule
// set (reflection, keyword punting); this test only covers the one
// decompose/reassemble step slip's Reader is built to make convenient.
use slip::{Payload, Reader, cell, list_of};

// SLIP itself stored words as small integer codes in fixed-size cells
// rather than strings; this table plays that role for the test.
const WORDS: &[&str] = &[
    "I", "NEED", "A", "VACATION", "WHAT", "WOULD", "IT", "MEAN", "TO", "YOU", "IF", "GOT",
];

fn code(word: &str) -> i64 {
    WORDS.iter().position(|&w| w == word).expect("unknown word") as i64
}

fn decode(code: i64) -> &'static str {
    WORDS[code as usize]
}

#[test]
fn eliza_reassembly_flattens_a_captured_sublist() {
    let sentence = ["I", "NEED", "A", "VACATION"];
    // Decomposition: "I NEED *" matches, capturing the words after NEED.
    let captured = list_of(sentence[2..].iter().copied().map(code));

    // Reassembly template: the fixed prefix, then the captured fragment
    // spliced in as a sublist, exactly like a SLIP reassembly rule would.
    let mut reply = list_of(
        [
            "WHAT", "WOULD", "IT", "MEAN", "TO", "YOU", "IF", "YOU", "GOT",
        ]
        .into_iter()
        .map(code),
    );
    reply.push_back(cell(Payload::Sublist(captured)));

    let mut reader = Reader::new(&reply);
    let words: Vec<&str> = (&mut reader)
        .map(|p| match p {
            Payload::Atom(c) => decode(*c),
            Payload::Sublist(_) => unreachable!(),
        })
        .collect();

    assert_eq!(
        words.join(" "),
        "WHAT WOULD IT MEAN TO YOU IF YOU GOT A VACATION"
    );
    assert_eq!(reader.depth(), 0); // fully drained, popped back out of every level
}

#[test]
fn full_eliza_session() {
    let mut eliza = slip::eliza::Eliza::new();
    assert_eq!(
        eliza.reply("I need a vacation."),
        "WHAT WOULD IT MEAN TO YOU IF YOU GOT A VACATION"
    );
    // Second hit on the same pattern cycles to the next template.
    assert_eq!(
        eliza.reply("I need a vacation"),
        "WHY DO YOU NEED A VACATION"
    );
    // Captures are reflected (MY -> YOUR, ME -> YOU), highest rank wins.
    assert_eq!(
        eliza.reply("I'm sad, my mother hates me"),
        "IS IT BECAUSE YOU ARE SAD THAT YOU CAME TO ME"
    );
    assert_eq!(
        eliza.reply("My boss hates me"),
        "WHY DO YOU SAY YOUR BOSS HATES YOU"
    );
    assert_eq!(
        eliza.reply("What a day"),
        "I'M NOT SURE I UNDERSTAND YOU FULLY"
    );
}
