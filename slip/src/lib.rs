//! A from-scratch sketch of Weizenbaum's SLIP (Symmetric LIst Processor),
//! the list-processing library ELIZA was written in. See README.md for the
//! full write-up of what maps onto `std`/crates and what doesn't.

pub mod eliza;
#[cfg(target_arch = "wasm32")]
mod web;

use intrusive_collections::linked_list::Cursor;
use intrusive_collections::{LinkedList, LinkedListLink, intrusive_adapter};

pub enum Payload {
    Atom(i64),
    // ponytail: embedded single-owner sublist; real SLIP shared a header
    // across several parent cells via its refcount instead. Upgrade path if
    // sharing is ever needed: Rc<RefCell<List>>, with Ref::leak'd cursors
    // (or an arena) to work around the borrowed-Cursor lifetime.
    Sublist(List),
}

pub struct Cell {
    link: LinkedListLink,
    pub data: Payload,
}

intrusive_adapter!(pub CellAdapter = Box<Cell>: Cell { link: LinkedListLink });

/// Embeds each cell's link fields in place instead of Vec/Rc-of-cons: the
/// closest safe-Rust match to FORTRAN's array of records with built-in
/// NEXT/PREV fields.
pub type List = LinkedList<CellAdapter>;

pub fn cell(data: Payload) -> Box<Cell> {
    Box::new(Cell {
        link: LinkedListLink::new(),
        data,
    })
}

pub fn list_of(atoms: impl IntoIterator<Item = i64>) -> List {
    let mut list = List::new(CellAdapter::new());
    for atom in atoms {
        list.push_back(cell(Payload::Atom(atom)));
    }
    list
}

/// Wikipedia's SLIP article describes the reader as "a state history stack
/// -- a good example of a memento pattern" -- hence one cursor per nesting
/// level rather than a single flat position. Each Reader only holds `&'a`
/// borrows, so several can scan the same list independently.
#[derive(Clone)]
pub struct Reader<'a> {
    stack: Vec<Cursor<'a, CellAdapter>>,
}

impl<'a> Reader<'a> {
    pub fn new(list: &'a List) -> Self {
        Reader {
            stack: vec![list.front()],
        }
    }

    /// A fresh Reader reports 1 even on an empty list (the unprobed null
    /// cursor from `new`); it drops to 0 only once `next()` pops it.
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
