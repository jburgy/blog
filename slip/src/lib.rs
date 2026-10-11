//! A from-scratch sketch of Weizenbaum's SLIP (Symmetric LIst Processor),
//! the list-processing library ELIZA was written in. See README.md for the
//! full write-up of what maps onto `std`/crates and what doesn't.

use intrusive_collections::linked_list::Cursor;
use intrusive_collections::{LinkedList, LinkedListLink, intrusive_adapter};

/// A cell's payload: either a leaf value or a nested sublist (SLIP's
/// "sublist indicator" cell, e.g. the `*` in `(A, B, *, C)`).
pub enum Payload {
    Atom(i64),
    // ponytail: embedded (single-owner) sublist, not shared. Real SLIP let
    // several parent cells point at the *same* header via its refcount. To
    // share one, wrap it in `Rc<RefCell<List>>` and hand out `Ref::leak`'d
    // cursors (or an arena) when that's actually needed.
    Sublist(List),
}

pub struct Cell {
    link: LinkedListLink,
    pub data: Payload,
}

intrusive_adapter!(pub CellAdapter = Box<Cell>: Cell { link: LinkedListLink });

/// A SLIP list: fixed-size cells linked in place, no separate container
/// allocation -- the Rust analogue of a FORTRAN array of records with
/// embedded NEXT/PREV fields instead of a `Vec`/`Rc`-of-cons-cells.
pub type List = LinkedList<CellAdapter>;

pub fn cell(data: Payload) -> Box<Cell> {
    Box::new(Cell {
        link: LinkedListLink::new(),
        data,
    })
}

/// Builds a flat list of atoms, e.g. for a sentence or a literal fragment.
pub fn list_of(atoms: impl IntoIterator<Item = i64>) -> List {
    let mut list = List::new(CellAdapter::new());
    for atom in atoms {
        list.push_back(cell(Payload::Atom(atom)));
    }
    list
}

/// One cursor per nesting level: the "state history stack" the Wikipedia
/// SLIP article describes -- a memento per level, recording the list being
/// read, the position within it, and (via `depth`) the level itself.
/// Entering a sublist pushes a frame; exhausting one pops back to resume
/// the parent exactly where it left off. Several `Reader`s can scan the
/// same list independently since each only holds `&'a` borrows.
pub struct Reader<'a> {
    stack: Vec<Cursor<'a, CellAdapter>>,
}

impl<'a> Reader<'a> {
    pub fn new(list: &'a List) -> Self {
        Reader {
            stack: vec![list.front()],
        }
    }

    /// Current nesting depth -- "the level ... of the history stack".
    /// A fresh `Reader` reports `1` (one frame, not yet probed) even on an
    /// empty list; it only drops to `0` once the first `next()` call pops it.
    pub fn depth(&self) -> usize {
        self.stack.len()
    }
}

impl<'a> Iterator for Reader<'a> {
    type Item = &'a Payload;

    fn next(&mut self) -> Option<&'a Payload> {
        loop {
            let cur = self.stack.last_mut()?;
            if cur.is_null() {
                self.stack.pop();
                if self.stack.is_empty() {
                    return None;
                }
                continue;
            }
            let data = &cur.get().unwrap().data;
            cur.move_next();
            match data {
                Payload::Atom(_) => return Some(data),
                Payload::Sublist(sub) => self.stack.push(sub.front()),
            }
        }
    }
}
