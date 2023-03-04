/*-*- mode:c;indent-tabs-mode:nil;c-basic-offset:2;tab-width:8;coding:utf-8 -*-│
│vi: set net ft=c ts=2 sts=2 sw=2 fenc=utf-8                                :vi│
╞══════════════════════════════════════════════════════════════════════════════╡
│ Copyright 2020 Justine Alexandra Roberts Tunney                              │
│                                                                              │
│ Permission to use, copy, modify, and/or distribute this software for         │
│ any purpose with or without fee is hereby granted, provided that the         │
│ above copyright notice and this permission notice appear in all copies.      │
│                                                                              │
│ THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL                │
│ WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED                │
│ WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE             │
│ AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL         │
│ DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR        │
│ PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER               │
│ TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR             │
│ PERFORMANCE OF THIS SOFTWARE.                                                │
╚─────────────────────────────────────────────────────────────────────────────*/

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § LISP Machine                                        ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

const kT          = 4;
const kQuote      = 6;
const kCond       = 12;
const kRead       = 17;
const kPrint      = 22;
const kAtom       = 28;
const kCar        = 33;
const kCdr        = 37;
const kCons       = 41;
const kEq         = 46;

const M = 4096;
const S = "NIL\0T\0QUOTE\0COND\0READ\0PRINT\0ATOM\0CAR\0CDR\0CONS\0EQ";

let cx: i32; /* stores negative memory use */
let dx: i32; /* stores lookahead character */

declare function getchar(): i32;

declare function putchar(i: i32): void;

function Intern(): i32 {
  let i: i32, j: i32, x: i32, y: i32;
  for (i = 0; (x = load<i32>(M + 4 * i++));) {
    for (j = 0;; ++j) {
      if (x != load<u8>(j) as i32) break;
      if (!x) return i - j - 1;
      x = load<i32>(M + 4 * i++);
    }
    while (x)
      x = load<i32>(M + 4 * i++);
  }
  j = 0;
  x = --i;
  let c: u8;
  while (c = load<u8>(j++)) store<i32>(M + 4 * i++, c);
  return x;
}

function GetChar(): i32 {
  let t: i32;

  t = dx;
  dx = getchar();
  return t;
}

function PrintChar(c: i32): void {
  putchar(c);
}

function GetToken(): i32 {
  let c: i32, i: i32 = 0;
  do if ((c = GetChar()) > ' '.codePointAt(0)) store<u8>(i++, c as u8);
  while (c <= ' '.codePointAt(0) || (c > ')'.codePointAt(0) && dx > ')'.codePointAt(0)));
  store<u8>(i, 0 as u8);
  return c;
}

function AddList(x: i32): i32 {
  return Cons(x, GetList());
}

function GetList(): i32 {
  const c: i32 = GetToken();
  if (c == ')'.codePointAt(0)) return 0;
  return AddList(GetObject(c));
}

function GetObject(c: i32): i32 {
  if (c == '('.codePointAt(0)) return GetList();
  return Intern();
}

function Read(): i32 {
  return GetObject(GetToken());
}

function PrintAtom(x: i32): void {
  let c: i32;
  for (;;) {
    if (!(c = load<i32>(M + 4 * x++))) break;
    PrintChar(c);
  }
}

function PrintList(x: i32): void {
  PrintChar('('.codePointAt(0));
  PrintObject(Car(x));
  while ((x = Cdr(x))) {
    if (x < 0) {
      PrintChar(' '.codePointAt(0));
      PrintObject(Car(x));
    } else {
      PrintChar('∙'.codePointAt(0));
      PrintObject(x);
      break;
    }
  }
  PrintChar(')'.codePointAt(0));
}

function PrintObject(x: i32): void {
  if (x < 0) {
    PrintList(x);
  } else {
    PrintAtom(x);
  }
}

function Print(e: i32): void {
  PrintObject(e);
}

function PrintNewLine(): void {
  PrintChar('\n'.codePointAt(0));
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § Bootstrap John McCarthy's Metacircular Evaluator    ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

function Car(x: i32): i32 {
  return load<i32>(4 * x);
}

function Cdr(x: i32): i32 {
  return load<i32>(4 * x + 4);
}

function Cons(car: i32, cdr: i32): i32 {
  store<i32>(4 * --cx, cdr);
  store<i32>(4 * --cx, car);
  return cx;
}

function Gc(x: i32, m: i32, k: i32): i32 {
  return x < m ? Cons(Gc(Car(x), m, k), 
                      Gc(Cdr(x), m, k)) + k : x;
}

function Evlis(m: i32, a: i32): i32 {
  if (m) {
    const x: i32 = Eval(Car(m), a);
    return Cons(x, Evlis(Cdr(m), a));
  } else {
    return 0;
  }
}

function Pairlis(x: i32, y: i32, a: i32): i32 {
  return x ? Cons(Cons(Car(x), Car(y)),
                  Pairlis(Cdr(x), Cdr(y), a)) : a;
}

function Assoc(x: i32, y: i32): i32 {
  if (!y) return 0;
  if (x == Car(Car(y))) return Cdr(Car(y));
  return Assoc(x, Cdr(y));
}

function Evcon(c: i32, a: i32): i32 {
  if (Eval(Car(Car(c)), a)) {
    return Eval(Car(Cdr(Car(c))), a);
  } else {
    return Evcon(Cdr(c), a);
  }
}

function Apply(f: i32, x: i32, a: i32): i32 {
  if (f < 0)       return Eval(Car(Cdr(Cdr(f))), Pairlis(Car(Cdr(f)), x, a));
  if (f > kEq)     return Apply(Eval(f, a), x, a);
  if (f == kEq)    return Car(x) == Car(Cdr(x)) ? kT : 0;
  if (f == kCons)  return Cons(Car(x), Car(Cdr(x)));
  if (f == kAtom)  return Car(x) < 0 ? 0 : kT;
  if (f == kCar)   return Car(Car(x));
  if (f == kCdr)   return Cdr(Car(x));
  if (f == kRead)  return Read();
  if (f == kPrint) return (x ? Print(Car(x)) : PrintNewLine()), 0;
  return 0;
}

function Eval(e: i32, a: i32): i32 {
  let A: i32, B: i32, C: i32;
  if (e >= 0)
    return Assoc(e, a);
  if (Car(e) == kQuote)
    return Car(Cdr(e));
  A = cx;
  if (Car(e) == kCond) {
    e = Evcon(Cdr(e), a);
  } else {
    e = Apply(Car(e), Evlis(Cdr(e), a), a);
  }
  B = cx;
  e = Gc(e, A, A - B);
  C = cx;
  while (C < B)
    store<i32>(4 * --A, load<i32>(4 * --B));
  cx = A;
  return e;
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § User Interface                                      ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

export function main(): void {
  let i: i32;
  for(i = 0; i < S.length; ++i) store<u8>(i, S.codePointAt(i) as u8);
  for (;;) {
    cx = 0;
    Print(Eval(Read(), 0));
    PrintNewLine();
  }
}