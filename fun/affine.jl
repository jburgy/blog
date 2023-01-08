# https://en.wikipedia.org/wiki/Affine_scaling

using Base.Order: Forward
using LinearAlgebra: Diagonal, Symmetric, Transpose, axpy!, ldiv!, lmul!, lu!
import LinearAlgebra: mul!

struct SparseMatrixCSR{T} <: AbstractArray{T,2}
    data::Vector{T}
    indices::Vector{keytype(Vector)}
    indptr::Vector{keytype(Vector)}

    function SparseMatrixCSR{T}(data::Vector{T}, indices::Vector{keytype(Vector)}, indptr::Vector{keytype(Vector)}) where {T}
        new(data, indices, indptr)
    end
end

size(a::SparseMatrixCSR{T}) where {T} = (length(a.indptr) - 1, maximum(a.indices))

function mul!(y::SparseMatrixCSR{T}, a::SparseMatrixCSR{T}, x::Diagonal{T}, α::Number=1.0, β::Number=0.0) where {T}
    copyto!(y.indices, a.indices)
    copyto!(y.indptr, a.indptr)
    for i ∈ eachindex(y.indptr)[1:end-1]
        for k ∈ y.indptr[i]:y.indptr[i+1]-1
            y.data[k] = α * a.data[k] * x.diag[y.indices[k]] + β * y.data[k]
        end
    end
    y
end

function mul!(y::Vector{T}, tA::Transpose{T,SparseMatrixCSR{T}}, x::Vector{T}, α::Number=1.0, β::Number=0.0) where {T}
    a = tA.parent
    for i ∈ eachindex(a.indptr)[1:end-1]
        αxi = α * x[i]
        for k ∈ a.indptr[i]:a.indptr[i+1]-1
            j = a.indices[k]
            y[j] = αxi * a.data[k] + β * y[j]
        end
    end
    y
end

function mul!(y::Vector{T}, a::SparseMatrixCSR{T}, x::Vector{T}, α::Number=1.0, β::Number=0.0) where {T}
    for i ∈ eachindex(a.indptr)[1:end-1]
        y[i] = α * sum(a.data[j] * x[a.indices[j]] for j ∈ a.indptr[i]:a.indptr[i+1]-1) + β * y[i]
    end
    y
end

function ad2aT!(y::Symmetric{T,Matrix{T}}, a::SparseMatrixCSR{T}, d2::Diagonal{T}) where {T}
    for j ∈ eachindex(a.indptr)[1:end-1]
        for i ∈ eachindex(a.indptr)[1:j]
            n = a.indptr[j]
            y.data[i, j] = sum(a.indptr[i]:a.indptr[i+1]-1) do k
                m = a.indices[k]
                n = searchsortedfirst(a.indices, m, n, a.indptr[j+1] - 1, Forward)
                a.indices[n] == m ? a.data[n] * d2[m, m] * a.data[k] : 0.0
            end
        end
    end
    y
end

function affine_scaling!(x::Vector{T}, A::SparseMatrixCSR{T}, b::Vector{T}, c::Vector{T}; ε=1e-8, β=0.99) where {T}
    d = Diagonal(copy(c))
    d2 = similar(d)
    Ad2 = deepcopy(A)
    r = similar(c)
    w = similar(b)
    Ad2AT = Symmetric(Matrix{T}(undef, (length(b), length(b))))
    while true
        copyto!(d.diag, x)
        mul!(d2.diag, d, x)
        mul!(Ad2, A, d2)
        ad2aT!(Ad2AT, A, d2)
        ldiv!(lu!(Ad2AT), mul!(w, Ad2, c))
        copyto!(r, c)
        mul!(r, transpose(A), w, -1.0, 1.0)
        mul!(r, d, r)
        if all(>=(0.0), r) && sum(r) < ε
            break
        end
        lmul!(β / maximum(r), r)
        mul!(x, d, r, -1.0, 1.0)  # x = x - diag(x)*r
    end
    return x
end

A = SparseMatrixCSR{Float64}([1.0, -1.0, 1.0, 1.0, 1.0], [1, 2, 3, 2, 4], [1, 4, 6])
b = [15.0, 15.0]
c = [-2.0, 1.0, 0.0, 0.0]
x = [10.0, 2.0, 7.0, 13.0]
println(affine_scaling!(x, A, b, c))
# println(ad2aT!(Vector{Float64}(undef, 3), A, x))