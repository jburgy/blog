// Covers slip's Reader: the "state history stack" Wikipedia's SLIP article
// describes. Two independent readers scan the same list; one descends into
// a nested sublist mid-scan while the other is untouched, then pops back
// out to resume the parent exactly where it left off.
use slip::{Payload, Reader, cell, list_of};

#[test]
fn independent_readers_track_separate_history_stacks() {
    let inner = list_of([97, 98]);

    let mut list = list_of([1]);
    list.push_back(cell(Payload::Sublist(inner)));
    list.push_back(cell(Payload::Atom(2)));

    let mut r1 = Reader::new(&list);
    let mut r2 = Reader::new(&list);

    assert!(matches!(r1.next(), Some(Payload::Atom(1))));
    assert_eq!(r1.depth(), 1); // still at the top level

    // r2 walks all the way into the sublist while r1 hasn't moved.
    assert!(matches!(r2.next(), Some(Payload::Atom(1))));
    assert!(matches!(r2.next(), Some(Payload::Atom(97)))); // descended automatically
    assert_eq!(r2.depth(), 2); // one frame for the parent list, one for the sublist

    // r1 is unaffected by r2's descent -- independent cursors over the same list.
    assert!(matches!(r1.next(), Some(Payload::Atom(97))));

    assert!(matches!(r2.next(), Some(Payload::Atom(98))));
    assert_eq!(r2.depth(), 2); // sublist exhausted but the frame isn't popped until probed
    assert!(matches!(r2.next(), Some(Payload::Atom(2))));
    assert_eq!(r2.depth(), 1); // popped back out: the memento resumed the parent
    assert!(r2.next().is_none());
}
