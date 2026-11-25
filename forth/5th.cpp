// C++20 port of 5th.c: same threaded-code design, but the dictionary is built at compile time.
// Each word is a type; `entry<I>` is a constant-initialized variable whose link and body
// references are resolved by name in consteval code (a mistyped word name fails to compile).
// build: clang++ -std=c++20 -Os -fwrapv -mstackrealign -o 5th 5th.cpp
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <functional>
#include <string_view>
#include <sys/syscall.h>
#include <tuple>
#include <unistd.h>
#include <utility>

static_assert(sizeof(void *) == 8, "word names such as 8+ assume 64-bit cells");

struct Interp;
union Instr;
using Code = intptr_t *(*)(Interp &, intptr_t *, Instr **, Instr *, Instr *);
union Instr { Code code; intptr_t lit; Instr *word; };

enum Flags : uint8_t { F_IMMED = 0x80, F_HIDDEN = 0x20, F_LENMASK = 0x1f };
constexpr size_t WORD_MAX = 0x20;

struct Hdr { Hdr *link; uint8_t flag; char name[15]; };
template <size_t N> struct W : Hdr { Instr code; Instr data[N]; }; // zero-length array for N == 0 is a GNU extension, as in 5th.c
static_assert(sizeof(Hdr) == 24);

struct Interp {
    intptr_t state; Hdr *latest; intptr_t *argc, *s0; intptr_t base; Instr **r0;
    char buffer[WORD_MAX]; char *here; Instr *lit;
};

// Machine state seen by primitives; run<F> wraps F into the tail-calling function the VM needs.
struct M { Interp &e; intptr_t *s; Instr **r; Instr *ip, *t, *jmp; };

template <auto F> intptr_t *run(Interp &e, intptr_t *s, Instr **r, Instr *ip, Instr *t) {
    M m{e, s, r, ip, t, nullptr};
    F(m);
    if (m.jmp) [[clang::musttail]] return m.jmp->code(e, m.s, m.r, m.ip, m.jmp);
    [[clang::musttail]] return m.ip->word->code(e, m.s, m.r, m.ip + 1, m.ip->word);
}

// ---- compile-time dictionary machinery ----
template <size_t N> struct Str {
    char v[N]; size_t len = N - 1;
    consteval Str(const char (&a)[N]) { std::copy_n(a, N, v); }
    constexpr std::string_view view() const { return {v, len}; }
};
struct Item { // body cell: word reference by name, literal, or raw code pointer
    char name[12]{}; intptr_t lit{}; Code fn{}; int kind{};
    constexpr Item() = default;
    template <size_t N> consteval Item(const char (&s)[N]) { std::copy_n(s, N, name); }
    consteval Item(Code f) : fn(f), kind(2) {}
    consteval Item(std::integral auto x) : lit(x), kind(1) {}
    constexpr std::string_view view() const { return name; }
};
template <Str N, uint8_t Fl, auto Fn, Item... I> struct Def {
    static constexpr auto name = N;
    static constexpr uint8_t flag = Fl;
    static constexpr Code fn = Fn;
    static constexpr size_t n = sizeof...(I);
    static constexpr Item items[n + 1] = {I...};
};
template <class... Ds> struct List {
    template <size_t I> using at = std::tuple_element_t<I, std::tuple<Ds...>>;
    static constexpr size_t size = sizeof...(Ds);
    static consteval size_t idx(std::string_view s) {
        size_t i = 0, found = size;
        for (std::string_view n : {Ds::name.view()...}) { if (n == s) found = i; ++i; }
        if (found == size) throw "unknown word";
        return found;
    }
};

// ---- helpers for writing primitives ----
template <auto V> constexpr auto push = [](M &m) {
    if constexpr (std::is_invocable_v<decltype(V), M &>) *--m.s = V(m);
    else *--m.s = (intptr_t)V;
};
template <auto Mp> constexpr auto addr = [](M &m) { return (intptr_t)&(m.e.*Mp); };
template <auto Mp> constexpr auto val = [](M &m) { return (intptr_t)(m.e.*Mp); };
template <class Op> constexpr auto bin = [](M &m) { m.s[1] = Op{}(m.s[1], m.s[0]); ++m.s; };
template <class Op> constexpr auto cmp = [](M &m) { m.s[1] = -(intptr_t)Op{}(m.s[1], m.s[0]); ++m.s; };
template <class Op> constexpr auto zcmp = [](M &m) { m.s[0] = -(intptr_t)Op{}(m.s[0], 0); };

template <Str N, auto F, uint8_t Fl = 0> using P = Def<N, Fl, run<F>>;
template <Str N, auto V, uint8_t Fl = 0> using K = P<N, push<V>, Fl>;

constexpr auto docol = [](M &m) { *--m.r = m.ip; m.ip = m.t + 1; };
constexpr auto dodoes = [](M &m) { *--m.r = m.ip; m.ip = m.t[1].word; *--m.s = (intptr_t)&m.t[2]; };
constexpr Code DOCOL = run<docol>, DODOES = run<dodoes>;
template <Str N, uint8_t Fl, Item... I> using X = Def<N, Fl, DOCOL, I...>;

// ---- runtime helpers ----
static int key() { int c = getchar(); if (c == EOF) exit(0); return c; }

static intptr_t word(char *buf) {
    int ch; char *s = buf;
    do {
        ch = key();
        if (ch == '\\') do ch = key(); while (ch != '\n');
    } while (ch <= ' ');
    do {
        if (s < buf + WORD_MAX) *s++ = (char)ch;
        ch = key();
    } while (ch > ' ');
    return s - buf;
}

// strtol needs a nul terminator but Forth strings carry a length: parse a bounded copy
static intptr_t number(const char *s, size_t c, intptr_t base, const char *&end) {
    char copy[WORD_MAX + 1], *stop;
    c = std::min(c, WORD_MAX);
    memcpy(copy, s, c);
    copy[c] = '\0';
    intptr_t v = strtol(copy, &stop, (int)base);
    end = s + (stop - copy);
    return v;
}

static Hdr *find(Hdr *w, const char *name, size_t c) {
    while (w && ((w->flag & (F_HIDDEN | F_LENMASK)) != c || memcmp(w->name, name, c))) w = w->link;
    return w;
}

static Instr *cfa(Hdr *w) {
    size_t off = std::max<size_t>((9 + (w->flag & F_LENMASK) + 7) & ~size_t{7}, sizeof(Hdr));
    return (Instr *)((char *)w + off);
}

static void err(const char *s, size_t n) { (void)!write(STDERR_FILENO, s, n); }

// ---- the dictionary ----
constexpr auto lit = [](M &m) { return (m.ip++)->lit; };
constexpr auto branch = [](M &m) { m.ip += m.ip->lit / 8; };
constexpr auto tos = [](M &m) { return m.s[0]; };

using L = List<
    P<"DROP", [](M &m) { ++m.s; }>,
    P<"SWAP", [](M &m) { std::swap(m.s[0], m.s[1]); }>,
    K<"DUP", tos>,
    K<"OVER", [](M &m) { return m.s[1]; }>,
    P<"ROT", [](M &m) { auto a = m.s[0], b = m.s[1], c = m.s[2]; m.s[2] = b; m.s[1] = a; m.s[0] = c; }>,
    P<"-ROT", [](M &m) { auto a = m.s[0], b = m.s[1], c = m.s[2]; m.s[2] = a; m.s[1] = c; m.s[0] = b; }>,
    P<"2DROP", [](M &m) { m.s += 2; }>,
    P<"2DUP", [](M &m) { auto a = m.s[0], b = m.s[1]; *--m.s = b; *--m.s = a; }>,
    P<"2SWAP", [](M &m) { std::swap(m.s[0], m.s[2]); std::swap(m.s[1], m.s[3]); }>,
    P<"?DUP", [](M &m) { if (m.s[0]) --m.s, m.s[0] = m.s[1]; }>,
    P<"1+", [](M &m) { ++m.s[0]; }>,
    P<"1-", [](M &m) { --m.s[0]; }>,
    P<"8+", [](M &m) { m.s[0] += 8; }>,
    P<"8-", [](M &m) { m.s[0] -= 8; }>,
    P<"+", bin<std::plus<>>>,
    P<"-", bin<std::minus<>>>,
    P<"*", bin<std::multiplies<>>>,
    P<"/MOD", [](M &m) {
        auto a = m.s[1], b = m.s[0];
        if (!b) return err("DIVISION BY ZERO\n", 17);
        m.s[1] = b == -1 ? 0 : a % b; // b == -1 would trap on INTPTR_MIN
        m.s[0] = b == -1 ? (intptr_t)(0 - (uintptr_t)a) : a / b;
    }>,
    P<"=", cmp<std::equal_to<>>>,
    P<"<>", cmp<std::not_equal_to<>>>,
    P<"<", cmp<std::less<>>>,
    P<">", cmp<std::greater<>>>,
    P<"<=", cmp<std::less_equal<>>>,
    P<">=", cmp<std::greater_equal<>>>,
    P<"0=", zcmp<std::equal_to<>>>,
    P<"0<>", zcmp<std::not_equal_to<>>>,
    P<"0<", zcmp<std::less<>>>,
    P<"0>", zcmp<std::greater<>>>,
    P<"0<=", zcmp<std::less_equal<>>>,
    P<"0>=", zcmp<std::greater_equal<>>>,
    P<"AND", bin<std::bit_and<>>>,
    P<"OR", bin<std::bit_or<>>>,
    P<"XOR", bin<std::bit_xor<>>>,
    P<"INVERT", [](M &m) { m.s[0] = ~m.s[0]; }>,
    P<"EXIT", [](M &m) { m.ip = *m.r++; }>,
    K<"LIT", lit>,
    P<"!", [](M &m) { auto p = (intptr_t *)m.s[0]; *p = m.s[1]; m.s += 2; }>,
    P<"@", [](M &m) { m.s[0] = *(intptr_t *)m.s[0]; }>,
    P<"+!", [](M &m) { *(intptr_t *)m.s[0] += m.s[1]; m.s += 2; }>,
    P<"-!", [](M &m) { *(intptr_t *)m.s[0] -= m.s[1]; m.s += 2; }>,
    P<"C!", [](M &m) { *(char *)m.s[0] = (char)m.s[1]; m.s += 2; }>,
    P<"C@", [](M &m) { m.s[0] = *(unsigned char *)m.s[0]; }>,
    P<"C@C!", [](M &m) { // ( source dest -- source+1 dest+1 )
        auto d = (char *)m.s[0], s = (char *)m.s[1];
        *d = *s; m.s[0] = (intptr_t)(d + 1); m.s[1] = (intptr_t)(s + 1);
    }>,
    P<"CMOVE", [](M &m) { memmove((void *)m.s[1], (void *)m.s[2], (size_t)m.s[0]); m.s += 3; }>,
    K<"STATE", addr<&Interp::state>>,
    K<"HERE", addr<&Interp::here>>,
    K<"LATEST", addr<&Interp::latest>>,
    K<"S0", addr<&Interp::s0>>,
    K<"BASE", addr<&Interp::base>>,
    K<"(ARGC)", val<&Interp::argc>>,
    K<"VERSION", 47>,
    K<"R0", val<&Interp::r0>>,
    K<"DOCOL", DOCOL>,
    K<"DODOES", DODOES>,
    K<"F_IMMED", F_IMMED>,
    K<"F_HIDDEN", F_HIDDEN>,
    K<"F_LENMASK", F_LENMASK>,
    K<"SYS_EXIT", SYS_exit>,
    K<"SYS_OPEN", SYS_open>,
    K<"SYS_CLOSE", SYS_close>,
    K<"SYS_READ", SYS_read>,
    K<"SYS_WRITE", SYS_write>,
    K<"SYS_CREAT", SYS_creat>,
    K<"SYS_BRK", SYS_brk>,
    K<"O_RDONLY", O_RDONLY>,
    K<"O_WRONLY", O_WRONLY>,
    K<"O_RDWR", O_RDWR>,
    K<"O_CREAT", O_CREAT>,
    K<"O_EXCL", O_EXCL>,
    K<"O_TRUNC", O_TRUNC>,
    K<"O_APPEND", O_APPEND>,
    K<"O_NONBLOCK", O_NONBLOCK>,
    P<">R", [](M &m) { *--m.r = (Instr *)*m.s++; }>,
    K<"R>", [](M &m) { return (intptr_t)*m.r++; }>,
    K<"RSP@", [](M &m) { return (intptr_t)m.r; }>,
    P<"RSP!", [](M &m) { m.r = (Instr **)*m.s++; }>,
    P<"RDROP", [](M &m) { ++m.r; }>,
    K<"DSP@", [](M &m) { return (intptr_t)m.s; }>,
    P<"DSP!", [](M &m) { m.s = (intptr_t *)m.s[0]; }>,
    K<"KEY", [](M &) { return (intptr_t)key(); }>,
    P<"EMIT", [](M &m) { putchar((int)*m.s++); fflush(stdout); }>,
    P<"WORD", [](M &m) { *--m.s = (intptr_t)m.e.buffer; *--m.s = word(m.e.buffer); }>,
    P<"NUMBER", [](M &m) {
        auto c = m.s[0]; auto s = (const char *)m.s[1]; const char *r;
        m.s[1] = number(s, (size_t)c, m.e.base, r);
        m.s[0] = r - s - c;
    }>,
    P<"FIND", [](M &m) { auto c = m.s[0]; m.s[1] = (intptr_t)find(m.e.latest, (char *)m.s[1], (size_t)c); ++m.s; }>,
    P<">CFA", [](M &m) { m.s[0] = (intptr_t)cfa((Hdr *)m.s[0]); }>,
    X<">DFA", 0, ">CFA", "8+", "EXIT", "EXIT">,
    P<"CREATE", [](M &m) {
        auto c = *m.s++; auto s = (char *)*m.s++;
        auto w = (Hdr *)(((intptr_t)m.e.here + 7) & -8);
        w->link = m.e.latest; w->flag = (uint8_t)c; memcpy(w->name, s, (size_t)c);
        m.e.here = (char *)cfa(w); m.e.latest = w;
    }>,
    P<",", [](M &m) { auto p = (Instr *)m.e.here; (p++)->word = (Instr *)*m.s++; m.e.here = (char *)p; }>,
    P<"[", [](M &m) { m.e.state = 0; }, F_IMMED>,
    P<"]", [](M &m) { m.e.state = 1; }>,
    P<"IMMEDIATE", [](M &m) { m.e.latest->flag ^= F_IMMED; }, F_IMMED>,
    P<"HIDDEN", [](M &m) { ((Hdr *)*m.s++)->flag ^= F_HIDDEN; }>,
    X<"HIDE", 0, "WORD", "FIND", "HIDDEN", "EXIT">,
    X<":", 0, "WORD", "CREATE", "LIT", DOCOL, ",", "LATEST", "@", "HIDDEN", "]", "EXIT">,
    X<";", F_IMMED, "LIT", "EXIT", ",", "LATEST", "@", "HIDDEN", "[", "EXIT">,
    K<"'", lit>,
    P<"BRANCH", branch>,
    P<"0BRANCH", [](M &m) { if (!*m.s++) branch(m); else ++m.ip; }>,
    P<"LITSTRING", [](M &m) {
        auto c = (m.ip++)->lit;
        *--m.s = (intptr_t)m.ip; *--m.s = c;
        m.ip += (c + 8) / 8;
    }>,
    P<"TELL", [](M &m) { (void)!write(STDOUT_FILENO, (void *)m.s[1], (size_t)m.s[0]); m.s += 2; }>,
    P<"INTERPRET", [](M &m) {
        Interp &e = m.e;
        if (m.s > e.s0) { err("STACK UNDERFLOW\n", 16); m.s = e.s0; }
        auto p = (Instr *)e.here;
        auto c = word(e.buffer);
        if (Hdr *w = find(e.latest, e.buffer, (size_t)c)) {
            Instr *t = cfa(w);
            if ((w->flag & F_IMMED) || !e.state) { m.jmp = t; return; }
            (p++)->word = t;
        } else {
            const char *r;
            auto a = number(e.buffer, (size_t)c, e.base, r);
            if (r == e.buffer) { err("PARSE ERROR: ", 13); err(e.buffer, (size_t)c); err("\n", 1); }
            else if (e.state) { (p++)->word = e.lit; (p++)->lit = a; }
            else *--m.s = a;
        }
        e.here = (char *)p;
    }>,
    X<"QUIT", 0, "R0", "RSP!", "INTERPRET", "BRANCH", -16, "EXIT">,
    P<"CHAR", [](M &m) { word(m.e.buffer); *--m.s = m.e.buffer[0]; }>,
    P<"EXECUTE", [](M &m) { m.jmp = (Instr *)*m.s++; }>,
    P<"SYSCALL3", [](M &m) {
        auto s = m.s;
        switch (s[0]) {
            case SYS_open: s[3] = openat(AT_FDCWD, (const char *)s[1], (int)s[2], (mode_t)s[3]); break;
            case SYS_read: s[3] = read((int)s[1], (void *)s[2], (size_t)s[3]); break;
            case SYS_write: s[3] = write((int)s[1], (const void *)s[2], (size_t)s[3]); break;
            default: s[3] = -1;
        }
        m.s += 3;
    }>,
    P<"SYSCALL2", [](M &m) {
        auto s = m.s;
        switch (s[0]) {
            case SYS_open: s[2] = openat(AT_FDCWD, (const char *)s[1], (int)s[2]); break;
            case SYS_access: s[2] = access((const char *)s[1], (int)s[2]); break;
            default: s[2] = -1;
        }
        m.s += 2;
    }>,
    P<"SYSCALL1", [](M &m) {
        auto s = m.s;
        switch (s[0]) {
            case SYS_exit: exit((int)s[1]);
            case SYS_close: s[1] = close((int)s[1]); break;
            case SYS_brk:
                if (s[1]) sbrk(s[1] - (intptr_t)sbrk(0));
                s[1] = (intptr_t)sbrk(0);
                break;
            case SYS_setuid: s[1] = setuid((uid_t)s[1]); break;
            default: s[1] = -1;
        }
        ++m.s;
    }>,
    P<"SYSCALL0", [](M &m) { m.s[0] = m.s[0] == SYS_getuid ? (intptr_t)getuid() : -1; }>
>;

// One nested aggregate keeps entries contiguous and in ascending order, which SEE relies on
// to find where a word ends. Each ctor resolves names against the already-built root object.
template <size_t I> struct Chain;
template <size_t J, size_t I = 0> constexpr auto &at_(Chain<I> &c) {
    if constexpr (J == I) return c.w;
    else return at_<J, I + 1>(c.next);
}

template <Item it> constexpr Instr resolve(auto *root) {
    Instr r{};
    if constexpr (it.kind == 0) r.word = &at_<L::idx(it.view())>(*root).code;
    else if constexpr (it.kind == 1) r.lit = it.lit;
    else r.code = it.fn;
    return r;
}

template <size_t I> constexpr W<L::at<I>::n> make(auto *root) {
    using D = L::at<I>;
    W<D::n> w{};
    if constexpr (I) w.link = &at_<I - 1>(*root);
    w.flag = D::flag | (uint8_t)D::name.len;
    std::copy_n(D::name.v, D::name.len, w.name);
    w.code.code = D::fn;
    [&]<size_t... k>(std::index_sequence<k...>) { ((w.data[k] = resolve<D::items[k]>(root)), ...); }(
        std::make_index_sequence<D::n>{});
    return w;
}

template <size_t I> struct Chain {
    W<L::at<I>::n> w; Chain<I + 1> next;
    constexpr Chain(auto *root) : w(make<I>(root)), next(root) {}
};
template <> struct Chain<L::size> { constexpr Chain(auto *) {} };
inline constinit Chain<0> dict{&dict};

int main(int, char *argv[]) {
    enum { N = 0x100 };
    intptr_t stack[N];
    Instr *return_stack[N];
    char *memory = (char *)sbrk(0x10000);
    if (memory == (char *)-1) return 1;
    Interp env{.state = 0, .latest = &at_<L::size - 1>(dict), .argc = (intptr_t *)&argv[-1], .s0 = stack + N,
               .base = 10, .r0 = return_stack + N, .buffer = {}, .here = memory,
               .lit = &at_<L::idx("LIT")>(dict).code};
    static Instr cold_start[] = {{.word = &at_<L::idx("QUIT")>(dict).code}};
    Instr *ip = cold_start;
    ip->word->code(env, env.s0, env.r0, ip, ip->word); // never returns: EOF calls exit()
}
