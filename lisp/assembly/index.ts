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

type T = i16;
const align = alignof<T>() as T;

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

const tNewLine    = 10 as u8;
const tSpace      = 32 as u8;
const tLeftParen  = 40 as u8;
const tRightParen = 41 as u8;
const tStar       = 42 as u8;

const M = 0x8000;

let cx: T; /* stores negative memory use */
let dx: u8; /* stores lookahead character */

declare function getchar(): i32;

declare function putchar(i: i32): void;

function Intern(): T {
  let i: T, j: T, k: T, x: u8;
  for (i = 0; x = load<u8>(i++, M);) {
    for (j = 0; x == load<u8>(j); ++j) {
      if (!x) return i - j - 1;
      x = load<u8>(i++, M);
    }
    while (x)
      x = load<u8>(i++, M);
  }
  j = 0;
  k = --i;
  while (x = load<u8>(j++)) store<u8>(i++, x, M);
  return k;
}

function GetChar(): u8 {
  let t = dx;

  dx = getchar() as u8;
  return t;
}

function PrintChar(c: i32): void {
  putchar(c);
}

function GetToken(): u8 {
  let c: u8, i: T = 0;
  do if ((c = GetChar()) > tSpace) store<u8>(i++, c);
  while (c <= tSpace || (c > tRightParen && dx > tRightParen));
  store<u8>(i, 0);
  return c;
}

function AddList(x: T): T {
  return Cons(x, GetList());
}

function GetList(): T {
  const c = GetToken();
  if (c == tRightParen) return 0;
  return AddList(GetObject(c));
}

function GetObject(c: u8): T {
  if (c == tLeftParen) return GetList();
  return Intern();
}

function Read(): T {
  return GetObject(GetToken());
}

function PrintAtom(x: T): void {
  let c: u8;
  while (c = load<u8>(x++, M)) {
    PrintChar(c);
  }
}

function PrintList(x: T): void {
  PrintChar(tLeftParen);
  PrintObject(Car(x));
  while (x = Cdr(x)) {
    if (x < 0) {
      PrintChar(tSpace);
      PrintObject(Car(x));
    } else {
      PrintChar(0x2219);
      PrintObject(x);
      break;
    }
  }
  PrintChar(tRightParen);
}

function PrintObject(x: T): void {
  if (x < 0) {
    PrintList(x);
  } else {
    PrintAtom(x);
  }
}

function Print(e: T): void {
  PrintObject(e);
}

function PrintNewLine(): void {
  PrintChar(tNewLine);
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § Bootstrap John McCarthy's Metacircular Evaluator    ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

function Car(x: T): T {
  return load<T>(M + (x << align));
}

function Cdr(x: T): T {
  return load<T>(M + (x + 1 << align));
}

function Cons(car: T, cdr: T): T {
  store<T>(M + (--cx << align), cdr);
  store<T>(M + (--cx << align), car);
  return cx;
}

function Gc(x: T, m: T, k: T): T {
  return x < m ? Cons(Gc(Car(x), m, k), 
                      Gc(Cdr(x), m, k)) + k : x;
}

function Evlis(m: T, a: T): T {
  if (m) {
    const x: T = Eval(Car(m), a);
    return Cons(x, Evlis(Cdr(m), a));
  } else {
    return 0;
  }
}

function Pairlis(x: T, y: T, a: T): T {
  return x ? Cons(Cons(Car(x), Car(y)),
                  Pairlis(Cdr(x), Cdr(y), a)) : a;
}

function Assoc(x: T, y: T): T {
  if (!y) return 0;
  if (x == Car(Car(y))) return Cdr(Car(y));
  return Assoc(x, Cdr(y));
}

function Evcon(c: T, a: T): T {
  if (Eval(Car(Car(c)), a)) {
    return Eval(Car(Cdr(Car(c))), a);
  } else {
    return Evcon(Cdr(c), a);
  }
}

function Apply(f: T, x: T, a: T): T {
  if (f < 0)       return Eval(Car(Cdr(Cdr(f))), Pairlis(Car(Cdr(f)), x, a));
  if (f > kEq)     return Apply(Eval(f, a), x, a);
  if (f == kEq)    return Car(x) == Car(Cdr(x)) ? kT as T : 0;
  if (f == kCons)  return Cons(Car(x), Car(Cdr(x)));
  if (f == kAtom)  return Car(x) < 0 ? 0 : kT as T;
  if (f == kCar)   return Car(Car(x));
  if (f == kCdr)   return Cdr(Car(x));
  if (f == kRead)  return Read();
  if (f == kPrint) return (x ? Print(Car(x)) : PrintNewLine()), 0;
  return 0;
}

function Eval(e: T, a: T): T {
  let A: T, B: T, C: T;
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
    store<T>(M + (--A << align), load<T>(M + (--B << align)));
  cx = A;
  return e;
}

/*───────────────────────────────────────────────────────────────────────────│─╗
│ The LISP Challenge § User Interface                                      ─╬─│┼
╚────────────────────────────────────────────────────────────────────────────│*/

export function main(): void {
  for (;;) {
    cx = 0;
    PrintChar(tStar);
    PrintChar(tSpace);
    Print(Eval(Read(), 0));
    PrintNewLine();
  }
}