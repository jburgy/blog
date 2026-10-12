//! C-ABI exports for the browser demo (`web/worker.mjs`); small enough to skip wasm-bindgen.

use std::cell::RefCell;

use crate::eliza::Eliza;

thread_local! {
    static ELIZA: RefCell<Eliza> = RefCell::new(Eliza::new());
    static REPLY: RefCell<String> = const { RefCell::new(String::new()) };
}

/// A buffer the host fills with UTF-8 input, then hands to `say`.
#[unsafe(no_mangle)]
pub extern "C" fn alloc(len: usize) -> *mut u8 {
    Box::into_raw(vec![0u8; len].into_boxed_slice()).cast()
}

/// Consumes a buffer from `alloc` and returns the reply (`reply_len` bytes),
/// valid until the next call.
///
/// # Safety
/// `ptr` and `len` must come from a single `alloc` call that wasn't passed here before.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn say(ptr: *mut u8, len: usize) -> *const u8 {
    let input = unsafe { Vec::from_raw_parts(ptr, len, len) };
    let reply = ELIZA.with_borrow_mut(|eliza| eliza.reply(&String::from_utf8_lossy(&input)));
    REPLY.with_borrow_mut(|slot| {
        *slot = reply;
        slot.as_ptr()
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn reply_len() -> usize {
    REPLY.with_borrow(String::len)
}
