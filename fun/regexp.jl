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

# https://docs.julialang.org/en/v1/manual/types/#%22Value-types%22
const OpChar = Val{0x1d}
const OpAlt = Val{0x78}
const OpKet = Val{0x79}
const OpBra = Val{0x86}

struct Alt
    link::UInt16
end

struct Ket end

struct Bra
    link::UInt16
end

const OpCode = Union{Char,Alt,Ket,Bra}

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

length(::OpChar) = 1
length(::OpAlt) = 2
length(::OpKet) = 0
length(::OpBra) = 2

bracket(::OpChar) = 0
bracket(::OpAlt) = 0
bracket(::OpKet) = -1
bracket(::OpBra) = 1

link(ptr::Ptr{UInt8}, i::Int) = UInt16(unsafe_load(ptr, i) << 8) | UInt16(unsafe_load(ptr, i + 1))

opcode(::OpChar, ptr::Ptr{UInt8}, i::Int) = Char(unsafe_load(ptr, i))
opcode(::OpAlt, ptr::Ptr{UInt8}, i::Int) = Alt(link(ptr, i))
opcode(::OpKet, ptr::Ptr{UInt8}, i::Int) = Ket()
opcode(::OpBra, ptr::Ptr{UInt8}, i::Int) = Bra(link(ptr, i))

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

function accept!(curr::Vector{Int}, next::Vector{Int}, char::Char, i::Int, op::Union{Alt,Bra})
    push!(curr, i + 3, i + op.link)
    false
end

function accept!(curr::Vector{Int}, next::Vector{Int}, char::Char, i::Int, op::Ket)
    char == '\0'
end

function accept!(curr::Vector{Int}, next::Vector{Int}, char::Char, i::Int, op::Char)
    op == char && push!(next, i + 2)
    false
end

# http://www.oilshell.org/archive/Thompson-1968.pdf
function match(opcodes::Dict{Int,OpCode}, string::String)
    curr = [0]
    next = empty(curr)
    for char ∈ string * "\0"
        for i ∈ curr
            accept!(curr, next, char, i, opcodes[i]) && return true
        end
        copyto!(curr, next)
        empty!(next)
    end
    false
end

code = OpCodes(compile("abc|def|ghi", 3))
match(Dict(code), "abc")
