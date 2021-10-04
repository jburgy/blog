"""
    Prechelt

> Find a sequence of words such that the sequence of characters in these words exactly corresponds to the sequence of
> digits in the phone number. All possible solutions must be found and printed. The solutions are created word by word
> and if no word from the dictionary can be inserted at some point during that process, a single digit from the phone
> number can appear in the result at that position. Many phone numbers have no solution at all. Here is an example of
> the program output for the phone number “3586-75,” when the dictionary contained the words "Dali," "um," "Sao," "da,"
> "Pik," and 73,108 others:
>
>     3586-75: Dali um
>     3586-75: Sao 6 um
>     3586-75: da Pik 5
> 
> A list of partial solutions needs to be maintained by the program while processing each number, and the dictionary
> must be embedded in a supporting data structure (such as a 10-ary digit tree) for efficient access.
>
>  -- <cite>Prechelt, Lutz. (1999). Comparing Java vs. C/C++ Efficiency Differences to Interpersonal Differences. Communications of the ACM. 42. 10.1145/317665.317683.</quote>

This implementation uses the [Aho-Corasick algorithm](https://en.wikipedia.org/wiki/Aho%E2%80%93Corasick_algorithm)
with two small specializations

    * words are mapped to digits as they are inserted in the Aho-Corasick data structure
    * the data structure uses fixed length arrays to minimize memory allocations

```jldoctest
julia> replaceall("358", ["Sao", "dal"])
1-element Vector{String}:
 "dal"

```
"""

const DIGITS = Vector{Int}(undef, 128)
DIGITS[codeunits("0123456789")] = 1:10
DIGITS[codeunits("ejnqrwxdsyftamcivbkulopghz")] = DIGITS[codeunits("01112223334455666777888999")]
DIGITS[codeunits("EJNQRWXDSYFTAMCIVBKULOPGHZ")] = DIGITS[codeunits("01112223334455666777888999")]

mutable struct Node
    depth::Int
    keys::Vector{String}
    next::Vector{Union{Missing, Node}}
    fail::Node

    function Node(depth::Int=0)
        node = new()
        node.depth = depth
        node.keys = String[]
        node.next = Vector{Union{Missing, Node}}(missing, 10)
        node
    end
end

digits(s::String) = DIGITS[codeunits(s)]

function insert!(node::Node, word::String)
    for digit ∈ digits(word)
        next = node.next[digit]
        if ismissing(node.next[digit])
            node.next[digit] = next = Node(node.depth + 1)
        end
        node = next
    end
    push!(node.keys, word)
end

function add_fail_transition!(node::Node)
    fail = node.fail
    for (index, next) ∈ enumerate(node.next)
        ismissing(next) && continue
        next.fail = coalesce(fail.next[index], fail)
    end
    for next ∈ skipmissing(node.next)
        add_fail_transition!(next)
    end
end

function search(node::Node, index::Int)
    coalesce(node.next[index], node.depth == 0 ? node : search(node.fail, index))
end

function aho_corasick(words::Union{Base.EachLine,Vector{String}})
    node = Node()
    node.fail = node
    for word ∈ words
        insert!(node, word)
    end
    for next ∈ skipmissing(node.next)
        next.fail = node
    end
    for next ∈ skipmissing(node.next)
        add_fail_transition!(next)
    end
    node
end

crossjoin(heads::Vector{String}, tails::Vector{String}) = reduce(tails; init=[]) do partial, tail
    [partial; heads .* tail]
end

function replaceall(number::String, node::Node)
    """
    ```jldoctest
    julia> replaceall("358675", ["Dali", "um", "Sao", "da", "Pik"])
    3-element Vector{String}:
     "Dalium"
     "Sao6um"
     "daPik5"
    
    ```
    """    
    heads = Vector{Union{Missing,Vector{String}}}(missing, length(number))
    for (k, digit) ∈ enumerate(digits(number))
        node = next = search(node, digit)
        while length(next.keys) > 0
            rest = next.keys
            j = k - node.depth
            i = j - 1

            heads[k] = if j <= 1
                rest
            elseif j == 2
                crossjoin(heads[j], rest)
            else
                [crossjoin(heads[j], rest); crossjoin(heads[i], number[i:i] .* rest)]
            end
            next = next.fail
        end
    end
    filter(s -> count(r"\d", s) <= 1, [heads[end]; heads[end-1] .* number[end:end]])
end

replaceall(number::String, words::Vector{String}) = replaceall(number, aho_corasick(words))
