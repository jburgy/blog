//! ELIZA on top of SLIP lists. Sentences are lists of interned word codes
//! (SLIP stored small integers, not strings); a reply is assembled as a SLIP
//! list in which every captured fragment is a nested `Sublist`, and `Reader`
//! flattens it back into one sentence. The script is a trimmed-down DOCTOR:
//! keyword + rank, decomposition patterns (`0` = any run of words),
//! reassembly templates (a number = the n-th matched component), cycling
//! through templates per pattern, and a NONE fallback.

use std::cmp::Reverse;
use std::collections::HashMap;

use crate::{CellAdapter, List, Payload, Reader, cell, list_of};

// (keywords, rank, [(decomposition, [reassembly])]). Candidate rules are tried
// by descending rank; a rule none of whose decompositions match falls through
// to the next one. In a reassembly, `$` is the keyword that selected the rule.
type Script = &'static [(
    &'static str,
    u8,
    &'static [(&'static str, &'static [&'static str])],
)];

const SCRIPT: Script = &[
    (
        "SORRY",
        80,
        &[(
            "0",
            &[
                "PLEASE DON'T APOLOGIZE",
                "APOLOGIES ARE NOT NECESSARY",
                "WHAT FEELINGS DO YOU HAVE WHEN YOU APOLOGIZE",
            ],
        )],
    ),
    (
        "REMEMBER",
        5,
        &[
            (
                "0 I REMEMBER 0",
                &[
                    "DO YOU OFTEN THINK OF 4",
                    "WHAT ELSE DO YOU RECALL",
                    "WHAT IN THE PRESENT SITUATION REMINDS YOU OF 4",
                ],
            ),
            ("0", &["WHAT ABOUT 1 DO YOU REMEMBER", "PLEASE GO ON"]),
        ],
    ),
    (
        "IF",
        3,
        &[
            (
                "0 IF 0",
                &[
                    "DO YOU THINK IT'S LIKELY THAT 3",
                    "DO YOU WISH THAT 3",
                    "WHAT DO YOU THINK ABOUT 3",
                ],
            ),
            ("0", &["PLEASE GO ON"]),
        ],
    ),
    (
        "DREAM DREAMS",
        70,
        &[(
            "0",
            &[
                "WHAT DOES THAT DREAM SUGGEST TO YOU",
                "DO YOU DREAM OFTEN",
                "WHAT PERSONS APPEAR IN YOUR DREAMS",
            ],
        )],
    ),
    (
        "HELLO HI",
        0,
        &[("0", &["HOW DO YOU DO PLEASE STATE YOUR PROBLEM"])],
    ),
    (
        "COMPUTER MACHINE",
        50,
        &[(
            "0",
            &[
                "DO COMPUTERS WORRY YOU",
                "WHY DO YOU MENTION COMPUTERS",
                "DON'T YOU THINK MACHINES PLAY A ROLE IN YOUR PROBLEM",
            ],
        )],
    ),
    (
        "MOTHER FATHER SISTER BROTHER PARENTS FAMILY WIFE HUSBAND CHILDREN",
        60,
        &[(
            "0",
            &[
                "TELL ME MORE ABOUT YOUR FAMILY",
                "WHO ELSE IN YOUR FAMILY COMES TO MIND",
                "WHAT ELSE COMES TO MIND WHEN YOU THINK OF YOUR FAMILY",
            ],
        )],
    ),
    (
        "MY",
        2,
        &[
            (
                "0 MY 0",
                &[
                    "WHY DO YOU SAY YOUR 3",
                    "DOES THAT SUGGEST ANYTHING ELSE WHICH BELONGS TO YOU",
                    "IS IT IMPORTANT TO YOU THAT YOUR 3",
                ],
            ),
            ("0", &["PLEASE GO ON"]),
        ],
    ),
    (
        "CAN",
        0,
        &[
            (
                "0 CAN YOU 0",
                &[
                    "YOU BELIEVE I CAN 4 DON'T YOU",
                    "YOU WANT ME TO BE ABLE TO 4",
                    "PERHAPS YOU WOULD LIKE TO BE ABLE TO 4 YOURSELF",
                ],
            ),
            (
                "0 CAN I 0",
                &[
                    "WHETHER OR NOT YOU CAN 4 DEPENDS ON YOU MORE THAN ON ME",
                    "DO YOU WANT TO BE ABLE TO 4",
                ],
            ),
            ("0", &["PLEASE GO ON"]),
        ],
    ),
    (
        "YOU",
        0,
        &[
            (
                "0 YOU 0 ME",
                &[
                    "WHAT MAKES YOU THINK I 3 YOU",
                    "DO YOU THINK I 3 YOU",
                    "WHY DO YOU THINK I 3 YOU",
                ],
            ),
            (
                "0",
                &[
                    "WE WERE DISCUSSING YOU NOT ME",
                    "OH I 1",
                    "YOU'RE NOT REALLY TALKING ABOUT ME ARE YOU",
                ],
            ),
        ],
    ),
    (
        "I",
        100,
        &[
            (
                "0 I AM 0",
                &[
                    "IS IT BECAUSE YOU ARE 4 THAT YOU CAME TO ME",
                    "HOW LONG HAVE YOU BEEN 4",
                    "DO YOU BELIEVE IT IS NORMAL TO BE 4",
                    "DO YOU ENJOY BEING 4",
                    "PLEASE TELL ME WHY YOU THINK YOU ARE 4",
                ],
            ),
            ("0 I HAVE 0", &["HOW LONG HAVE YOU HAD 4"]),
            (
                "0 I FEEL 0",
                &[
                    "TELL ME MORE ABOUT SUCH FEELINGS",
                    "DO YOU OFTEN FEEL 4",
                    "DO YOU ENJOY FEELING 4",
                    "SOMETIMES I FEEL THE SAME WAY",
                ],
            ),
        ],
    ),
    (
        "I",
        21,
        &[
            (
                "0 I NEED 0",
                &[
                    "WHAT WOULD IT MEAN TO YOU IF YOU GOT 4",
                    "WHY DO YOU NEED 4",
                    "SUPPOSE YOU GOT 4 SOON",
                ],
            ),
            (
                "0 I WANT 0",
                &[
                    "WHAT WOULD IT MEAN IF YOU GOT 4",
                    "WHY DO YOU WANT 4",
                    "SUPPOSE YOU GOT 4 SOON",
                ],
            ),
            (
                "0 I CAN'T 0",
                &[
                    "HOW DO YOU KNOW YOU CAN'T 4",
                    "HAVE YOU TRIED",
                    "PERHAPS YOU COULD 4 NOW",
                ],
            ),
        ],
    ),
    (
        "I",
        0,
        &[(
            "0",
            &[
                "YOU SAY 1",
                "CAN YOU ELABORATE ON THAT",
                "DO YOU SAY 1 FOR SOME SPECIAL REASON",
            ],
        )],
    ),
    ("BYE", 30, &[("0", &["GOODBYE AND TAKE CARE"])]),
    (
        "HOPE THINK WANT PREFER NEED WISH",
        20,
        &[("0", &["DO YOU REALLY $"])],
    ),
    (
        "GO HAVE BE TRY EAT TAKE HELP MAKE GET JUMP WRITE TYPE FILL PUT TURN COMPUTE CRY KILL DRINK CRASH ADD",
        15,
        &[(
            "0",
            &["WHY HAVE YOU DECIDED THAT TO $ IS IMPORTANT FOR YOU"],
        )],
    ),
    (
        "WHY WHERE WHEN WHAT WHICH HOW",
        10,
        &[("0", &["I KEEP MY OPINION ON $ FOR MYSELF"])],
    ),
    (
        "BECAUSE",
        90,
        &[(
            "0",
            &[
                "IS THAT THE REAL REASON",
                "DON'T ANY OTHER REASONS COME TO MIND",
                "DOES THAT REASON EXPLAIN ANYTHING ELSE",
            ],
        )],
    ),
    (
        "YES",
        40,
        &[(
            "0",
            &[
                "YOU SEEM QUITE POSITIVE",
                "YOU ARE SURE",
                "I SEE",
                "I UNDERSTAND",
            ],
        )],
    ),
    (
        "NO",
        35,
        &[(
            "0",
            &[
                "ARE YOU SAYING NO JUST TO BE NEGATIVE",
                "YOU ARE BEING A BIT NEGATIVE",
                "WHY NOT",
            ],
        )],
    ),
    (
        "ALWAYS",
        1,
        &[(
            "0",
            &[
                "CAN YOU THINK OF A SPECIFIC EXAMPLE",
                "WHEN",
                "WHAT ARE YOU THINKING OF",
                "REALLY ALWAYS",
            ],
        )],
    ),
    (
        "NONE",
        0,
        &[(
            "0",
            &[
                "I'M NOT SURE I UNDERSTAND YOU FULLY",
                "PLEASE GO ON",
                "WHAT DOES THAT SUGGEST TO YOU",
                "DO YOU FEEL STRONGLY ABOUT DISCUSSING SUCH THINGS",
            ],
        )],
    ),
];

// Applied to captured fragments only, all at once, so I->YOU is never undone.
const REFLECTIONS: &[(&str, &str)] = &[
    ("I", "YOU"),
    ("ME", "YOU"),
    ("MY", "YOUR"),
    ("AM", "ARE"),
    ("MINE", "YOURS"),
    ("MYSELF", "YOURSELF"),
    ("YOU", "I"),
    ("YOUR", "MY"),
    ("YOURS", "MINE"),
    ("YOURSELF", "MYSELF"),
    ("ARE", "AM"),
];

enum Part {
    Word(i64),
    Key,
    Slot(usize),
}

struct Decomp {
    runs: Vec<Vec<i64>>,
    templates: Vec<Vec<Part>>,
    next: usize,
}

struct Rule {
    rank: u8,
    decomps: Vec<Decomp>,
}

#[derive(Default)]
struct Vocab {
    codes: HashMap<String, i64>,
    words: Vec<String>,
}

impl Vocab {
    fn code(&mut self, word: &str) -> i64 {
        *self.codes.entry(word.to_owned()).or_insert_with(|| {
            self.words.push(word.to_owned());
            self.words.len() as i64 - 1
        })
    }
}

// Reader never yields sublists (it descends into them), so every item is an atom.
fn atom(p: &Payload) -> i64 {
    match p {
        Payload::Atom(c) => *c,
        Payload::Sublist(_) => unreachable!("Reader flattens sublists"),
    }
}

// `runs` are the literal word runs between `0` wildcards, so n runs means n-1
// wildcards. Each run is found leftmost, no backtracking needed; the last one
// must also end the sentence. Returns the components, one per word or wildcard.
// ponytail: only `0` (any run of words) wildcards; fixed-length ones need backtracking.
fn decompose(runs: &[Vec<i64>], mut words: Reader) -> Option<Vec<Vec<i64>>> {
    let (first, rest) = runs.split_first()?;
    let mut parts = Vec::new();
    for &w in first {
        (words.next().map(atom)? == w).then_some(())?;
        parts.push(vec![w]);
    }
    if rest.is_empty() {
        return words.next().is_none().then_some(parts);
    }
    for (k, run) in rest.iter().enumerate() {
        let last = k == rest.len() - 1;
        let mut gap = Vec::new();
        words = loop {
            let mut tail = words.clone();
            let found = run.iter().all(|&w| tail.next().map(atom) == Some(w));
            if found && (!last || tail.next().is_none()) {
                break tail;
            }
            gap.push(atom(words.next()?));
        };
        parts.push(gap);
        parts.extend(run.iter().map(|&w| vec![w]));
    }
    Some(parts)
}

pub struct Eliza {
    vocab: Vocab,
    rules: Vec<Rule>,
    keywords: HashMap<i64, Vec<usize>>,
    none: usize,
    reflect: HashMap<i64, i64>,
}

impl Default for Eliza {
    fn default() -> Self {
        Self::new()
    }
}

impl Eliza {
    pub fn new() -> Self {
        let mut vocab = Vocab::default();
        let mut rules = Vec::new();
        let mut keywords: HashMap<i64, Vec<usize>> = HashMap::new();
        let mut none = 0;
        for (keys, rank, decomps) in SCRIPT {
            let decomps = decomps
                .iter()
                .map(|(pattern, templates)| Decomp {
                    runs: pattern
                        .split_whitespace()
                        .fold(vec![vec![]], |mut runs, w| {
                            match w {
                                "0" => runs.push(Vec::new()),
                                _ => runs.last_mut().unwrap().push(vocab.code(w)),
                            }
                            runs
                        }),
                    templates: templates
                        .iter()
                        .map(|t| {
                            t.split_whitespace()
                                .map(|w| match w.parse() {
                                    Ok(n) => Part::Slot(n),
                                    Err(_) if w == "$" => Part::Key,
                                    Err(_) => Part::Word(vocab.code(w)),
                                })
                                .collect()
                        })
                        .collect(),
                    next: 0,
                })
                .collect();
            if *keys == "NONE" {
                none = rules.len();
            } else {
                for key in keys.split_whitespace() {
                    keywords
                        .entry(vocab.code(key))
                        .or_default()
                        .push(rules.len());
                }
            }
            rules.push(Rule {
                rank: *rank,
                decomps,
            });
        }
        let reflect = REFLECTIONS
            .iter()
            .map(|(a, b)| (vocab.code(a), vocab.code(b)))
            .collect();
        Eliza {
            vocab,
            rules,
            keywords,
            none,
            reflect,
        }
    }

    pub fn reply(&mut self, line: &str) -> String {
        let upper = line.to_uppercase();
        // Like Weizenbaum's ELIZA, only the first clause some rule applies to is used.
        for clause in upper.split([',', '.', ';', '?', '!']) {
            let sentence = list_of(
                clause
                    .replace("I'M", "I AM")
                    .split_whitespace()
                    .map(|w| self.vocab.code(w)),
            );
            let mut candidates: Vec<(usize, i64)> = Reader::new(&sentence)
                .flat_map(|p| {
                    let key = atom(p);
                    self.keywords
                        .get(&key)
                        .into_iter()
                        .flatten()
                        .map(move |&r| (r, key))
                })
                .collect();
            // The sort is stable, so the earliest keyword wins a rank tie.
            candidates.sort_by_key(|&(r, _)| Reverse(self.rules[r].rank));
            if let Some(reply) = candidates
                .into_iter()
                .find_map(|(r, key)| self.apply(r, key, &sentence))
            {
                return reply;
            }
        }
        self.apply(self.none, 0, &List::new(CellAdapter::new()))
            .expect("NONE has a catch-all")
    }

    fn apply(&mut self, rule: usize, key: i64, input: &List) -> Option<String> {
        let (decomp, captured) = self.rules[rule]
            .decomps
            .iter_mut()
            .find_map(|d| decompose(&d.runs, Reader::new(input)).map(|c| (d, c)))?;
        let template = &decomp.templates[decomp.next % decomp.templates.len()];
        decomp.next += 1;

        let mut sentence = List::new(CellAdapter::new());
        for part in template {
            let payload = match part {
                Part::Word(c) => Payload::Atom(*c),
                Part::Key => Payload::Atom(key),
                Part::Slot(n) => Payload::Sublist(list_of(
                    captured[n - 1]
                        .iter()
                        .map(|c| *self.reflect.get(c).unwrap_or(c)),
                )),
            };
            sentence.push_back(cell(payload));
        }
        let words: Vec<&str> = Reader::new(&sentence)
            .map(|p| match p {
                Payload::Atom(c) => self.vocab.words[*c as usize].as_str(),
                Payload::Sublist(_) => unreachable!("Reader flattens sublists"),
            })
            .collect();
        Some(words.join(" "))
    }
}
