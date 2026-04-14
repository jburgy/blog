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
    b: npt.ArrayLike,
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
    b0 = np.asarray(b, dtype=np.float64).ravel()
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
            where = np.reshape(xb < 0, (1, -1))
            if not np.any(where):
                nstep = 2
                continue
            sumn = bi.sum(axis=0, where=where & (bi < 0.0))
            sump = bi.sum(axis=0, where=where & (bi > 0.0))
            y.fill(0.0)
            np.add(sumn, sump, out=y, where=where[0, :])
            np.putmask(y, mask=abs(y) < rerr_mx * np.maximum(sumn, -sump), values=0.0)
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
                mask = np.reshape(ibasis >= n, (1, -1))
                sumn = bi.sum(axis=0, where=mask & (bi < 0.0))
                sump = bi.sum(axis=0, where=mask & (bi > 0.0))
                y.fill(0.0)
                np.add(sumn, sump, out=y, where=mask[0, :])
                np.negative(y, out=y)
                np.putmask(
                    y, mask=abs(y) < rerr_mx * np.maximum(sumn, -sump), values=0.0
                )
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
        L = j + k  # absolute row index (0‑based)
        if a[L, k] < 0:
            a[L, iend:] = -a[L, iend:]  # flip sign of entire row L
        index[k] = L
        if L != k:
            # Swap rows k and L for columns k .. n-1
            a[[k, L], iend:] = a[  # ty:ignore[invalid-argument-type]
                [L, k], iend:
            ]  # ty:ignore[invalid-assignment]

    # ------------------------------------------------------------------
    # LU decomposition (Crout with partial pivoting) for the remaining part
    # ------------------------------------------------------------------
    pmin = 0.0
    for k in range(iend, n - 1):
        # Pivot search in column k, rows k..n-1
        col_k = a[k:, k]
        abs_col = np.abs(col_k)
        max_loc = np.argmax(abs_col)
        L = k + max_loc
        s = abs_col[max_loc]
        if k > iend and s >= pmin:
            pass
        elif (pmin := s) == 0.0:
            return True
        index[k] = L
        if L != k:
            # Swap rows k and L for columns iend .. n-1
            a[[k, L], iend:] = a[  # ty:ignore[invalid-argument-type]
                [L, k], iend:
            ]  # ty:ignore[invalid-assignment]

        # Compute k‑th row of U (columns > k)
        if k == iend:
            if k + 1 < n:
                a[k, k + 1 :] = a[k, k + 1 :] / a[k, k]
        else:
            # Store column k of L (rows iend..k-1) in temp
            temp[iend:k] = a[iend:k, k]
            L_col = a[iend:k, k]
            U_block = a[iend:k, k + 1 :]
            sums = L_col @ U_block
            a[k, k + 1 :] = (a[k, k + 1 :] - sums) / a[k, k]

        # Compute k‑th column of L (rows > k)
        if k + 1 < n:
            # Store row k of U (columns iend..k-1) in temp
            temp[iend:k] = a[k, iend:k]
            sums = a[k + 1 :, iend:k] @ temp[iend:k]
            a[k + 1 :, k] = a[k + 1 :, k] - sums

    # Check the last pivot
    last_pivot = a[n - 1, n - 1]
    if abs(last_pivot) > pmin:
        pass
    elif last_pivot == 0.0:
        return True

    # ------------------------------------------------------------------
    # Replace L (lower triangular) with its inverse
    # ------------------------------------------------------------------
    for j in range(iend, n - 1):
        a[j, j] = 1.0 / a[j, j]
        temp[j] = a[j, j]
        for k in range(j + 1, n):
            sum_val = np.dot(a[k, j:k], temp[j:k])
            a[k, j] = -sum_val / a[k, k]
            temp[k] = a[k, j]
    a[n - 1, n - 1] = 1.0 / a[n - 1, n - 1]

    if n == 1:
        return False

    # ------------------------------------------------------------------
    # Solve U * X = inv(L)   (U is unit upper triangular)
    # ------------------------------------------------------------------
    for k in range(n - 1, -1, -1):
        lmin = max(iend, k + 1)
        if lmin < n:
            temp[lmin:] = a[k, lmin:]
            a[k, lmin:] = 0.0
            sums = temp[lmin:] @ a[lmin:, iend:]
            a[k, iend:] = a[k, iend:] - sums

    # ------------------------------------------------------------------
    # Apply column interchanges (inverse of row interchanges)
    # ------------------------------------------------------------------
    for j in range(n - 2, -1, -1):
        k = index[j]
        if j != k:
            a[:, [j, k]] = a[:, [k, j]]

    return False


# Nutrient minimums.
nutrients = {
    "Calories (kcal)": 3,
    "Protein (g)": 70,
    "Calcium (g)": 0.8,
    "Iron (mg)": 12,
    "Vitamin a (KIU)": 5,
    "Vitamin B1 (mg)": 1.8,
    "Vitamin B2 (mg)": 2.7,
    "Niacin (mg)": 18,
    "Vitamin C (mg)": 75,
}

# Commodity, Unit, 1939 price (cents), Calories (kcal), Protein (g),
# Calcium (g), Iron (mg), Vitamin a (KIU), Vitamin B1 (mg), Vitamin B2 (mg),
# Niacin (mg), Vitamin C (mg)
data = {
    "Wheat Flour (Enriched)": [44.7, 1411, 2, 365, 0, 55.4, 33.3, 441, 0],
    "Macaroni": [11.6, 418, 0.7, 54, 0, 3.2, 1.9, 68, 0],
    "Wheat Cereal (Enriched)": [11.8, 377, 14.4, 175, 0, 14.4, 8.8, 114, 0],
    "Corn Flakes": [11.4, 252, 0.1, 56, 0, 13.5, 2.3, 68, 0],
    "Corn Meal": [36.0, 897, 1.7, 99, 30.9, 17.4, 7.9, 106, 0],
    "Hominy Grits": [28.6, 680, 0.8, 80, 0, 10.6, 1.6, 110, 0],
    "Rice": [21.2, 460, 0.6, 41, 0, 2, 4.8, 60, 0],
    "Rolled Oats": [25.3, 907, 5.1, 341, 0, 37.1, 8.9, 64, 0],
    "White Bread (Enriched)": [15.0, 488, 2.5, 115, 0, 13.8, 8.5, 126, 0],
    "Whole Wheat Bread": [12.2, 484, 2.7, 125, 0, 13.9, 6.4, 160, 0],
    "Rye Bread": [12.4, 439, 1.1, 82, 0, 9.9, 3, 66, 0],
    "Pound Cake": [8.0, 130, 0.4, 31, 18.9, 2.8, 3, 17, 0],
    "Soda Crackers": [12.5, 288, 0.5, 50, 0, 0, 0, 0, 0],
    "Milk": [6.1, 310, 10.5, 18, 16.8, 4, 16, 7, 177],
    "Evaporated Milk (can)": [8.4, 422, 15.1, 9, 26, 3, 23.5, 11, 60],
    "Butter": [10.8, 9, 0.2, 3, 44.2, 0, 0.2, 2, 0],
    "Oleomargarine": [20.6, 17, 0.6, 6, 55.8, 0.2, 0, 0, 0],
    "Eggs": [2.9, 238, 1.0, 52, 18.6, 2.8, 6.5, 1, 0],
    "Cheese (Cheddar)": [7.4, 448, 16.4, 19, 28.1, 0.8, 10.3, 4, 0],
    "Cream": [3.5, 49, 1.7, 3, 16.9, 0.6, 2.5, 0, 17],
    "Peanut Butter": [15.7, 661, 1.0, 48, 0, 9.6, 8.1, 471, 0],
    "Mayonnaise": [8.6, 18, 0.2, 8, 2.7, 0.4, 0.5, 0, 0],
    "Crisco": [20.1, 0, 0, 0, 0, 0, 0, 0, 0],
    "Lard": [41.7, 0, 0, 0, 0.2, 0, 0.5, 5, 0],
    "Sirloin Steak": [2.9, 166, 0.1, 34, 0.2, 2.1, 2.9, 69, 0],
    "Round Steak": [2.2, 214, 0.1, 32, 0.4, 2.5, 2.4, 87, 0],
    "Rib Roast": [3.4, 213, 0.1, 33, 0, 0, 2, 0, 0],
    "Chuck Roast": [3.6, 309, 0.2, 46, 0.4, 1, 4, 120, 0],
    "Plate": [8.5, 404, 0.2, 62, 0, 0.9, 0, 0, 0],
    "Liver (Beef)": [2.2, 333, 0.2, 139, 169.2, 6.4, 50.8, 316, 525],
    "Leg of Lamb": [3.1, 245, 0.1, 20, 0, 2.8, 3.9, 86, 0],
    "Lamb Chops (Rib)": [3.3, 140, 0.1, 15, 0, 1.7, 2.7, 54, 0],
    "Pork Chops": [3.5, 196, 0.2, 30, 0, 17.4, 2.7, 60, 0],
    "Pork Loin Roast": [4.4, 249, 0.3, 37, 0, 18.2, 3.6, 79, 0],
    "Bacon": [10.4, 152, 0.2, 23, 0, 1.8, 1.8, 71, 0],
    "Ham, smoked": [6.7, 212, 0.2, 31, 0, 9.9, 3.3, 50, 0],
    "Salt Pork": [18.8, 164, 0.1, 26, 0, 1.4, 1.8, 0, 0],
    "Roasting Chicken": [1.8, 184, 0.1, 30, 0.1, 0.9, 1.8, 68, 46],
    "Veal Cutlets": [1.7, 156, 0.1, 24, 0, 1.4, 2.4, 57, 0],
    "Salmon, Pink (can)": [5.8, 705, 6.8, 45, 3.5, 1, 4.9, 209, 0],
    "Apples": [5.8, 27, 0.5, 36, 7.3, 3.6, 2.7, 5, 544],
    "Bananas": [4.9, 60, 0.4, 30, 17.4, 2.5, 3.5, 28, 498],
    "Lemons": [1.0, 21, 0.5, 14, 0, 0.5, 0, 4, 952],
    "Oranges": [2.2, 40, 1.1, 18, 11.1, 3.6, 1.3, 10, 1998],
    "Green Beans": [2.4, 138, 3.7, 80, 69, 4.3, 5.8, 37, 862],
    "Cabbage": [2.6, 125, 4.0, 36, 7.2, 9, 4.5, 26, 5369],
    "Carrots": [2.7, 73, 2.8, 43, 188.5, 6.1, 4.3, 89, 608],
    "Celery": [0.9, 51, 3.0, 23, 0.9, 1.4, 1.4, 9, 313],
    "Lettuce": [0.4, 27, 1.1, 22, 112.4, 1.8, 3.4, 11, 449],
    "Onions": [5.8, 166, 3.8, 59, 16.6, 4.7, 5.9, 21, 1184],
    "Potatoes": [14.3, 336, 1.8, 118, 6.7, 29.4, 7.1, 198, 2522],
    "Spinach": [1.1, 106, 0, 138, 918.4, 5.7, 13.8, 33, 2755],
    "Sweet Potatoes": [9.6, 138, 2.7, 54, 290.7, 8.4, 5.4, 83, 1912],
    "Peaches (can)": [3.7, 20, 0.4, 10, 21.5, 0.5, 1, 31, 196],
    "Pears (can)": [3.0, 8, 0.3, 8, 0.8, 0.8, 0.8, 5, 81],
    "Pineapple (can)": [2.4, 16, 0.4, 8, 2, 2.8, 0.8, 7, 399],
    "Asparagus (can)": [0.4, 33, 0.3, 12, 16.3, 1.4, 2.1, 17, 272],
    "Green Beans (can)": [1.0, 54, 2, 65, 53.9, 1.6, 4.3, 32, 431],
    "Pork and Beans (can)": [7.5, 364, 4, 134, 3.5, 8.3, 7.7, 56, 0],
    "Corn (can)": [5.2, 136, 0.2, 16, 12, 1.6, 2.7, 42, 218],
    "Peas (can)": [2.3, 136, 0.6, 45, 34.9, 4.9, 2.5, 37, 370],
    "Tomatoes (can)": [1.3, 63, 0.7, 38, 53.2, 3.4, 2.5, 36, 1253],
    "Tomato Soup (can)": [1.6, 71, 0.6, 43, 57.9, 3.5, 2.4, 67, 862],
    "Peaches, Dried": [8.5, 87, 1.7, 173, 86.8, 1.2, 4.3, 55, 57],
    "Prunes, Dried": [12.8, 99, 2.5, 154, 85.7, 3.9, 4.3, 65, 257],
    "Raisins, Dried": [13.5, 104, 2.5, 136, 4.5, 6.3, 1.4, 24, 136],
    "Peas, Dried": [20.0, 1367, 4.2, 345, 2.9, 28.7, 18.4, 162, 0],
    "Lima Beans, Dried": [17.4, 1055, 3.7, 459, 5.1, 26.9, 38.2, 93, 0],
    "Navy Beans, Dried": [26.9, 1691, 11.4, 792, 0, 38.4, 24.6, 217, 0],
    "Coffee": [0, 0, 0, 0, 0, 4, 5.1, 50, 0],
    "Tea": [0, 0, 0, 0, 0, 0, 2.3, 42, 0],
    "Cocoa": [8.7, 237, 3, 72, 0, 2, 11.9, 40, 0],
    "Chocolate": [8.0, 77, 1.3, 39, 0, 0.9, 3.4, 14, 0],
    "Sugar": [34.9, 0, 0, 0, 0, 0, 0, 0, 0],
    "Corn Syrup": [14.7, 0, 0.5, 74, 0, 0, 0, 5, 0],
    "Molasses": [9.0, 0, 10.3, 244, 0, 1.9, 7.5, 146, 0],
    "Strawberry Preserves": [6.4, 11, 0.4, 7, 0.2, 0.2, 0.4, 3, 0],
}


def test_smplx():
    ind, x, z, iter = smplx(
        a=np.column_stack([*data.values()]),
        b=np.r_[*nutrients.values()],
        c=-np.ones(len(data)),
        numge=len(nutrients),
    )
    assert ind == 0
    assert x.size == len(nutrients) + len(data)
    assert np.count_nonzero(x) == len(nutrients)
    assert [a for a, b in zip(nutrients, x[len(data) :]) if not b] == [
        "Calories (kcal)",
        "Calcium (g)",
        "Vitamin a (KIU)",
        "Vitamin B2 (mg)",
        "Vitamin C (mg)",
    ]
    assert np.isclose(z, -0.10866227746009827)
    assert iter == 8


if __name__ == "__main__":
    test_smplx()
