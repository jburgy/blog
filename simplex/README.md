# The Revised Simplex Method with Reinversion and Refinement

[`simplex.py`](simplex.py) is a NumPy transcription of `SMPLX`/`SMPLX1` from
[`SMPLX.F`](SMPLX.F), written by Alfred H. Morris, Jr. (Naval Surface Weapons
Center, 1977–1990). The comments in the Python source refer back to the
statement labels of the Fortran, so `# 400` marks the ratio test, `# 500` the
pivot, and so on. This note explains what those blocks compute.

## The problem

Given $A \in \mathbb{R}^{m \times n_0}$, $b_0 \in \mathbb{R}^m_{\ge 0}$ and
$c \in \mathbb{R}^{n_0}$,

$$\text{maximize } c^{\mathsf T} x \quad \text{subject to } A x \mathrel{(\le, =, \ge)} b_0, \quad x \ge 0 .$$

The first `numle` rows are $\le$ constraints, the next `numge` are $\ge$, and
the remaining $m - m_s$ rows (with $m_s = \texttt{numle} + \texttt{numge}$) are
equalities.

## Notation

Row $i$ receives one extra variable $x_{n_0+i}$ — a *slack* ($\sigma_i = +1$),
a *surplus* ($\sigma_i = -1$), or an *artificial* ($\sigma_i = +1$) variable —
whose column is $\sigma_i e_i$. Writing $n = n_0 + m_s$, the variables
$x_0, \dots, x_{n-1}$ are the *real* ones and $x_n, \dots, x_{n_0+m-1}$ are the
artificials, which must be driven to zero.

A *basis* is an index vector $\mathcal{B} = (\mathcal{B}_1, \dots, \mathcal{B}_m)$
of $m$ variables. Its matrix $B$ has columns $A_{\cdot \mathcal{B}_i}$, and the
algorithm carries $B^{-1}$ explicitly (`bi`) together with the basic values
$x^B = B^{-1} b_0$ (`xb`). All nonbasic variables are held at $0$, so

$$x_{\mathcal{B}_i} = x^B_i, \qquad z = \sum_i c_{\mathcal{B}_i} x^B_i .$$

The initial basis is $\mathcal{B}_i = n_0 + i$ with $B^{-1} = \operatorname{diag}(\sigma)$.

## Three phases

Because surplus rows start with $x^B_i = -b_{0i} \le 0$, the method uses three
successive objectives (`Phase` in the code, `NSTEP` in the Fortran):

| phase | condition | minimize |
| --- | --- | --- |
| `NEGATIVE` | some $x^B_i \lt 0$ | $-\sum_{i : x^B_i < 0} x^B_i$ |
| `ONE` | some artificial is basic | $\sum_{i : \mathcal{B}_i \ge n} x^B_i$ |
| `TWO` | feasible | $-c^{\mathsf T} x$ |

Each phase is an ordinary simplex run; only the price vector $\pi$ changes.

## Pricing

Let $w \in \{0,1\}^m$ select the offending rows of the current phase. The prices
and *reduced costs* are

$$\pi = \begin{cases} w^{\mathsf T} B^{-1} & \text{NEGATIVE} \\ -w^{\mathsf T} B^{-1} & \text{ONE} \\ c_{\mathcal{B}}^{\mathsf T} B^{-1} & \text{TWO} \end{cases}
\qquad
r_j = \pi^{\mathsf T} A_{\cdot j} - \begin{cases} c_j & \text{TWO and } j \lt n_0 \\ 0 & \text{otherwise} \end{cases}$$

Entering $x_j$ with step $t$ moves $x^B \leftarrow x^B - t\, B^{-1} A_{\cdot j}$,
so the phase objective changes at rate $r_j$: any $j$ with $r_j \lt 0$ improves
it. Reduced costs of basic variables are exactly $0$ and are forced there.

In phase `TWO` the whole vector is recomputed only when the phase is entered
(`# 680`). Afterwards the cheap update (`# 700`) suffices: with $\rho$ the
pivot row $e_{i_p}^{\mathsf T} B^{-1}$ *after* the pivot,

$$r \leftarrow r - r_{j_p}\, \bigl(\rho^{\mathsf T} A_{\cdot j}\bigr)_j .$$

## Numerical hygiene

Three devices keep an explicit inverse usable in single precision.

**Chopping.** `chop(s, a, tol)` zeroes a sum $s$ whose accumulated magnitude
$a$ dwarfs it: $s_i \leftarrow 0$ whenever $|s_i| \lt \tfrac{\tau}{2}\,(a_i + |s_i|)$.
This is the Fortran's `DSUMP`/`DSUMN` cancellation test.

**Error estimate.** `rerr` tracks the relative error of $B^{-1}$. After each
pivot, up to `mcheck` rows are audited against the identity
$e_i^{\mathsf T} B^{-1} A_{\cdot \mathcal{B}_i} = 1$ and `rerr` absorbs the worst
deviation. When `rerr` exceeds `ACCURATE` $= 10^{-2}$ and at least
`REINVERT_AFTER` $= 5$ pivots have elapsed, the basis is reinverted.

**Refinement.** At the end of a phase one step of iterative refinement is taken:

$$\hat{x}^B = x^B + B^{-1}\bigl(b_0 - B x^B\bigr),$$

chopped against $|B^{-1}||b_0 - Bx^B| + |x^B|$ and with sign flips zeroed. A
phase is declared complete only if the *refined* values satisfy it.

## The algorithm

Uppercase names are the arrays above; $\xi$ is the transformed entering column
and $\theta$ the step length.

<pre>
<b>procedure</b> SMPLX(A, b₀, c, numle, numge, mxiter):
    <b>if</b> m &lt; 2 <b>or</b> n₀ &lt; 2 <b>or</b> mₛ &gt; m <b>or</b> min b₀ &lt; 0 <b>then return</b> INPUT_ERROR

    ℬ ← (n₀, …, n₀+m−1);  B⁻¹ ← diag(σ);  x&#7470; ← σ ⊙ b₀
    phase ← NEGATIVE;  iter ← 0;  icount ← 0;  rerr ← rerr_min

    <b>loop</b>
        <b>if</b> reinvert <b>then</b>                                    <i>⟨100⟩</i>
            rerr ← REINVERT(ℬ)
            <b>if</b> rerr &gt; ACCURATE <b>then return</b> INACCURATE     <i>⟨590⟩</i>
            icount ← 0;  phase ← NEGATIVE

        r ← PRICE(phase)                                     <i>⟨600⟩</i>
        r&#7522; ← 0 <b>for all</b> basic j

        j&#7476; ← ENTER(r, phase)                                 <i>⟨200⟩</i>
        <b>if</b> j&#7476; = <b>none then</b>                                 <i>⟨230–250⟩</i>
            <i>the phase has no improving direction</i>
            x̂ ← REFINE()
            <b>case</b> phase <b>of</b>
                NEGATIVE: <b>if</b> min x̂ ≥ −τ <b>then</b>
                              x&#7470; ← max(x̂, 0);  phase ← ONE;  <b>continue</b>
                ONE:      <b>if</b> x̂&#7522; ≤ τ <b>for all</b> artificial ℬ&#7522; <b>then</b>
                              x&#7470; ← x̂ <b>with</b> artificials zeroed
                              phase ← TWO;  <b>continue</b>
                TWO:      z ← c<sub>ℬ</sub>ᵀ x̂;  x&#7470; ← x̂
                          <b>return</b> OPTIMAL <b>or</b> POSSIBLY_OPTIMAL
            <b>if</b> icount ≥ REINVERT_AFTER <b>then</b> reinvert;  <b>continue</b>
            <b>return</b> INFEASIBLE

        <b>if</b> iter ≥ mxiter <b>then return</b> MAX_ITER              <i>⟨300⟩</i>
        iter ← iter + 1;  icount ← icount + 1
        <b>if</b> j&#7476; &lt; n₀ <b>and</b> A<sub>·j&#7476;</sub> = 0 <b>then return</b> UNBOUNDED      <i>⟨305⟩</i>

        ξ ← COLUMN(j&#7476;)
        <b>if</b> ξ = 0 <b>then</b>                                      <i>⟨350⟩</i>
            r<sub>j&#7476;</sub> ← 0;  <i>reprice without repricing</i>;  <b>continue</b>

        i&#7477; ← LEAVE(ξ, phase)                                 <i>⟨400⟩</i>
        <b>if</b> i&#7477; = <b>none then</b>                                 <i>⟨450⟩</i>
            <b>if</b> icount ≥ REINVERT_AFTER <b>then</b> reinvert;  <b>continue</b>
            <b>return</b> UNBOUNDED

        PIVOT(i&#7477;, j&#7476;)                                        <i>⟨500⟩</i>

        <b>if</b> rerr ≤ ACCURATE <b>then</b>                            <i>⟨520⟩</i>
            rerr ← max(rerr, max<sub>i ∈ S</sub> |1 − e&#7522;ᵀ B⁻¹ A<sub>·ℬ&#7522;</sub>|)
        <b>if</b> rerr &gt; ACCURATE <b>and</b> icount ≥ REINVERT_AFTER <b>then</b>
            reinvert ← <b>true</b>;  bflag ← <b>true</b>               <i>⟨530⟩</i>
</pre>

### Choosing the entering variable

The rule is Dantzig's, applied separately to the original variables and to the
slack/surplus variables; a slack is preferred only if it beats the best
original column by more than 10%. In phase `TWO` the threshold `rmin` is
$-\tau \min_{c_j \ne 0} |c_j|$ rather than $0$, so that reduced costs within
rounding noise of zero do not trigger a pivot.

<pre>
<b>procedure</b> ENTER(r, phase):                                <i>⟨200⟩</i>
    rmin ← <b>if</b> phase = TWO <b>then</b> −rtol <b>else</b> 0
    j₁ ← argmin { r&#7522; : j &lt; n₀ };  j₂ ← argmin { r&#7522; : n₀ ≤ j &lt; n }
    j&#7476; ← <b>if</b> r<sub>j₂</sub> &lt; 1.1 · min(rmin, r<sub>j₁</sub>) <b>then</b> j₂ <b>else</b> j₁
    <b>return</b> <b>if</b> r<sub>j&#7476;</sub> &lt; rmin <b>then</b> j&#7476; <b>else none</b>
</pre>

### The entering column

<pre>
<b>procedure</b> COLUMN(j&#7476;):                                    <i>⟨300⟩</i>
    <b>if</b> j&#7476; ≥ n₀ <b>then return</b> σ<sub>j&#7476;−n₀</sub> · B⁻¹<sub>·,j&#7476;−n₀</sub>
    ξ ← B⁻¹ A<sub>·j&#7476;</sub>
    <b>for</b> i <b>with</b> |ξ&#7522;| &lt; 5·10⁻³ <b>do</b>
        <b>if</b> |ξ&#7522;| &lt; τ · max<sub>k</sub>|A<sub>k,j&#7476;</sub>| · max<sub>k</sub>|B⁻¹<sub>ik</sub>| <b>then</b> ξ&#7522; ← 0
    <b>return</b> ξ
</pre>

The second test discards entries that are indistinguishable from the rounding
error of the inner product, which is what keeps the ratio test from dividing by
numerical garbage.

### The ratio test

Raising $x_{j_p}$ to $t$ drives $x^B \leftarrow x^B - t\,\xi$, so a component
with $\xi_i \gt 0$ decreases and hits $0$ at $t = x^B_i / \xi_i$.

<pre>
<b>procedure</b> LEAVE(ξ, phase):                                <i>⟨400⟩</i>
    C ← { i : ξ&#7522; &gt; 0 };  <b>if</b> phase = NEGATIVE <b>then</b> C ← C ∩ { i : x&#7470;&#7522; ≥ 0 }
    θ ← min { x&#7470;&#7522; / ξ&#7522; : i ∈ C }
    C ← { i ∈ C : x&#7470;&#7522; / ξ&#7522; = θ }

    <b>if</b> phase = NEGATIVE <b>and</b> (θ ≠ 0 <b>or</b> C = ∅) <b>then</b>      <i>⟨410, 420⟩</i>
        <i>a negative basic variable may rise to zero and leave</i>
        N ← { i : x&#7470;&#7522; &lt; 0, ξ&#7522; &lt; 0, x&#7470;&#7522;/ξ&#7522; ≤ θ }
        <b>if</b> N ≠ ∅ <b>then return</b> last argmax { x&#7470;&#7522;/ξ&#7522; : i ∈ N }
    <b>else if</b> phase = TWO <b>then</b>                             <i>⟨441⟩</i>
        <i>expel an artificial variable whenever one can be expelled</i>
        <b>if</b> ∃ i <b>with</b> ξ&#7522; &lt; 0 <b>and</b> ℬ&#7522; ≥ n <b>then return</b> first such i

    <b>return</b> <b>if</b> C ≠ ∅ <b>then</b> BREAK_TIE(C) <b>else none</b>

<b>procedure</b> BREAK_TIE(C):                                   <i>⟨460⟩</i>
    <b>if</b> ∃ i ∈ C <b>with</b> ℬ&#7522; ≥ n <b>then return</b> first such i
    <i>key&#7522; = c<sub>ℬ&#7522;</sub> for an original variable, σ·b₀ for a slack or surplus</i>
    S ← { i ∈ C : ℬ&#7522; &lt; n₀ }
    <b>if</b> S = ∅ <b>or</b> (min { key&#7522; : i ∈ S } &gt; 0 <b>and</b> C ∖ S ≠ ∅) <b>then</b> S ← C ∖ S
    <b>return</b> last argmin { key&#7522; : i ∈ S }
</pre>

An empty candidate set means the entering column can grow without limit; the
objective is unbounded — unless $B^{-1}$ has drifted, which is why the caller
reinverts first and only reports `UNBOUNDED` on the second attempt.

### The pivot

With $\theta = x^B_{i_p} / \xi_{i_p}$ and $\rho = B^{-1}_{i_p \cdot} / \xi_{i_p}$:

$$x^B \leftarrow x^B - \theta\,\xi, \quad x^B_{i_p} \leftarrow \theta, \qquad
B^{-1} \leftarrow B^{-1} - \xi\,\rho^{\mathsf T}, \quad B^{-1}_{i_p \cdot} \leftarrow \rho,$$

followed by $\mathcal{B}_{i_p} \leftarrow j_p$. Components of $x^B$ that turn
slightly negative — and were not negative before — are snapped to $0$.

### Reinversion

<pre>
<b>procedure</b> REINVERT(ℬ):                                    <i>⟨100–183⟩</i>
    <i>order ℬ so that slack/surplus/artificial indices come first</i>
    <b>let</b> iend = #{ i : ℬ&#7522; ≥ n₀ }
    <b>if</b> iend = m <b>then return</b> ∞          <i>⟨22: the basis is all unit columns⟩</i>
    B ← [ σ e&#7522; <b>for</b> the first iend columns | A<sub>·ℬ&#7522;</sub> <b>for</b> the rest ]
    <b>if</b> CROUT1(B, iend) <b>fails then return</b> ∞
    rerr ← max(rerr_min, ε · ‖B‖₁ · ‖B⁻¹‖₁)
    <b>if</b> rerr &gt; ACCURATE <b>then return</b> ∞
    x&#7470; ← chop(B⁻¹ b₀, |B⁻¹| |b₀|)
    <b>return</b> rerr
</pre>

If reinversion fails and the flag `bflag` says the last pivot is suspect, that
pivot is undone ($\mathcal{B}_{i_p}$ restored to the variable that left) and
reinversion is attempted once more (`# 580`).

### Prerequisite: `crout1`

`crout1(a, iend, index, scratch)` inverts $a$ in place and reports singularity.
It is a Crout $LU$ factorization with partial pivoting, specialized so that the
leading `iend` columns — known to hold a single $\pm 1$ — are eliminated
without arithmetic. It is a direct translation of `CROUT1` from the NSWC
Library of Mathematics Subroutines (A. H. Morris, Jr.) and is treated here as a
black box.

## Return codes

`Status` mirrors `IND` of the Fortran: `OPTIMAL`, `INFEASIBLE`, `MAX_ITER`
(default $8m$ iterations), `INACCURATE`, `UNBOUNDED`, `INPUT_ERROR`, and
`POSSIBLY_OPTIMAL` — optimality reached while `rerr` exceeded `ACCURATE`.

## References

- A. H. Morris, Jr., *NSWC Library of Mathematics Subroutines*, NSWCDD/TR-92/425.
- G. B. Dantzig, *Linear Programming and Extensions*, Princeton, 1963.
- V. Chvátal, *Linear Programming*, Freeman, 1983 — chapters 7 (revised simplex)
  and 3 (anti-cycling tie-break rules).
