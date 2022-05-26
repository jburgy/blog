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
import Base: Fix1, eltype, iterate, length
using Test: @test, @testset

# https://docs.julialang.org/en/v1/manual/types/#%22Value-types%22
const OpChar = Val{0x1d}
const OpPosStar = Val{0x2a}
const OpAlt = Val{0x78}
const OpKet = Val{0x79}
const OpKetRMax = Val{0x7a}
const OpBra = Val{0x86}
const OpCBra = Val{0x88}
const OpBraZero = Val{0x96}

exprs = Dict{Symbol,Tuple{Expr,Vararg{Expr}}}(
    :char! => (quote
            op ≡ char && push!(next, ((i & ~2) | 1) + (2 << 2))
            false
        end, :(op::Char)),
    :posstar! => (quote
            local j = i | 1
            push!(curr, j + (2 << 2))
            op ≡ char && push!(next, j)
            false
        end, :(op::Char)),
    :alt! => (quote
            push!(curr, i + (3 << 2), i + link)
            false
        end, :(link::UInt16)),
    :ket! => (:((i & 3) ≠ 0 && char ≡ '\0'), :(link::UInt16)),
    :ketrmax! => (quote
            (i & 3) ≠ 0 && push!(curr, (i | 1) + (3 << 2))
            (i & 3) ≡ 1 && push!(curr, (i | 2) - link)
            false
        end, :(link::UInt16)),
    :bra! => (quote
            push!(curr, i + (3 << 2))
            (i & 2) ≠ 0 && push!(curr, i + link)
            false
        end, :(link::UInt16)),
    :cbra! => (quote
            push!(curr, i + (5 << 2))
            (i & 2) ≠ 0 && push!(curr, i + link)
            false
        end, :(link::UInt16)),
    :brazero! => (quote
        push!(curr, (i | 2) + 4)
        false
    end,),
)

for (name, (expr, args...)) ∈ exprs
    @eval function $name($(args...), curr::Vector{Int64}, next::Vector{Int64}, char::Char, i::Int64)
        $expr
    end
end

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

opcode(::OpChar, ptr::Ptr{UInt8}, i::Int) = Fix1(char!, Char(unsafe_load(ptr, i)))
opcode(::OpPosStar, ptr::Ptr{UInt8}, i::Int) = Fix1(posstar!, Char(unsafe_load(ptr, i)))
opcode(::OpAlt, ptr::Ptr{UInt8}, i::Int) = Fix1(alt!, link(ptr, i) << 2)
opcode(::OpKet, ptr::Ptr{UInt8}, i::Int) = Fix1(ket!, link(ptr, i) << 2)
opcode(::OpKetRMax, ptr::Ptr{UInt8}, i::Int) = Fix1(ketrmax!, link(ptr, i) << 2)
opcode(::OpBra, ptr::Ptr{UInt8}, i::Int) = Fix1(bra!, link(ptr, i) << 2)
opcode(::OpCBra, ptr::Ptr{UInt8}, i::Int) = Fix1(cbra!, link(ptr, i) << 2)
opcode(::OpBraZero, ptr::Ptr{UInt8}, ::Int) = brazero!

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
eltype(::Type{OpCodes}) = Pair{Int,Function}

(f::Fix1)(curr::Vector{Int64}, next::Vector{Int64}, char::Char, i::Int64) = f.f(f.x, curr, next, char, i)

# http://www.oilshell.org/archive/Thompson-1968.pdf
function match(opcodes::Dict{Int,Function}, string::String)
    curr = [2]
    next = empty(curr)
    for char ∈ string * "\0"
        for i ∈ curr
            opcodes[i>>2](curr, next, char, i) && return true
        end
        copy!(curr, next)
        empty!(next)
    end
    false
end

function jit(opcodes::Dict{Int,Function})
    stmts = [:(local jmp = i >> 2)]
    for (index, opcode) ∈ opcodes
        x = opcode isa Fix1 ? opcode.x : nothing
        (expr, args...) = isnothing(x) ? (exprs[Symbol(opcode)]..., :(dummy::Nothing)) : exprs[Symbol(opcode.f)]
        push!(stmts, quote
            if jmp == $index
                let $(args...) = $x
                    $expr && return true
                end
            end
        end)
    end
    body = Expr(:block, stmts...)
    match! = quote
        (string::String) -> begin
            curr = [2]
            next = empty(curr)
            for char ∈ string * "\0"
                for i ∈ curr
                    $body
                end
                copy!(curr, next)
                empty!(next)
            end
            false
        end
    end
    eval(match!)
end

@testset "match" begin
    tests = Dict{String,Dict{String,Bool}}(
        "abc" => Dict("ab" => false, "bc" => false, "abc" => true),
        "ab|c" => Dict("a" => false, "ac" => false, "ab" => true, "c" => true),
        "a*" => Dict("" => true, "aaa" => true, "aba" => false),
        "(ab)*" => Dict("" => true, "abab" => true, "abb" => false),
        "(a|b)*" => Dict("" => true, "abba" => true, "abc" => false),
        "a(b|c)*d" => Dict("ad" => true, "abc" => false, "abd" => true, "acd" => true),
    )

    @testset "$regexp" for (regexp, cases) ∈ tests
        code = Dict(OpCodes(compile(regexp, 0)))
        jitted = jit(code)
        @testset "$string" for (string, matches) ∈ cases
            @test match(code, "$string") ≡ matches
            @test jitted("$string") ≡ matches
        end
    end
end
