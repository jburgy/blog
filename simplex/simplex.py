# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy>=2.4.3",
# ]
# ///

from enum import IntEnum

import numpy as np
from numpy import typing as npt

Matrix = np.ndarray[tuple[int, int], np.dtype[np.float64]]
Vector = np.ndarray[tuple[int], np.dtype[np.float64]]
Index = np.ndarray[tuple[int], np.dtype[np.intp]]

ACCURATE = 1e-2  # largest acceptable estimated relative error of bi
REINVERT_AFTER = 5  # pivots since the last reinversion before another is tried


class Status(IntEnum):
    """IND on return from SMPLX."""

    OPTIMAL = 0
    INFEASIBLE = 1
    MAX_ITER = 2
    INACCURATE = 3
    UNBOUNDED = 4
    INPUT_ERROR = 5
    POSSIBLY_OPTIMAL = 6


class Phase(IntEnum):
    """NSTEP in SMPLX1."""

    NEGATIVE = 1  # eliminate negative basic variables
    ONE = 2  # drive artificial variables to zero
    TWO = 3  # maximize c^T x


def chop(s: Vector, a: Vector, tol: float) -> None:
    """Zero s = sump + sumn where |s| < tol * max(sump, -sumn); a = sump - sumn."""
    a += abs(s)  # 2 * max(sump, -sumn)
    a *= 0.5 * tol
    np.putmask(s, abs(s) < a, 0.0)


def smplx_py(
    a: Matrix,
    b0: npt.ArrayLike,
    c: npt.ArrayLike,
    mxiter: int | None = None,
    numle: int = 0,
    numge: int = 0,
) -> tuple[Status, Vector, float, int]:
    """
    Solve linear program:
        maximize c^T x
        subject to a x (<=, =, >=) b0, x >= 0.
    Constraints: first numle are <=, next numge are >=, rest are =.
    mxiter defaults to 8 * len(b0), as in the f2py wrapper.
    Returns (status, x, z, iterations); x holds original, slack and surplus values.
    """
    m, n0 = a.shape
    if mxiter is None:
        mxiter = 8 * m
    b0 = np.asarray(b0, dtype=np.float64).ravel()
    c = np.asarray(c, dtype=np.float64).ravel()
    ms = numle + numge
    if m < 2 or n0 < 2 or ms > m or np.any(b0 < 0):
        return Status.INPUT_ERROR, np.empty(0), float("nan"), 0

    # Single precision machine constants, as in SPMPAR
    eps0 = 2.0**-23
    rerr_mn = 10.0 * eps0
    rerr_mx = 1e-4
    xmax = np.finfo(np.float64).max
    rtol = rerr_mx * abs(c).min(initial=xmax, where=c != 0)
    mcheck = min(5, m // 15 + 1)

    # Variable n0 + i is the slack (+1), surplus (-1) or artificial (+1) variable
    # of constraint i, so its column is sgn[i] * e_i.
    n = n0 + ms  # original, slack and surplus variables
    sgn = np.ones(m)
    sgn[numle:ms] = -1.0
    cc = np.r_[c, np.zeros(m)]
    tie = np.r_[c, sgn * b0]  # tie-breaking keys
    ctol = -rerr_mx * abs(c)  # reduced costs in (ctol, 0) are rounded to 0
    a_absmax = abs(a).max(axis=0)
    a_abssum = abs(a).sum(axis=0)

    # Basis, initially the slack, surplus and artificial variables
    ibasis = np.arange(n0, n0 + m)
    basis = np.zeros(n0 + m, dtype=bool)
    basis[ibasis] = True
    bi = np.diag(sgn)  # basis inverse
    xb = sgn * b0  # basic variable values
    r = np.zeros(n)  # reduced costs

    # Scratch
    w = np.empty(m)  # row weights
    pi = np.empty(m)  # prices
    col = np.empty(m)  # bi @ entering column
    ratios = np.empty(m)
    xnew = np.empty(m)
    xr = np.empty(m)  # refined xb
    rowv = np.empty(m)
    absum = np.empty(m)  # sums of absolute values for chop
    res = np.empty(m)  # residual b0 - B @ xb
    xfull = np.empty(n0 + m)
    dr = np.empty(n)
    M = np.empty((m, m))
    index = np.empty(m - 1, dtype=np.intp)

    def times_columns(v: Vector, out: Vector) -> Vector:
        """650-670: out[j] = v @ column j, for original, slack and surplus j."""
        np.vecmat(v, a, out=out[:n0])
        np.multiply(v[:ms], sgn[:ms], out=out[n0:])
        return out

    def entering(rmin: float) -> int | None:
        """200: most negative reduced cost below rmin, slacks only if 10% lower."""
        j1 = r[:n0].argmin()
        j2 = n0 + r[n0:].argmin() if n > n0 else j1
        jp = j2 if r[j2] < 1.1 * min(rmin, r[j1]) else j1
        return int(jp) if r[jp] < rmin else None  # basic r are 0 and rmin <= 0

    def entering_column(jp: int) -> None:
        """300-331: col = bi @ column jp, with negligible entries zeroed."""
        if jp >= n0:
            np.multiply(bi[:, jp - n0], sgn[jp - n0], out=col)
            return
        np.matvec(bi, a[:, jp], out=col)
        small = np.flatnonzero(abs(col) < 5e-3)
        tol = rerr_mx * a_absmax[jp] * abs(bi[small]).max(axis=1, initial=0.0)
        col[small[abs(col[small]) < tol]] = 0.0

    def leaving(phase: Phase) -> int | None:
        """400-464: row of the leaving basic variable, None if there is none."""
        with np.errstate(divide="ignore", invalid="ignore"):
            np.divide(xb, col, out=ratios)
        cand = (xb >= 0.0) & (col > 0.0) if phase == Phase.NEGATIVE else col > 0.0
        epsi = ratios.min(where=cand, initial=xmax)
        cand &= ratios == epsi
        if phase == Phase.NEGATIVE and (epsi != 0.0 or not cand.any()):  # 410, 420
            neg = (xb < 0.0) & (col < 0.0) & (ratios <= epsi)
            neg &= ratios == ratios.max(where=neg, initial=0.0)
            if neg.any():
                return int(np.flatnonzero(neg)[-1])
        elif phase == Phase.TWO and (art := (col < 0.0) & (ibasis >= n)).any():  # 441
            return int(art.argmax())
        return tie_break(np.flatnonzero(cand)) if cand.any() else None

    def tie_break(rows: Index) -> int:
        """460: first artificial, else least c if <= 0 or no slack, else least ±b0."""
        k = ibasis[rows]
        if np.any(k >= n):
            return int(rows[np.argmax(k >= n)])
        key = tie.take(k)
        sel = k < n0
        if key.min(where=sel, initial=xmax) > 0.0 and not sel.all():
            sel = ~sel
        return int(rows[sel & (key == key.min(where=sel, initial=xmax))][-1])

    def pivot(ip: int, jp: int) -> int:
        """500-512: replace basic variable ip by jp; return the leaving variable."""
        const = xb[ip] / col[ip]
        t = np.subtract(xb, np.multiply(col, const, out=xnew), out=xnew)
        np.putmask(t, (t < 0.0) & ((xb >= 0.0) | (t >= rerr_mx * xb)), 0.0)
        np.copyto(xb, t)
        xb[ip] = const
        np.divide(bi[ip], col[ip], out=rowv)
        np.subtract(bi, np.multiply.outer(col, rowv, out=M), out=bi)
        bi[ip] = rowv
        iout = int(ibasis[ip])
        ibasis[ip] = jp
        basis[iout] = False
        basis[jp] = True
        return iout

    def refine(tol: float) -> Vector:
        """800-856: one step of iterative refinement of xb."""
        xfull.fill(0.0)
        xfull[ibasis] = xb
        np.matvec(a, xfull[:n0], out=res)
        np.add(res, np.multiply(sgn, xfull[n0:], out=absum), out=res)
        np.subtract(b0, res, out=res)
        np.add(np.matvec(bi, res, out=xr), xb, out=xr)
        np.matvec(np.abs(bi, out=M), np.abs(res, out=res), out=absum)
        np.add(absum, abs(xb), out=absum)
        chop(xr, absum, tol)
        np.putmask(xr, np.sign(xr) != np.sign(xb), 0.0)
        return xr

    def reinvert_basis(undo: tuple[int, int] | None) -> float:
        """100-183, 580: reinvert bi and recompute xb; return rerr, or inf on failure.

        On failure, undo the pivot (jp, iout) if given and try once more.
        """
        while True:
            orig = ibasis < n0
            np.concatenate((ibasis[~orig], ibasis[orig][::-1]), out=ibasis)
            iend = m - orig.sum()
            if iend == m:  # 22
                return np.inf
            k = ibasis[:iend] - n0
            bi.fill(0.0)
            bi[k, np.arange(iend)] = sgn[k]
            np.take(a, ibasis[iend:], axis=1, out=bi[:, iend:], mode="clip")
            bnorm = max(a_abssum[ibasis[iend:]].max(), 1.0 if iend else 0.0)
            if not crout1(bi, iend, index, M):
                binorm = np.sum(np.abs(bi, out=M), axis=0, out=absum).max()
                rerr = max(rerr_mn, eps0 * bnorm * binorm)
                if rerr <= ACCURATE:  # 183
                    np.matvec(bi, b0, out=xb)
                    chop(xb, np.matvec(np.abs(bi, out=M), b0, out=absum), rerr_mx)
                    return rerr
            if undo is None:  # 580
                return np.inf
            jp, iout = undo
            undo = None
            ibasis[ibasis == jp] = iout
            basis[jp] = False
            basis[iout] = True

    # Main algorithm
    phase = Phase.NEGATIVE
    status = Status.OPTIMAL
    iter_count = icount = 0  # iterations, in total and since the last reinversion
    rerr = rerr_mn  # estimated relative error of bi
    z = 0.0
    jp = ip = iout = 0  # entering column, pivot row and leaving variable
    full = reprice = reinvert = bflag = False

    while True:
        if reinvert:  # 100
            reinvert = False
            rerr = reinvert_basis((jp, iout) if bflag else None)
            if rerr > ACCURATE:  # 590
                status = Status.INACCURATE
                break
            bflag = False
            icount = 0
            phase = Phase.NEGATIVE

        # 600 Set up the reduced costs r
        if reprice:  # 350 GO TO 200
            reprice = False
        elif phase == Phase.TWO:
            if full:  # 680
                full = False
                np.vecmat(cc[ibasis], bi, out=pi)
                times_columns(pi, r)
                r[:n0] -= c
            else:  # 700
                times_columns(bi[ip], dr)
                dr *= r[jp]
                r -= dr
            np.maximum(r[:n0], 0.0, out=r[:n0], where=r[:n0] > ctol)
        else:  # 601-643 minimize the sum of negative, then artificial, variables
            rows = xb < 0 if phase == Phase.NEGATIVE else ibasis >= n
            if phase == Phase.NEGATIVE and not rows.any():
                phase, rows = Phase.ONE, ibasis >= n
            if phase == Phase.ONE and not rows.any():
                phase, full = Phase.TWO, True
                continue
            np.copyto(w, rows)
            np.vecmat(w, bi, out=pi)
            chop(pi, np.vecmat(w, np.abs(bi, out=M), out=absum), rerr_mx)
            if phase == Phase.ONE:
                np.negative(pi, out=pi)
            times_columns(pi, r)
        np.putmask(r, mask=basis[:n], values=0.0)

        # 200 Choose the entering variable
        j = entering(-rtol if phase == Phase.TWO else 0.0)
        if j is None:  # the current phase is complete
            if phase == Phase.ONE and np.all((ibasis < n) | (xb <= 0)):  # 230
                phase, full = Phase.TWO, True
                continue
            if phase == Phase.TWO:  # 250
                if rerr > ACCURATE and icount >= REINVERT_AFTER:
                    reinvert = True
                    continue
                accurate = rerr <= ACCURATE
                status = Status.OPTIMAL if accurate else Status.POSSIBLY_OPTIMAL
            xr = refine(min(rerr_mx, rerr))
            if phase == Phase.NEGATIVE:  # 860
                if np.all(xr >= -rerr_mx):
                    np.clip(xr, a_min=0.0, a_max=None, out=xb)
                    phase = Phase.ONE
                    continue
            elif phase == Phase.ONE:  # 870
                art = ibasis >= n
                if np.all(xr[art] <= rerr_mx):
                    xr[art] = 0.0
                    np.copyto(dst=xb, src=xr)
                    phase, full = Phase.TWO, True
                    continue
            else:  # 880
                z = float(cc[ibasis] @ xr)
                np.copyto(dst=xb, src=xr)
                break
            if icount >= REINVERT_AFTER:  # 240
                reinvert = True
                continue
            status = Status.INFEASIBLE
            break
        jp = j

        # 300 Compute the entering column
        if iter_count >= mxiter:
            status = Status.MAX_ITER
            break
        iter_count += 1
        icount += 1
        if jp < n0 and a_absmax[jp] == 0.0:  # 305
            status = Status.UNBOUNDED
            break
        entering_column(jp)
        if not col.any():  # 350
            iter_count -= 1
            icount -= 1
            r[jp] = 0.0
            reprice = True
            continue

        # 400 Choose the leaving variable and pivot
        i = leaving(phase)
        if i is None:  # 450
            if icount >= REINVERT_AFTER:
                reinvert = True
                continue
            status = Status.UNBOUNDED
            break
        ip = i
        iout = pivot(ip, jp)

        # 520 Check the accuracy of bi
        if rerr <= ACCURATE:
            rows = np.flatnonzero(ibasis < n0)[:mcheck]
            diag = np.vecdot(bi[rows], a[:, ibasis[rows]].T)  # ≈ 1
            rerr = max(rerr, abs(1.0 - diag).max(initial=0.0))
        if rerr > ACCURATE and icount >= REINVERT_AFTER:  # 530
            reinvert = bflag = True

    # 220 Return the original, slack and surplus variables
    x = np.zeros(n)
    keep = ibasis < n
    x[ibasis[keep]] = xb[keep]
    return status, x, z, iter_count


def crout1(a: Matrix, iend: int, index: Index, scratch: Matrix) -> bool:
    """
    Crout procedure for inverting a matrix in place.

    Parameters
    ----------
    a : numpy.ndarray, shape (N, N)
        Input matrix. On output, contains the inverse if successful.
    iend : int
        Number of leading columns that contain exactly one nonzero element,
        which is either 1 or -1 (assumed).
    index : numpy.ndarray, shape (N - 1,)
        Integer scratch for row interchange records (0‑based).
    scratch : numpy.ndarray, shape (N, N)
        Float scratch.

    Returns
    -------
    ierr : bool
        False if successful, True if matrix is singular.
    """
    n, _ = a.shape
    if n == 1:
        if a[0, 0] == 0.0:
            return True
        a[0, 0] = 1.0 / a[0, 0]
        return False
    temp, work = scratch[0], scratch[1]

    # ------------------------------------------------------------------
    # Process the first iend columns
    # ------------------------------------------------------------------
    for k in range(iend):
        col_k = a[k:, k]
        j = np.argmax(col_k != 0.0)
        if col_k[j] == 0.0:
            return True
        j += k
        if a[j, k] < 0:
            np.negative(a[j, iend:], out=a[j, iend:])  # flip sign of entire row j
        index[k] = j
        if j != k:
            # Swap rows k and j for columns k .. n-1
            temp[k:] = a[k, k:]
            a[k, k:] = a[j, k:]
            a[j, k:] = temp[k:]

    # ------------------------------------------------------------------
    # LU decomposition (Crout with partial pivoting) for the remaining part
    # ------------------------------------------------------------------
    for k in range(iend, n - 1):
        # Pivot search in column k, rows k..n-1
        abs_col = np.abs(a[k:, k], out=temp[k:])
        max_loc = np.argmax(abs_col)
        j = k + max_loc
        if abs_col[max_loc] == 0.0:
            return True
        index[k] = j
        if j != k:
            # Swap rows k and j for columns iend .. n-1
            temp[iend:] = a[k, iend:]
            a[k, iend:] = a[j, iend:]
            a[j, iend:] = temp[iend:]

        kp1 = k + 1
        ik = slice(iend, k)
        # Compute k‑th row of U (columns > k)
        a[k, kp1:] -= np.vecmat(a[k, ik], a[ik, kp1:], out=work[kp1:])
        a[k, kp1:] /= a[k, k]
        # Compute (k+1)‑th column of L (rows > k)
        ik = slice(iend, kp1)
        a[kp1:, kp1] -= np.matvec(a[kp1:, ik], a[ik, kp1], out=work[kp1:])

    # Check the last pivot
    nm1 = n - 1
    if a[nm1, nm1] == 0.0:
        return True

    # ------------------------------------------------------------------
    # Replace L (lower triangular) with its inverse, one row at a time
    # ------------------------------------------------------------------
    linv = scratch[: n - iend, : n - iend]  # temp and work are unused meanwhile
    linv.fill(0.0)
    for k in range(n - iend):
        kk = iend + k
        np.vecmat(a[kk, iend:kk], linv[:k, :k], out=linv[k, :k])
        linv[k, :k] /= -a[kk, kk]
        linv[k, k] = 1.0 / a[kk, kk]
        a[kk, iend : kk + 1] = linv[k, : k + 1]

    # ------------------------------------------------------------------
    # Solve U * X = inv(L)   (U is unit upper triangular)
    # ------------------------------------------------------------------
    for k in range(nm1 - 1, -1, -1):
        lmin = max(iend, k + 1)
        temp[lmin:] = a[k, lmin:]
        a[k, lmin:] = 0.0
        a[k, iend:] -= np.vecmat(temp[lmin:], a[lmin:, iend:], out=work[iend:])

    # ------------------------------------------------------------------
    # Apply column interchanges (inverse of row interchanges)
    # ------------------------------------------------------------------
    for j in range(nm1 - 1, -1, -1):
        k = index[j]
        if j != k:
            temp[:] = a[:, j]
            a[:, j] = a[:, k]
            a[:, k] = temp

    return False


try:  # the Fortran SMPLX is much faster on small problems
    from _simplex import smplx  # ty: ignore[unresolved-import]
except ImportError:
    smplx = smplx_py
