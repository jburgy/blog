//! ```cargo
//! [dependencies]
//! libc = "0.2"
//! ```
use std::collections::{HashMap, HashSet};
use std::convert::TryInto;
use std::fs::OpenOptions;
use std::io::{self, Read, Write};
use std::os::fd::{FromRawFd, IntoRawFd};
use std::os::unix::fs::OpenOptionsExt;
use std::process;

const BUFFER_START: usize = 0x4000;
const BUFFER_SIZE: usize = 0x1000;
const WORD_BUFFER: usize = 0x5014;
const STATE_ADDR: usize = 0x1400;
const HERE_ADDR: usize = 0x1401;
const LATEST_ADDR: usize = 0x1402;
const S0_ADDR: usize = 0x1403;
const BASE_ADDR: usize = 0x1404;
const LIT_CFA: i32 = 5251;

const SYS_EXIT: i32 = 1;
const SYS_READ: i32 = 3;
const SYS_WRITE: i32 = 4;
const SYS_OPEN: i32 = 5;
const SYS_CLOSE: i32 = 6;
const SYS_BRK: i32 = 45;
const SYS_CREAT: i32 = 8;

#[derive(Default)]
struct NumResult {
    result: i32,
    remaining: i32,
}

struct Forth {
    memory: Vec<u8>,
    currkey: usize,
    buftop: usize,
}

impl Forth {
    fn new() -> io::Result<Self> {
        let mut memory = vec![0u8; 0x10000 * 4];
        
        // Initialize the rodata section
        Self::init_rodata(&mut memory);
        
        Ok(Self {
            memory,
            currkey: BUFFER_START,
            buftop: BUFFER_START,
        })
    }

    fn init_rodata(memory: &mut [u8]) {
        let names = concat!(
            "DROP SWAP DUP OVER ROT -ROT 2DROP 2DUP 2SWAP ?DUP 1+ 1- 4+ 4- ",
            "+ - * /MOD = <> < > <= >= 0= 0<> 0< 0> 0<= 0>= AND OR XOR INVERT ",
            "EXIT LIT ! @ +! -! C! C@ C@C! CMOVE STATE HERE LATEST S0 BASE VERSION R0 DOCOL ",
            "F_IMMED F_HIDDEN F_LENMASK SYS_EXIT SYS_OPEN SYS_CLOSE SYS_READ SYS_WRITE SYS_CREAT SYS_BRK ",
            "O_RDONLY O_WRONLY O_RDWR O_CREAT O_EXCL O_TRUNC O_APPEND O_NONBLOCK ", 
            ">R R> RSP@ RSP! RDROP DSP@ DSP! KEY EMIT WORD NUMBER FIND >CFA >DFA CREATE , [ ] ",
            "IMMEDIATE HIDDEN HIDE : ; ' BRANCH 0BRANCH LITSTRING TELL INTERPRET QUIT CHAR EXECUTE ",
            "SYSCALL3 SYSCALL2 SYSCALL1"
        );
        let immediate = HashSet::from(["[", "IMMEDIATE", ";"]);
        let composite = HashMap::from([
            (">DFA", ">CFA 4+ EXIT"),
            (":", "WORD CREATE LIT 0 , LATEST @ HIDDEN ] EXIT"),
            (";", "LIT EXIT , LATEST @ HIDDEN [ EXIT"),
            ("HIDE", "WORD FIND HIDDEN EXIT"),
            ("QUIT", "R0 RSP! INTERPRET BRANCH -8"),
        ]);

        let mut here: usize = 5133 << 2;
        let mut latest: usize = 0;
        let mut code: u32 = 1;
        for name in names.split_whitespace() {
            memory[here..here + 4].copy_from_slice(&(latest as u32).to_ne_bytes());
            latest = here;
            memory[here + 4] = (name.len() as u8) | (if immediate.contains(name) { 0x80u8 } else { 0u8 });
            memory[here + 5..here + 5 + name.len()].copy_from_slice(&name.as_bytes());
            here += 4 + ((name.len() + 4) & !3); // Align to 4 bytes

            if let Some(body) = composite.get(name) {
                memory[here..here + 4].copy_from_slice(&0i32.to_ne_bytes());
                here += 4;
                for word in body.split_whitespace() {
                    if let Ok(num) = word.parse::<i32>() {
                        memory[here..here + 4].copy_from_slice(&num.to_ne_bytes());
                        here += 4;
                    } else {
                        let mut node = latest as usize;
                        while node != 0 && (memory[node + 4] & 0x3F != word.len() as u8 || &memory[node + 5..node + 5 + word.len()] != word.as_bytes()) {
                            node = i32::from_ne_bytes(memory[node..node + 4].try_into().unwrap()) as usize;
                        }
                        node += 4 + ((word.len() + 4) & !3); // >CFA
                        memory[here..here + 4].copy_from_slice(&(node as u32).to_ne_bytes());
                        here += 4;
                    }
                }
            } else {
                memory[here..here + 4].copy_from_slice(&code.to_ne_bytes());
                here += 4;
                code += 1;
            }
        }
        memory[STATE_ADDR * 4..(STATE_ADDR + 1) * 4].copy_from_slice(&0i32.to_ne_bytes());
        memory[HERE_ADDR * 4..(HERE_ADDR + 1) * 4].copy_from_slice(&(here as u32).to_ne_bytes());
        memory[LATEST_ADDR * 4..(LATEST_ADDR + 1) * 4].copy_from_slice(&(latest as u32).to_ne_bytes());
        memory[S0_ADDR * 4..(S0_ADDR + 1) * 4].copy_from_slice(&0x2000i32.to_ne_bytes());
        memory[BASE_ADDR * 4..(BASE_ADDR + 1) * 4].copy_from_slice(&10i32.to_ne_bytes());
    }

    #[inline]
    fn read_i32(&self, addr: usize) -> i32 {
        let slice: &[u8] = &self.memory[addr * 4..(addr + 1) * 4];
        let bytes: [u8; 4] = slice.try_into().expect("length mismatch");
        i32::from_ne_bytes(bytes)
    }

    #[inline]
    fn write_i32(&mut self, addr: usize, value: i32) {
        let slice: &mut [u8] = &mut self.memory[addr * 4..(addr + 1) * 4];
        let bytes: [u8; 4] = value.to_ne_bytes();
        slice.copy_from_slice(&bytes);
    }

    fn key(&mut self) -> io::Result<u8> {
        while self.buftop <= self.currkey {
            self.currkey = BUFFER_START;
            let n = io::stdin().read(&mut self.memory[BUFFER_START..BUFFER_START + BUFFER_SIZE])?;
            self.buftop = BUFFER_START + n;
        }
        let ch = self.memory[self.currkey];
        self.currkey += 1;
        Ok(ch)
    }

    fn word(&mut self) -> io::Result<i32> {
        let mut ch = self.key()?;
        
        // Skip whitespace and handle comments
        loop {
            if ch == b'\\' {
                // Comment - skip to end of line
                loop {
                    ch = self.key()?;
                    if ch == b'\n' {
                        break;
                    }
                }
            }
            if ch > b' ' {
                break;
            }
            ch = self.key()?;
        }

        // Read word
        let mut pos = WORD_BUFFER;
        loop {
            self.memory[pos] = ch;
            pos += 1;
            ch = self.key()?;
            if ch <= b' ' {
                break;
            }
        }

        Ok((pos - WORD_BUFFER) as i32)
    }

    fn find(&self, count: i32, name: usize) -> i32 {
        let mut word = self.read_i32(LATEST_ADDR);

        while word != 0 {
            let len = self.memory[word as usize + 4] & 0x3F;
            if len == count as u8 {
                let word_name = &self.memory[word as usize + 5..word as usize + 5 + count as usize];
                let search_name = &self.memory[name..name + count as usize];
                if word_name == search_name {
                    return word;
                }
            }
            word = self.read_i32((word >> 2) as usize);
        }

        0
    }

    fn number(&self, n: i32, s: usize) -> NumResult {
        let base = self.read_i32(BASE_ADDR);
        let mut pos = s;
        let mut remaining = n;
        let mut sign = 1;
        
        // Handle sign
        match self.memory[pos] {
            b'-' => {
                sign = -1;
                remaining -= 1;
                pos += 1;
            }
            b'+' => {
                remaining -= 1;
                pos += 1;
            }
            _ => {}
        }

        let mut result = 0i32;
        while remaining > 0 {
            result = result.wrapping_mul(base);
            let ch = self.memory[pos];
            pos += 1;
            
            let mut digit = (ch as i32) - ('0' as i32);
            if digit < 0 {
                break;
            }
            if digit > 9 {
                digit -= 7; // 'A' - '0' - 10
                if digit < 10 {
                    break;
                }
            }
            if digit >= base {
                break;
            }
            result = result.wrapping_add(digit);
            remaining -= 1;
        }

        NumResult {
            result: result.wrapping_mul(sign),
            remaining,
        }
    }

    fn code_field_address(&self, mut word: i32) -> i32 {
        word += 4;
        word += ((self.memory[word as usize] & 0x1F) as i32) + 4;
        word &= !3;
        word
    }

    fn run(&mut self) -> io::Result<()> {
        // Stacks are part of self.memory
        // data_stack: 0x0000-0x07FF (first 8192 bytes, 2048 i32s)
        // return_stack: 0x0800-0x0FFF (next 8192 bytes, 2048 i32s)
        let mut sp = 0x0800usize;
        let mut rsp = 0x1000usize;
        let mut cfa = 5530usize;
        let mut ip = 0usize;

        loop {
            match self.read_i32(cfa) {
                0 => { // DOCOL
                    rsp -= 1;
                    self.write_i32(rsp, ip as i32);
                    ip = cfa + 1;
                }
                1 => { // DROP
                    sp += 1;
                }
                2 => { // SWAP
                    let (a, b) = self.memory[sp * 4..(sp + 2) * 4].split_at_mut(4);
                    a.swap_with_slice(b);
                }
                3 => { // DUP
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(sp + 1));
                }
                4 => { // OVER
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(sp + 2));
                }
                5 => { // ROT
                    let (a, b, c) = (self.read_i32(sp), self.read_i32(sp + 1), self.read_i32(sp + 2));
                    self.write_i32(sp + 2, b);
                    self.write_i32(sp + 1, a);
                    self.write_i32(sp, c);
                }
                6 => { // -ROT
                    let (a, b, c) = (self.read_i32(sp), self.read_i32(sp + 1), self.read_i32(sp + 2));
                    self.write_i32(sp + 2, a);
                    self.write_i32(sp + 1, c);
                    self.write_i32(sp, b);
                }
                7 => { // 2DROP
                    sp += 2;
                }
                8 => { // 2DUP
                    sp -= 2;
                    self.write_i32(sp, self.read_i32(sp + 2));
                    self.write_i32(sp + 1, self.read_i32(sp + 3));
                }
                9 => { // 2SWAP
                    let (a, b, c, d) = (self.read_i32(sp), self.read_i32(sp + 1), 
                                       self.read_i32(sp + 2), self.read_i32(sp + 3));
                    self.write_i32(sp + 3, b);
                    self.write_i32(sp + 2, a);
                    self.write_i32(sp + 1, d);
                    self.write_i32(sp, c);
                }
                10 => { // ?DUP
                    let a = self.read_i32(sp);
                    if a != 0 {
                        sp -= 1;
                        self.write_i32(sp, a);
                    }
                }
                11 => { // 1+
                    self.write_i32(sp, self.read_i32(sp).wrapping_add(1));
                }
                12 => { // 1-
                    self.write_i32(sp, self.read_i32(sp).wrapping_sub(1));
                }
                13 => { // 4+
                    self.write_i32(sp, self.read_i32(sp).wrapping_add(4));
                }
                14 => { // 4-
                    self.write_i32(sp, self.read_i32(sp).wrapping_sub(4));
                }
                15 => { // +
                    let val = self.read_i32(sp + 1).wrapping_add(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                16 => { // -
                    let val = self.read_i32(sp + 1).wrapping_sub(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                17 => { // *
                    let val = self.read_i32(sp + 1).wrapping_mul(self.read_i32(sp));
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                18 => { // /MOD
                    let (a, b) = (self.read_i32(sp + 1), self.read_i32(sp));
                    self.write_i32(sp + 1, a % b);
                    self.write_i32(sp, a / b);
                }
                19 => { // =
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) == self.read_i32(sp)) as i32);
                    sp += 1;
                }
                20 => { // <>
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) != self.read_i32(sp)) as i32);
                    sp += 1;
                }
                21 => { // <
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) < self.read_i32(sp)) as i32);
                    sp += 1;
                }
                22 => { // >
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) > self.read_i32(sp)) as i32);
                    sp += 1;
                }
                23 => { // <=
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) <= self.read_i32(sp)) as i32);
                    sp += 1;
                }
                24 => { // >=
                    self.write_i32(sp + 1, (self.read_i32(sp + 1) >= self.read_i32(sp)) as i32);
                    sp += 1;
                }
                25 => { // 0=
                    self.write_i32(sp, (self.read_i32(sp) == 0) as i32);
                }
                26 => { // 0<>
                    self.write_i32(sp, (self.read_i32(sp) != 0) as i32);
                }
                27 => { // 0<
                    self.write_i32(sp, (self.read_i32(sp) < 0) as i32);
                }
                28 => { // 0>
                    self.write_i32(sp, (self.read_i32(sp) > 0) as i32);
                }
                29 => { // 0<=
                    self.write_i32(sp, (self.read_i32(sp) <= 0) as i32);
                }
                30 => { // 0>=
                    self.write_i32(sp, (self.read_i32(sp) >= 0) as i32);
                }
                31 => { // AND
                    let val = self.read_i32(sp + 1) & self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                32 => { // OR
                    let val = self.read_i32(sp + 1) | self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                33 => { // XOR
                    let val = self.read_i32(sp + 1) ^ self.read_i32(sp);
                    self.write_i32(sp + 1, val);
                    sp += 1;
                }
                34 => { // INVERT
                    self.write_i32(sp, !self.read_i32(sp));
                }
                35 => { // EXIT
                    ip = self.read_i32(rsp) as usize;
                    rsp += 1;
                }
                36 => { // LIT
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(ip));
                    ip += 1;
                }
                37 => { // !
                    self.write_i32((self.read_i32(sp) >> 2) as usize, self.read_i32(sp + 1));
                    sp += 2;
                }
                38 => { // @
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    self.write_i32(sp, self.read_i32(addr));
                }
                39 => { // +!
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    let val = self.read_i32(addr).wrapping_add(self.read_i32(sp + 1));
                    self.write_i32(addr, val);
                    sp += 2;
                }
                40 => { // -!
                    let addr = (self.read_i32(sp) >> 2) as usize;
                    let val = self.read_i32(addr).wrapping_sub(self.read_i32(sp + 1));
                    self.write_i32(addr, val);
                    sp += 2;
                }
                41 => { // C!
                    let addr = self.read_i32(sp) as usize;
                    let val = self.read_i32(sp + 1) as u8;
                    self.memory[addr] = val;
                    sp += 2;
                }
                42 => { // C@
                    let addr = self.read_i32(sp) as usize;
                    self.write_i32(sp, self.memory[addr] as i32);
                }
                43 => { // C@C!
                    let src = self.read_i32(sp) as usize;
                    let dst = self.read_i32(sp + 1) as usize;
                    self.memory[dst] = self.memory[src];
                    sp += 1;
                }
                44 => { // CMOVE
                    let src = self.read_i32(sp + 2) as usize;
                    let dst = self.read_i32(sp + 1) as usize;
                    let len = self.read_i32(sp) as usize;
                    self.memory.copy_within(src..src + len, dst);
                    sp += 2;
                }
                45 => { // STATE
                    sp -= 1;
                    self.write_i32(sp, (STATE_ADDR << 2) as i32);
                }
                46 => { // HERE
                    sp -= 1;
                    self.write_i32(sp, (HERE_ADDR << 2) as i32);
                }
                47 => { // LATEST
                    sp -= 1;
                    self.write_i32(sp, (LATEST_ADDR << 2) as i32);
                }
                48 => { // S0
                    sp -= 1;
                    self.write_i32(sp, (S0_ADDR << 2) as i32);
                }
                49 => { // BASE
                    sp -= 1;
                    self.write_i32(sp, (BASE_ADDR << 2) as i32);
                }
                50 => { // VERSION
                    sp -= 1;
                    self.write_i32(sp, 47);
                }
                51 => { // R0
                    sp -= 1;
                    self.write_i32(sp, (0x1000 << 2) as i32);
                }
                52 => { // DOCOL
                    sp -= 1;
                    self.write_i32(sp, 0);
                }
                53 => { // F_IMMED
                    sp -= 1;
                    self.write_i32(sp, 0x80);
                }
                54 => { // F_HIDDEN
                    sp -= 1;
                    self.write_i32(sp, 0x20);
                }
                55 => { // F_LENMASK
                    sp -= 1;
                    self.write_i32(sp, 0x1F);
                }
                56 => { // SYS_EXIT
                    sp -= 1;
                    self.write_i32(sp, SYS_EXIT);
                }
                57 => { // SYS_OPEN
                    sp -= 1;
                    self.write_i32(sp, SYS_OPEN);
                }
                58 => { // SYS_CLOSE
                    sp -= 1;
                    self.write_i32(sp, SYS_CLOSE);
                }
                59 => { // SYS_READ
                    sp -= 1;
                    self.write_i32(sp, SYS_READ);
                }
                60 => { // SYS_WRITE
                    sp -= 1;
                    self.write_i32(sp, SYS_WRITE);
                }
                61 => { // SYS_CREAT
                    sp -= 1;
                    self.write_i32(sp, SYS_CREAT);
                }
                62 => { // SYS_BRK
                    sp -= 1;
                    self.write_i32(sp, SYS_BRK);
                }
                63 => { // O_RDONLY
                    sp -= 1;
                    self.write_i32(sp, libc::O_RDONLY);
                }
                64 => { // O_WRONLY
                    sp -= 1;
                    self.write_i32(sp, libc::O_WRONLY);
                }
                65 => { // O_RDWR
                    sp -= 1;
                    self.write_i32(sp, libc::O_RDWR);
                }
                66 => { // O_CREAT
                    sp -= 1;
                    self.write_i32(sp, libc::O_CREAT);
                }
                67 => { // O_EXCL
                    sp -= 1;
                    self.write_i32(sp, libc::O_EXCL);
                }
                68 => { // O_TRUNC
                    sp -= 1;
                    self.write_i32(sp, libc::O_TRUNC);
                }
                69 => { // O_APPEND
                    sp -= 1;
                    self.write_i32(sp, libc::O_APPEND);
                }
                70 => { // O_NONBLOCK
                    sp -= 1;
                    self.write_i32(sp, libc::O_NONBLOCK);
                }
                71 => { // >R
                    rsp -= 1;
                    self.write_i32(rsp, self.read_i32(sp) >> 2);
                    sp += 1;
                }
                72 => { // R>
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(rsp) << 2);
                    rsp += 1;
                }
                73 => { // RSP@
                    sp -= 1;
                    self.write_i32(sp, (rsp << 2) as i32);
                }
                74 => { // RSP!
                    rsp = (self.read_i32(sp) >> 2) as usize;
                    sp += 1;
                }
                75 => { // RDROP
                    rsp += 1;
                }
                76 => { // DSP@
                    let a = sp;
                    sp -= 1;
                    self.write_i32(sp, (a << 2) as i32);
                }
                77 => { // DSP!
                    sp = (self.read_i32(sp) >> 2) as usize;
                }
                78 => { // KEY
                    sp -= 1;
                    let ch = self.key()? as i32;
                    self.write_i32(sp, ch);
                }
                79 => { // EMIT
                    let ch = self.read_i32(sp) as u8;
                    io::stdout().write_all(&[ch])?;
                    io::stdout().flush()?;
                    sp += 1;
                }
                80 => { // WORD
                    sp -= 1;
                    self.write_i32(sp, WORD_BUFFER as i32);
                    sp -= 1;
                    let word_len = self.word()?;
                    self.write_i32(sp, word_len);
                }
                81 => { // NUMBER
                    let num = self.number(self.read_i32(sp), self.read_i32(sp + 1) as usize);
                    self.write_i32(sp + 1, num.result);
                    self.write_i32(sp, num.remaining);
                }
                82 => { // FIND
                    let result = self.find(self.read_i32(sp), self.read_i32(sp + 1) as usize);
                    self.write_i32(sp + 1, result);
                    sp += 1;
                }
                83 => { // >CFA
                    let addr = self.code_field_address(self.read_i32(sp));
                    self.write_i32(sp, addr);
                }
                84 => { // CREATE
                    let count = self.read_i32(sp) as usize;
                    let name = self.read_i32(sp + 1) as usize;
                    let here = self.read_i32(HERE_ADDR) as usize;
                    
                    self.write_i32(here >> 2, self.read_i32(LATEST_ADDR));
                    self.memory[here + 4] = count as u8;
                    self.memory.copy_within(name..name + count, here + 5);
                    
                    let new_here = self.code_field_address(here as i32);
                    self.write_i32(HERE_ADDR, new_here);
                    self.write_i32(LATEST_ADDR, here as i32);
                    sp += 2;
                }
                85 => { // ,
                    let here = self.read_i32(HERE_ADDR) as usize;
                    self.write_i32(here >> 2, self.read_i32(sp));
                    self.write_i32(HERE_ADDR, (here + 4) as i32);
                    sp += 1;
                }
                86 => { // [
                    self.write_i32(STATE_ADDR, 0);
                }
                87 => { // ]
                    self.write_i32(STATE_ADDR, 1);
                }
                88 => { // IMMEDIATE
                    let latest = (self.read_i32(LATEST_ADDR) >> 2) as usize;
                    self.write_i32(latest + 1, self.read_i32(latest + 1) ^ 0x80);
                }
                89 => { // HIDDEN
                    let word = (self.read_i32(sp) >> 2) as usize;
                    self.write_i32(word + 1, self.read_i32(word + 1) ^ 0x20);
                    sp += 1;
                }
                90 => { // '
                    sp -= 1;
                    self.write_i32(sp, self.read_i32(ip));
                    ip += 1;
                }
                91 => { // BRANCH
                    ip = (ip as i32 + (self.read_i32(ip) >> 2)) as usize;
                }
                92 => { // 0BRANCH
                    if self.read_i32(sp) != 0 {
                        ip += 1;
                    } else {
                        ip = (ip as i32 + (self.read_i32(ip) >> 2)) as usize;
                    }
                    sp += 1;
                }
                93 => { // LITSTRING
                    sp -= 1;
                    self.write_i32(sp, ((ip + 1) << 2) as i32);
                    sp -= 1;
                    let len = self.read_i32(ip);
                    self.write_i32(sp, len);
                    ip += 1 + ((len + 3) >> 2) as usize;
                }
                94 => { // TELL
                    let len = self.read_i32(sp) as usize;
                    let addr = self.read_i32(sp + 1) as usize;
                    io::stdout().write_all(&self.memory[addr..addr + len])?;
                    io::stdout().flush()?;
                    sp += 2;
                }
                95 => { // INTERPRET
                    let a = self.word()? as usize;
                    let b = self.find(a as i32, WORD_BUFFER);
                    
                    if b != 0 {
                        cfa = self.code_field_address(b) as usize;
                        if (self.memory[b as usize + 4] & 0x80) != 0 || self.read_i32(STATE_ADDR) == 0 {
                            cfa >>= 2;
                            continue;
                        }
                        let here = self.read_i32(HERE_ADDR);
                        self.write_i32(here as usize >> 2, cfa as i32);
                        self.write_i32(HERE_ADDR, here + 4);
                    } else {
                        let num = self.number(a as i32, WORD_BUFFER);
                        if num.remaining != 0 {
                            io::stderr().write_all(b"PARSE ERROR: ")?;
                            io::stderr().write_all(&self.memory[WORD_BUFFER..WORD_BUFFER + a])?;
                            io::stderr().write_all(b"\n")?;
                        } else if self.read_i32(STATE_ADDR) != 0 {
                            let here = self.read_i32(HERE_ADDR);
                            self.write_i32(here as usize >> 2, LIT_CFA << 2); // LIT
                            self.write_i32(HERE_ADDR, here + 4);
                            let here = self.read_i32(HERE_ADDR);
                            self.write_i32(here as usize >> 2, num.result);
                            self.write_i32(HERE_ADDR, here + 4);
                        } else {
                            sp -= 1;
                            self.write_i32(sp, num.result);
                        }
                    }
                }
                96 => { // CHAR
                    self.word()?;
                    sp -= 1;
                    self.write_i32(sp, self.memory[WORD_BUFFER] as i32);
                }
                97 => { // EXECUTE
                    cfa = (self.read_i32(sp) >> 2) as usize;
                    sp += 1;
                    continue;
                }
                98 => { // SYSCALL3
                    let (n, a, b, c) = (
                        self.read_i32(sp),
                        self.read_i32(sp + 1),
                        self.read_i32(sp + 2),
                        self.read_i32(sp + 3),
                    );
                    let result = match n {
                        SYS_READ => {
                            unsafe {
                                let mut file = std::fs::File::from_raw_fd(a);
                                let buf = &mut self.memory[b as usize..b as usize + c as usize];
                                let n = file.read(buf)?;
                                std::mem::forget(file);
                                Ok(n as i32)
                            }
                        }
                        SYS_WRITE => {
                            unsafe {
                                let mut file = std::fs::File::from_raw_fd(a);
                                let buf = &self.memory[b as usize..b as usize + c as usize];
                                let n = file.write(buf)?;
                                std::mem::forget(file);
                                Ok(n as i32)
                            }
                        }
                        SYS_CREAT => {
                            let path = std::str::from_utf8(&self.memory[a as usize..a as usize + b as usize]).expect("UTF-8");
                            let file = OpenOptions::new()
                                .write(true)
                                .create(true)
                                .truncate(true)
                                .mode(c as u32)
                                .open(path)?;
                            Ok(file.into_raw_fd())
                        }
                        _ => Err(io::Error::new(io::ErrorKind::Unsupported, "Unknown syscall")),
                    };
                    self.write_i32(sp + 3, result.unwrap_or(-1));
                    sp += 3;
                }
                99 => { // SYSCALL2
                    let (n, a, b, flags) = (self.read_i32(sp), self.read_i32(sp + 1), self.read_i32(sp + 2), self.read_i32(sp + 3));
                    let result = match n {
                        SYS_OPEN => {
                            let path = std::str::from_utf8(&self.memory[a as usize..a as usize + b as usize]).expect("UTF-8");
                            let file = std::fs::OpenOptions::new()
                                .read(flags & 0 != 0 || flags & 2 != 0)
                                .write(flags & 1 != 0 || flags & 2 != 0)
                                .create(flags & 64 != 0)
                                .create_new(flags & 128 != 0)
                                .truncate(flags & 512 != 0)
                                .append(flags & 1024 != 0)
                                .open(path)?;
                            Ok(file.into_raw_fd())
                        }
                        _ => Err(io::Error::new(io::ErrorKind::Unsupported, "Unknown syscall")),
                    };
                    self.write_i32(sp + 2, result.unwrap_or(-1));
                    sp += 2;
                }
                100 => { // SYSCALL1
                    let (n, a) = (self.read_i32(sp), self.read_i32(sp + 1));
                    match n {
                        SYS_EXIT => std::process::exit(a),
                        SYS_CLOSE => {
                            unsafe { drop(std::fs::File::from_raw_fd(a)) };
                            self.write_i32(sp + 1, 0);
                            sp += 1;
                        }
                        SYS_BRK => {
                            if a == 0 {
                                self.write_i32(sp + 1, self.memory.as_ptr() as i32 + self.memory.len() as i32);
                            } else {
                                let new_size = (a as usize).saturating_sub(self.memory.as_ptr() as usize);
                                if new_size > self.memory.capacity() {
                                    self.memory.reserve(new_size - self.memory.len());
                                    if new_size > self.memory.capacity() {
                                        self.write_i32(sp + 1, -1);
                                    } else {
                                        self.memory.resize(new_size, 0);
                                        self.write_i32(sp + 1, a);
                                    }
                                } else {
                                    self.memory.resize(new_size, 0);
                                    self.write_i32(sp + 1, a);
                                }
                            }
                            sp += 1;
                        }
                        _ => {
                            self.write_i32(sp + 1, -1);
                            sp += 1;
                        }
                    }
                }
                opcode => {
                    return Err(io::Error::new(io::ErrorKind::InvalidData, 
                        format!("Unknown opcode: {}", opcode)));
                }
            }
            cfa = (self.read_i32(ip) >> 2) as usize;
            ip += 1;
        }
    }
}

fn main() {
    let mut forth = Forth::new().unwrap_or_else(|e| {
        eprintln!("Failed to initialize: {}", e);
        process::exit(1);
    });

    if let Err(e) = forth.run() {
        eprintln!("Runtime error: {}", e);
        process::exit(1);
    }
}
