//! Confirm that Zig's comptime can implement Rob Pike's "smallest regular
//! expression package that would illustrate the basic ideas while still
//! recognizing a useful and non-trivial set of patterns".
//!
//! See https://www.cs.princeton.edu/courses/archive/spr09/cos333/beautiful.html.

const std = @import("std");
const expect = std.testing.expect;

// match: search for regexp anywhere in text
fn match(comptime regexp: [:0]const u8, text: [:0]const u8) bool {
    if (regexp[0] == '^')
        return matchhere(regexp[1..], text);
    for (0..text.len) |i| { // must look even if string is empty
        if (matchhere(regexp, text[i..]))
            return true;
    }
    return false;
}

// matchhere: search for regexp at beginning of text
fn matchhere(comptime regexp: [:0]const u8, text: [:0]const u8) bool {
    if (regexp[0] == 0)
        return true;
    if (regexp[1] == '*')
        return matchstar(regexp[0], regexp[2..], text);
    if (regexp[0] == '$' and regexp[1] == 0)
        return text[0] == 0;
    if (text.len > 0 and (regexp[0] == '.' or regexp[0] == text[0]))
        return matchhere(regexp[1..], text[1..]);
    return false;
}

// matchstar: search for c*regexp at beginning of text
fn matchstar(c: u8, comptime regexp: [:0]const u8, text: [:0]const u8) bool {
    for (text, 0..) |ch, i| { // a * matches zero or more instances
        if (matchhere(regexp, text[i..]))
            return true;
        if (ch != c and c != '.')
            break;
    }
    return false;
}

test match {
    try expect(match("a", "abc"));
    try expect(match("b", "abc"));
    try expect(match("c", "abc"));
    try expect(match("^a", "abc"));
    try expect(!match("^b", "abc"));
    try expect(!match("^c", "abc"));
    try expect(!match("a$", "abc"));
    try expect(!match("b$", "abc"));
    try expect(match("c$", "abc"));
    try expect(match("a.c", "abc"));
    try expect(match("a.*c", "abc"));
    try expect(match("a.*bc", "abc"));
}
