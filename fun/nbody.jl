# The Computer Language Benchmarks Game
# http://benchmarksgame.alioth.debian.org/
#
# originally by Kevin Carson
# modified by Tupteq, Fredrik Johansson, and Daniel Nanz
# modified by Maciej Fijalkowski


using LinearAlgebra.BLAS: BlasInt, axpy!, libblas, hpmv!

const REAL, IMAG = 1:2

"""
character                   UPLO,
integer                     N,
double precision            ALPHA,
complex*16, dimension(*)    X,
integer                     INCX,
complex*16, dimension(*)    AP
"""
hpr!(α::Float64, x::AbstractVector{ComplexF64}, ap::AbstractVector{ComplexF64}) = ccall(
    (:zhpr_64_, libblas), Cvoid,
    (Ref{UInt8}, Ref{BlasInt}, Ref{Float64}, Ptr{Float64}, Ref{BlasInt}, Ref{ComplexF64}),
    'U', length(x), α, x, 1, ap
)

"""
character                       UPLO,
integer                         N,
double precision                ALPHA,
double precision, dimension(*)  X,
integer                         INCX,
double precision, dimension(*)  Y,
integer                         INCY,
double precision, dimension(*)  AP
"""
spr2!(α::Float64, x::AbstractVector{Float64}, y::AbstractVector{Float64}, ap::AbstractVector{Float64}) = ccall(
    (:dspr2_64_, libblas), Cvoid,
    (Ref{UInt8}, Ref{BlasInt}, Ref{Float64}, Ptr{Float64}, Ref{BlasInt}, Ptr{Float64}, Ref{BlasInt}, Ref{Float64}),
    'U', length(x), α, x, 1, y, 1, ap
)

x = [
    0.0 0.0 0.0
    4.84143144246472090e+00 -1.16032004402742839e+00 -1.03622044471123109e-01
    8.34336671824457987e+00 4.12479856412430479e+00 -4.03523417114321381e-01
    1.28943695621391310e+01 -1.51111514016986312e+01 -2.23307578892655734e-01
    1.53796971148509165e+01 -2.59193146099879641e+01 1.79258772950371181e-01
]
v = [
    0.0 0.0 0.0
    1.66007664274403694e-03 7.69901118419740425e-03 -6.90460016972063023e-05
    -2.76742510726862411e-03 4.99852801234917238e-03 2.30417297573763929e-05
    2.96460137564761618e-03 2.37847173959480950e-03 -2.96589568540237556e-05
    2.68067772490389322e-03 1.62824170038242295e-03 -9.51592254519715870e-05
] * 0.36524
m = [
1.0 9.54791938424326609e-04 2.85885980666130812e-04 4.36624404335156298e-05 5.15138902046611451e-05
] * 4π^2

v[1, :] = -m * v / m[1]
a = Matrix{ComplexF64}(undef, size(x))
ar = reinterpret(reshape, Float64, a)

jm = m * -1im
n = length(m)
# see https://stackoverflow.com/a/52564537/8479938
# only need upper triangle plus diagonal hence ½ n x (n + 1)
ap = Matrix{ComplexF64}(undef, (n * (n + 1) ÷ 2, 3))
apr = reinterpret(reshape, Float64, ap)
xxT = Vector{Float64}(undef, size(ap, 1))
d = Vector{Float64}(undef, size(ap, 1))
trid = cumsum(1:n)  # triangular diagonal
x2 = Vector{Float64}(undef, n)
ones_ = ones(n)

dt = 0.01

for _ ∈ 1:20_000
    copyto!(view(ar, REAL, :, :), x)
    fill!(view(ar, IMAG, :, :), -1.0)
    fill!(ap, 0.0im)
    for d ∈ 1:3
        # A += α z z*
        hpr!(-2.0, view(a, :, d), view(ap, :, d))
    end
    sum!(xxT, view(apr, REAL, :, :))
    xxT .+= 6
    x2[:] = @view xxT[trid]
    # A += α (x yᵀ + y xᵀ)
    spr2!(-0.5, x2, ones_, xxT)

    map!(√, d, xxT)
    xxT .*= d
    view(apr, IMAG, :, :) ./= xxT
    replace!(view(apr, IMAG, :, :), NaN => 0.0)

    for d ∈ 1:3
        # y = α A x + β y
        hpmv!('U', 0.5, view(ap, :, d), jm, 0.0, view(a, :, d))
    end
    axpy!(dt, view(ar, REAL, :, :), v)  # v += a dt
    axpy!(dt, v, x)  # x += v dt
end

show(stdout, "text/plain", x)
println()
