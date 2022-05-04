"""
https://en.wikipedia.org/wiki/Kleene%27s_algorithm in julia

Julia's seamless interoperability with C lets us skip the boring steps of
tokenizing and lexing the regular expression and let `PCRE.compile` take
handle it.  Only the bare minimum is interpreter.

https://github.com/PhilipHazel/pcre2/blob/master/HACKING is a great resource
to understand PCRE's internals
"""

using Base: HasEltype, IteratorEltype, IteratorSize, SizeUnknown
using Base.PCRE: INFO_NAMECOUNT, INFO_NAMEENTRYSIZE, INFO_NAMETABLE, compile, info
import Base: eltype, iterate, length
using DataStructures
using Test

# https://docs.julialang.org/en/v1/manual/types/#%22Value-types%22
const OpChar = Val{0x1d}
const OpPosStar = Val{0x2a}
const OpAlt = Val{0x78}
const OpKet = Val{0x79}
const OpKetRMax = Val{0x7a}
const OpBra = Val{0x86}
const OpCBra = Val{0x88}
const OpBraZero = Val{0x96}

struct PosStar
    char::Char
end

struct Alt
    link::UInt16
end

struct Ket
    link::UInt16
end

struct KetRMax
    link::UInt16
end

struct Bra
    link::UInt16
end

struct CBra
    link::UInt16
    group::UInt16
end

struct BraZero end

const OpCode = Union{Char,PosStar,Alt,Ket,KetRMax,Bra,CBra,BraZero}

"""
Helper struct to convert a compiled https://www.pcre.org/ (which is just a `Ptr{Uint8}`) into
an iterator of (`Int`,`OpCode`) pairs.  Integers refer to jumps in the original bytestream.
They don't line up with indices in a vector of opcodes because instructions have variable
lengths.  `OpKet` take 1 byte, `OpChar` need a 2nd byte to encode the character being matched,
and `OpAlt` and `OpBra` need 2 extra bytes to encode a link.
"""
struct OpCodes
    ptr::Ptr{UInt8}
    start::Int

    function OpCodes(ptr::Ptr{Nothing})
        # https://github.com/PhilipHazel/pcre2/blob/master/src/pcre2_study.c
        # /* Find start of compiled code */
        # 
        # code = (PCRE2_UCHAR *)((uint8_t *)re + sizeof(pcre2_real_code)) +
        #   re->name_entry_size * re->name_count;

        # https://github.com/PhilipHazel/pcre2/blob/master/src/pcre2_pattern_info.c
        # case PCRE2_INFO_NAMETABLE:
        # *((PCRE2_SPTR *)where) = (PCRE2_SPTR)((char *)re + sizeof(pcre2_real_code));
        # break;
        name_count = info(ptr, INFO_NAMECOUNT, UInt32)
        name_entry_size = info(ptr, INFO_NAMEENTRYSIZE, UInt32)
        # code starts immediately _after_ captured names
        new(info(ptr, INFO_NAMETABLE, Ptr{UInt8}), name_count * name_entry_size + 1)
    end
end

length(::Union{OpChar,OpPosStar}) = 1
length(::OpBraZero) = 0
length(::Union{OpAlt,OpKet,OpKetRMax,OpBra}) = 2
length(::OpCBra) = 4

bracket(::Union{OpChar,OpPosStar,OpAlt,OpBraZero}) = 0
bracket(::Union{OpKet,OpKetRMax}) = -1
bracket(::Union{OpBra,OpCBra}) = 1

link(ptr::Ptr{UInt8}, i::Int) = UInt16(unsafe_load(ptr, i) << 8) | UInt16(unsafe_load(ptr, i + 1))

opcode(::OpChar, ptr::Ptr{UInt8}, i::Int) = Char(unsafe_load(ptr, i))
opcode(::OpPosStar, ptr::Ptr{UInt8}, i::Int) = PosStar(Char(unsafe_load(ptr, i)))
opcode(::OpAlt, ptr::Ptr{UInt8}, i::Int) = Alt(link(ptr, i))
opcode(::OpKet, ptr::Ptr{UInt8}, i::Int) = Ket(link(ptr, i))
opcode(::OpKetRMax, ptr::Ptr{UInt8}, i::Int) = KetRMax(link(ptr, i))
opcode(::OpBra, ptr::Ptr{UInt8}, i::Int) = Bra(link(ptr, i))
opcode(::OpCBra, ptr::Ptr{UInt8}, i::Int) = CBra(link(ptr, i), link(ptr, i + 2))
opcode(::OpBraZero, ptr::Ptr{UInt8}, ::Int) = BraZero()

# https://docs.julialang.org/en/v1/manual/interfaces/
function iterate(code::OpCodes)
    ptr = code.ptr
    offset = code.start
    byte = Val(unsafe_load(ptr, offset))
    offset - 1 => opcode(byte, ptr, offset + 1), (bracket(byte), offset + length(byte) + 1)
end

function iterate(code::OpCodes, state::Tuple{Int,Int})
    brackets, offset = state
    brackets > 0 || return nothing
    ptr = code.ptr
    byte = Val(unsafe_load(ptr, offset))
    offset - 1 => opcode(byte, ptr, offset + 1), (brackets + bracket(byte), offset + length(byte) + 1)
end

IteratorSize(::Type{OpCodes}) = SizeUnknown()
IteratorEltype(::Type{OpCodes}) = HasEltype()
eltype(::Type{OpCodes}) = Pair{Int,OpCode}

# http://www.oilshell.org/archive/Thompson-1968.pdf
function match(opcodes::Dict{Int,OpCode}, string::String)
    accept!(char::Char, i::Int, op::Char) = (op == char && push!(next, i + 2); false)
    function accept!(char::Char, i::Int, op::PosStar)
        push!(curr, i + 2)
        op.char == char && push!(next, i)
        false
    end
    zero = Ref(false)
    function accept!(::Char, i::Int, op::Union{Alt,Bra,CBra})
        push!(curr, i + (op isa CBra ? 5 : 3))
        if zero[] || !(opcodes[i+op.link] isa Union{Ket,KetRMax})
            push!(curr, i + op.link)
        end
        false
    end
    function accept!(::Char, i::Int, op::KetRMax)
        zero[] = false
        push!(curr, i + 3, i - op.link)
        false
    end
    accept!(char::Char, ::Int, ::Ket) = char == '\0'
    function accept!(::Char, i::Int, ::BraZero)
        zero[] = true
        push!(curr, i + 1)
        false
    end

    curr = [0]
    next = empty(curr)
    for char ∈ string * "\0"
        zero[] = char == '\0'
        for i ∈ curr
            accept!(char, i, opcodes[i]) && return true
        end
        copy!(curr, next)
        empty!(next)
    end
    false
end

@testset "match" begin
    tests = Dict{String,Dict{String,Bool}}(
        "abc" => Dict("ab" => false, "bc" => false, "abc" => true),
        "ab|c" => Dict("a" => false, "ac" => false, "ab" => true, "c" => true),
        "a*" => Dict("" => true, "aaa" => true, "aba" => false),
        "(ab)*" => Dict("" => true, "abab" => true, "abb" => false),
        "(a|b)*" => Dict("" => true, "abba" => true, "abc" => false),
        "a(b|c)*d" => Dict("ad" => true, "acd" => true),
    )

    @testset "$regexp" for (regexp, cases) ∈ tests
        code = Dict(OpCodes(compile(regexp, 0)))
        @testset "$string" for (string, matches) ∈ cases
            @test match(code, "$string") == matches
        end
    end
end
