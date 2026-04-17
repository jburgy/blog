# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "numpy>=2.4.3",
# ]
# ///

# ruff: noqa: E501, E741, F821, F841

import numpy as np
from numpy import typing as npt

Matrix = np.ndarray[tuple[int, int], np.dtype[np.float64]]
Vector = np.ndarray[tuple[int], np.dtype[np.float64]]
Mask = np.ndarray[tuple[int], np.dtype[np.bool_]]
Index = np.ndarray[tuple[int], np.dtype[np.int64]]


def reorder_basis(
    a: Matrix,
    b0: Vector,
    numle: int,
    bi: Matrix,
    xb: Vector,
    basis: Mask,
    ibasis: Index,
    rerr_mn: float,
    eps0: float,
    jp: np.int64,
    iout: int,
    attempts: int = 2,
) -> bool:  # 100-200
    m, n0 = a.shape
    for _ in range(attempts):
        where = ibasis < n0
        np.concatenate((ibasis[~where], ibasis[where][::-1]), out=ibasis)
        iend = m - where.sum()
        # FIXME: bailout if where.all()
        bi.fill(0.0)
        bi[:, iend:] = a[:, ibasis[iend:]]
        np.fill_diagonal(
            bi[:iend, :iend], np.where(ibasis[:iend] < n0 + numle, 1.0, -1.0)
        )
        if crout1(bi, iend):
            return True
        bnorm = np.amax(np.sum(abs(a[:, ibasis[iend:]]), axis=0), initial=0.0)
        binorm = np.amax(np.sum(abs(bi), axis=0))
        rerr = max(rerr_mn, eps0 * bnorm * binorm)
        if rerr <= 1e-2:
            break
        # 580
        ip = np.argmax(ibasis == jp)
        ibasis[ip] = iout
        basis[jp] = False
        basis[iout] = True
    else:
        return True
    np.matvec(bi, b0, out=xb)  # FIXME: zero out small values
    return False


def refine_result(
    a: Matrix,
    b0: Vector,
    numle: int,
    numge: int,
    bi: Matrix,
    xb: Vector,
    y: Vector,
    r: Vector,
    ibasis: Index,
    rerr_mx: float,
    rerr: np.float64,
):  # 800
    m, n0 = a.shape
    n = (ns := n0 + numle) + numge
    y[:m] = 0.0
    where = (n0 <= ibasis) & (ibasis < ns)
    np.put(y, ibasis[where] - n0, xb[where])
    where = (ns <= ibasis) & (ibasis < n)
    np.put(y, ibasis[where] - n0, -xb[where])
    where = ibasis < n0
    if np.any(where):
        np.subtract(b0, y + a[:, ibasis[where]] @ xb[where], out=r[:m])
    else:
        np.subtract(b0, y, out=r[:m])

    rerr1 = min(rerr_mx, rerr)
    t = np.empty(m)
    for i, xi in enumerate(xb):
        np.multiply(bi[i, :], r[:m], out=t)
        sump = t.sum(where=t > 0.0, initial=max(xi, 0.0))
        sumn = t.sum(where=t < 0.0, initial=min(xi, 0.0))
        w = sump + sumn
        if w == 0 or np.sign(xi) != np.sign(w):
            continue
        y[i] = w if abs(xi) > rerr1 * max(sump, -sumn) else 0.0
    np.copyto(dst=xb, src=y)


def smplx(
    a: np.ndarray[tuple[int, int], np.dtype[np.float64]],
    b0: npt.ArrayLike,
    c: npt.ArrayLike,
    mxiter: int = 1000,
    numle: int = 0,
    numge: int = 0,
) -> tuple[int, np.ndarray[tuple[int], np.dtype[np.float64]], float, int]:
    """
    Solve linear program:
        maximize c^T x
        subject to a x (<=, =, >=) b0, x >= 0.
    Constraints: first numle are <=, next numge are >=, rest are =.
    """
    # Infer dimensions
    m, n0 = a.shape
    mcheck = min(5, m // 15 + 1)
    b0 = np.asarray(b0, dtype=np.float64).ravel()
    c = np.asarray(c, dtype=np.float64).ravel()
    ms = numle + numge
    # Validate input
    if m < 2 or n0 < 2 or ms > m or a.shape[0] < m or np.any(b0 < 0):
        return 5, np.empty(0, dtype=np.float64), float("nan"), 0

    # Machine constants
    finfo = np.finfo(np.float64)
    eps0 = np.ldexp(1.0, -23)
    assert isinstance(eps0, np.float64)
    rerr_mn = 10.0 * eps0
    rerr_mx = 1e-4 if eps0 >= 1e-13 else 1e-5
    xmax = finfo.max
    rtol = rerr_mx * abs(c).min(initial=xmax, where=c != 0)

    # Work arrays
    n = (ns := n0 + numle) + numge
    r = np.zeros(n, dtype=np.float64)  # solution and reduced costs
    bi = np.eye(m, dtype=np.float64)  # basis inverse
    xb = b0.copy()  # basic variable values
    y = np.zeros(m, dtype=np.float64)  # work array
    ratios = np.empty(m, dtype=np.float64)  # ratios for determining leaving variable
    basis = np.zeros(n0 + m, dtype=bool)  # 1 if variable is basic

    # 30-42 Initial basis (slack variables)
    ibasis = np.arange(n0, n0 + m)
    # Mark basic variables
    basis[ibasis] = True

    # Adjust for >= constraints
    xb[numle:ms] = -xb[numle:ms]
    np.fill_diagonal(bi[numle:ms, numle:ms], -1.0)

    # Main algorithm
    nstep = 1
    iter_count = icount = 0
    rerr = rerr_mn
    ind = 0
    setup = False

    while True:
        # Set up the r array
        if nstep == 1:  # 601 for the nstep = 1 case
            where = xb < 0
            if not np.any(where):
                nstep = 2
                continue
            y.fill(0.0)
            bi.sum(axis=0, where=where, out=y)
            # 650
            np.vecmat(y, a, out=r[:n0])
            # 660
            r[n0:ns] = y[:numle]
            r[ns:] = -y[numle : numle + numge]
        elif nstep == 2:  # 630 for the nstep = 2 case
            # num ≔ n + np.count_nonzero(ibasis >= n)
            # num ≡ n ⇒ np.all(ibasis < n)
            if np.all(ibasis < n) or setup:  # 680
                setup = False
                nstep = 3
                where = ibasis < n0
                np.vecmat(c[ibasis[where]], bi[where, :], out=y)
                np.vecmat(y, a, out=r[:n0])
                np.subtract(r[:n0], c, out=r[:n0])
                np.putmask(
                    r[:n0],
                    mask=(r[:n0] < 0) & (abs(r[:n0]) < rerr_mx * abs(c[:n0])),
                    values=0.0,
                )
            else:
                where = ibasis >= n
                y.fill(0.0)
                bi.sum(axis=0, where=where, out=y)
                np.negative(y, out=y)
                # 650
                np.vecmat(y, a, out=r[:n0])
            # 660
            r[n0:ns] = y[:numle]
            r[ns:] = -y[numle : numle + numge]
        else:  # 700 for the nstep = 3 case
            const = r[jp]
            np.subtract(r[:n0], const * np.vecmat(bi[ip, :], a), out=r[:n0])
            np.putmask(
                r[:n0],
                mask=(r[:n0] < 0.0) & (abs(r[:n0]) < rerr_mx * abs(c[:n0])),
                values=0.0,
            )
            np.subtract(r[n0:ns], const * bi[ip, :numle], out=r[n0:ns])
            np.add(r[ns:], const * bi[ip, numle:], out=r[ns:])
        np.putmask(r, mask=basis, values=0.0)

        # Find the next vector a[:, jp] to be inserted into the basis
        # 200
        rmin = -rtol if nstep == 3 else 0.0
        rm = np.ma.array(r, mask=basis | (r >= rmin), fill_value=rmin)
        rm.mask[n0:] = (  # ty: ignore[invalid-assignment]
            basis[n0:] | (r[n0:] >= min(r[:n0]) * 1.1)
        )
        if rm.all() is np.ma.masked:
            if nstep == 2 and np.all((ibasis >= n) & (xb <= 0)):
                setup = True
                continue  # GO TO 680
            elif nstep == 3:
                ind = 0 if rerr <= 1e-2 else 6
            # Refine xb and store the result in y
            refine_result(a, b0, numle, numge, bi, xb, y, r, ibasis, rerr_mx, rerr)
            if nstep == 1:  # 860 Check the refinement (nstep = 1)
                if np.all(y >= -rerr_mx):
                    np.clip(y, a_min=0.0, a_max=None, out=xb[:m])
                    nstep = 2
                    continue
            elif nstep == 2:  # 870 Check the refinement (nstep = 2)
                if np.all((ibasis >= n) | (xb <= rerr_mx)):
                    np.clip(y, a_min=0.0, a_max=None, out=xb[:m])
                    setup = True
                    continue
            else:  # 880 Compute z (nstep =3)
                where = ibasis < n0
                z = y[where].dot(c[ibasis[where]])
                np.copyto(dst=xb[:m], src=y)
                break
            if icount >= 5:
                if reorder_basis(
                    a, b0, numle, bi, xb, basis, ibasis, rerr_mn, eps0, jp, iout
                ):
                    break
                continue
        else:
            jp = rm.argmin()

        # If mxiter iterations have not been performed then
        # begin the next iteration.  Compute the jp-th column
        # of bi @ a and store it in y.
        if iter_count >= mxiter:
            ind = 2
            break

        if jp < n0:
            amax = np.amax(abs(a[:, jp]))
            if amax == 0.0:
                ind = 4
                break
            np.matvec(bi, a[:, jp], out=y)
            np.putmask(
                y, mask=abs(y) < rerr_mx * amax * np.amax(abs(bi), axis=1), values=0.0
            )
        elif jp < ns:
            np.take(bi, jp - n0, axis=1, out=y)
        else:
            np.take(bi, jp - n0, axis=1, out=y)
            np.negative(y, out=y)

        if np.any(y):
            iter_count += 1
            icount += 1
        else:
            r[jp] = 0.0
            continue

        with np.errstate(divide="ignore", invalid="ignore"):
            np.divide(xb, y, out=ratios)
        # Finding the variable xb[ip] to be made nonbasic
        where = (
            (xb >= 0.0) | (y > 0.0)
            if nstep == 1  # for the nstep = 1 case
            else y > 0.0
            if nstep == 2  # for the nstep = 2 case
            # for the nstep == 3 case
            else ((y < 0.0) & (ibasis >= n)) | (y > 0.0)
        )
        epsi = (
            ratios.max(where=(xb < 0.0) & (y < 0.0), initial=0.0)
            if nstep == 1 and not np.any(where)
            else ratios.min(where=where, initial=xmax)
        )
        where = ratios == epsi

        if not np.any(where):
            if icount >= 5:
                if reorder_basis(
                    a, b0, numle, bi, xb, basis, ibasis, rerr_mn, eps0, jp, iout
                ):
                    break
                continue
            ind = 4
            break

        # Tie breaking procedure
        ip = (
            np.r_[c, b0[:numle], -b0[numle:]].take(ibasis[where]).argmin()
            if np.count_nonzero(where) > 1
            else where.argmax()
        )

        # Transformation of xb
        const = xb[ip] / y[ip]
        xb -= const * y
        xb[ip] = const

        # Transformation of bi
        const = bi[ip, :] / y[ip]
        where = bi[ip, :] != 0.0
        np.subtract(bi, np.outer(y, const), bi, where=where)
        bi[ip, where] = const[where]

        # Updating ibasis and basis
        iout = ibasis[ip]
        ibasis[ip] = jp
        basis[iout] = False
        basis[jp] = True

        # Check the accuracy of bi and reset rerr
        if rerr <= 1e-2:
            for j, k in enumerate(ibasis[ibasis < n0][:mcheck]):
                sum = np.dot(bi[j, :], a[:, k])
                rerr = max(rerr, abs(1.0 - sum))
            if rerr <= 1e-2:
                continue  # GO TO 600
        # The accuracy criteria are not satisfied
        if icount >= 5:
            if reorder_basis(
                a, b0, numle, bi, xb, basis, ibasis, rerr_mn, eps0, jp, iout
            ):
                break

    # 220 Insert the values of the original, slack, and surplus
    # variables into r.  Then terminate
    r.fill(0.0)
    r[ibasis] = xb
    return ind, r, z, iter_count


def crout1(a: Matrix, iend: int) -> bool:
    """
    Crout procedure for inverting a matrix in place.

    Parameters
    ----------
    a : numpy.ndarray, shape (N, N)
        Input matrix. On output, contains the inverse if successful.
    iend : int
        Number of leading columns that contain exactly one nonzero element,
        which is either 1 or -1 (assumed).

    Returns
    -------
    ierr : bool
        False if successful, True if matrix is singular.
    """
    a = a.astype(np.float64, copy=False)
    n, _ = a.shape
    index = np.zeros(n - 1, dtype=int)  # row interchange records (0‑based)
    temp = np.zeros(n)

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
            a[j, iend:] = -a[j, iend:]  # flip sign of entire row j
        index[k] = j
        if j != k:
            # Swap rows k and j for columns k .. n-1
            a[[k, j], iend:] = a[  # ty:ignore[invalid-argument-type]
                [j, k], iend:
            ]  # ty:ignore[invalid-assignment]

    # ------------------------------------------------------------------
    # LU decomposition (Crout with partial pivoting) for the remaining part
    # ------------------------------------------------------------------
    pmin = 0.0
    for k in range(iend, n - 1):
        # Pivot search in column k, rows k..n-1
        abs_col = np.abs(a[k:, k])
        max_loc = np.argmax(abs_col)
        j = k + max_loc
        s = abs_col[max_loc]
        if k > iend and s >= pmin:
            pass
        elif (pmin := s) == 0.0:
            return True
        index[k] = j
        if j != k:
            # Swap rows k and j for columns iend .. n-1
            a[[k, j], iend:] = a[  # ty:ignore[invalid-argument-type]
                [j, k], iend:
            ]  # ty:ignore[invalid-assignment]

        kp1 = k + 1
        ik = slice(iend, k)
        # Compute k‑th row of U (columns > k)
        a[k, kp1:] -= np.vecmat(a[ik, k], a[ik, kp1:])
        a[k, kp1:] /= a[k, k]
        # Compute k‑th column of L (rows > k)
        a[kp1:, k] -= np.matvec(a[kp1:, ik], a[k, ik])

    # Check the last pivot
    nm1 = n - 1
    last_pivot = a[nm1, nm1]
    if abs(last_pivot) > pmin:
        pass
    elif last_pivot == 0.0:
        return True

    # ------------------------------------------------------------------
    # Replace L (lower triangular) with its inverse
    # ------------------------------------------------------------------
    for j in range(iend, nm1):
        temp[j] = a[j, j] = 1.0 / a[j, j]
        for k in range(j + 1, n):
            a[k, j] = -np.dot(a[k, j:k], temp[j:k]) / a[k, k]
            temp[k] = a[k, j]
    a[nm1, nm1] = 1.0 / a[nm1, nm1]

    if n == 1:
        return False

    # ------------------------------------------------------------------
    # Solve U * X = inv(L)   (U is unit upper triangular)
    # ------------------------------------------------------------------
    for k in range(nm1, -1, -1):
        lmin = max(iend, k + 1)
        if lmin < n:
            temp[lmin:] = a[k, lmin:]
            a[k, lmin:] = 0.0
            a[k, iend:] -= np.vecmat(temp[lmin:], a[lmin:, iend:])

    # ------------------------------------------------------------------
    # Apply column interchanges (inverse of row interchanges)
    # ------------------------------------------------------------------
    for j in range(nm1 - 1, -1, -1):
        k = index[j]
        if j != k:
            a[:, [j, k]] = a[:, [k, j]]

    return False


# Overwrite above definition with a fast FORTRAN implementation
try:
    from _simplex import smplx  # ty: ignore[unresolved-import]
except ImportError:
    pass

