# ruff: noqa: E741, F821, F841

# simplex.py
import numpy as np

def smplx(a, b0, c, ind=0, ibasis=None, mxiter=1000, numle=None, numge=None):
    """
    Solve linear program:
        maximize c^T x
        subject to A x (<=, =, >=) b0, x >= 0.
    Constraints: first numle are <=, next numge are >=, rest are =.
    """
    # Infer dimensions
    m, n0 = a.shape
    b0 = np.asarray(b0, dtype=float).ravel()
    c = np.asarray(c, dtype=float).ravel()
    if numge is None:
        numge = 0
    if numle is None:
        numle = m - numge
    ms = numle + numge
    # Validate input
    if m < 2 or n0 < 2 or ms > m or a.shape[0] < m or np.any(b0 < 0):
        return 5, None, None, None

    # Machine constants
    eps0 = np.finfo(float).eps
    rerr_mn = 10.0 * eps0
    rerr_mx = 1e-4 if eps0 >= 1e-13 else 1e-5
    xmax = np.finfo(float).max

    # Work arrays
    ns = n0 + numle          # original + slack
    n = ns + numge           # + surplus
    x = np.zeros(n)          # solution and reduced costs
    bi = np.eye(m)           # basis inverse
    xb = np.zeros(m)         # basic variable values
    y = np.zeros(m)          # work array
    basis = np.zeros(n, dtype=int)   # 1 if variable is basic
    idx = np.zeros(m, dtype=int)     # work index array

    # Initial basis (slack variables)
    if ind == 0:
        ibasis_arr = np.arange(n0, n0 + m)
        # Adjust for >= constraints
        for j in range(numle, ms):
            xb[j] = -b0[j]
            bi[j, j] = -1.0
    else:
        ibasis_arr = np.asarray(ibasis, dtype=int) - 1   # convert to 0-index
        # Reorder so non-original variables come first
        ibeg, iend = 0, m - 1
        reorder = np.zeros(m, dtype=int)
        for i in range(m):
            if ibasis_arr[i] >= n0:
                reorder[ibeg] = ibasis_arr[i]
                ibeg += 1
            else:
                reorder[iend] = ibasis_arr[i]
                iend -= 1
        ibasis_arr = reorder
        # Reinvert basis
        ierr, _ = _crout1(bi, iend, idx)
        if ierr != 0:
            return 5, None, None, None
        # Recompute xb
        for i in range(m):
            xb[i] = np.dot(bi[i], b0)
            if abs(xb[i]) < rerr_mx * max(abs(xb[i]), 0.0):
                xb[i] = 0.0

    # Mark basic variables
    for i in range(m):
        basis[ibasis_arr[i]] = 1

    # Main algorithm
    nstep = 1
    iter_count = 0
    rerr = rerr_mn
    bflag = 0
    r = x   # alias

    # Helper to compute reduced costs (phase-dependent)
    def compute_reduced_costs():
        nonlocal r, y, basis
        if nstep == 1:
            # Phase I: eliminate negative xb
            neg_idx = np.where(xb < 0)[0]
            if len(neg_idx) > 0:
                y = np.sum(bi[neg_idx], axis=0)
                # Zero small entries
                y[np.abs(y) < rerr_mx * np.max(np.abs(y), initial=0)] = 0.0
            else:
                y.fill(0.0)
            # Reduced costs for original variables
            for j in range(n0):
                if not basis[j]:
                    r[j] = np.dot(y, a[:, j])
            # Slack/surplus
            if ns > n0:
                r[n0:ns] = y[:numle] if numle else 0.0
            if n > ns:
                r[ns:n] = -y[numle:ms] if numge else 0.0
        elif nstep == 2:
            # Phase I: eliminate artificial variables
            art_idx = np.where(ibasis_arr >= n)[0]
            if len(art_idx) > 0:
                y = -np.sum(bi[art_idx], axis=0)
                y[np.abs(y) < rerr_mx * np.max(np.abs(y), initial=0)] = 0.0
            else:
                y.fill(0.0)
            # Reduced costs (same as phase 1)
            for j in range(n0):
                if not basis[j]:
                    r[j] = np.dot(y, a[:, j])
            if ns > n0:
                r[n0:ns] = y[:numle] if numle else 0.0
            if n > ns:
                r[ns:n] = -y[numle:ms] if numge else 0.0
        else:  # nstep == 3
            # Phase II: original objective
            # y = C_b * BI
            y = np.zeros(m)
            for i in range(m):
                if ibasis_arr[i] < n0:
                    y += c[ibasis_arr[i]] * bi[i]
            for j in range(n0):
                if not basis[j]:
                    rj = -c[j] + np.dot(y, a[:, j])
                    r[j] = rj if rj < 0 and abs(rj) > rerr_mx * abs(c[j]) else 0.0
            # Slack/surplus (same as phase 1 but using y)
            if ns > n0:
                r[n0:ns] = y[:numle] if numle else 0.0
            if n > ns:
                r[ns:n] = -y[numle:ms] if numge else 0.0

    # Main iteration loop
    while True:
        # Find entering variable
        jp = -1
        rmin = 0.0
        if nstep == 3:
            rmin = -rerr_mx * min(abs(c[c != 0]), default=1.0)  # RTOL
        for j in range(n):
            if not basis[j] and r[j] < rmin:
                jp = j
                rmin = r[j]
        if jp == -1:
            # No entering variable -> optimal
            if nstep == 2:
                # Phase I: check if artificials are zero
                for i in range(m):
                    if ibasis_arr[i] >= n and xb[i] > 0:
                        return 1, None, None, None   # infeasible
                nstep = 3
                compute_reduced_costs()
                continue
            elif nstep == 1:
                nstep = 2
                compute_reduced_costs()
                continue
            else:  # nstep == 3
                ind_out = 0
            break

        # Iteration limit
        if iter_count >= mxiter:
            ind_out = 2
            break

        iter_count += 1
        ict = ict + 1 if 'ict' in locals() else 1  # iterations since last reinversion

        # Compute column of basis inverse * A(:, jp)
        if jp < n0:
            a_col = a[:, jp]
            y[:] = np.dot(bi, a_col)
            # Zero very small entries
            tol = rerr_mx * np.max(np.abs(a_col)) * np.max(np.abs(bi), axis=1)
            y[np.abs(y) < tol] = 0.0
        elif jp < ns:
            y[:] = bi[:, jp - n0]
        else:
            y[:] = -bi[:, jp - n0]

        # Check unboundedness
        if np.all(y <= 0):
            if nstep == 2 and ict >= 5:
                ind_out = 4
                break
            elif nstep != 2:
                ind_out = 4
                break

        # Ratio test
        ip = -1
        if nstep == 1:
            # Negative variable elimination (allow negative xb)
            ratios = np.where(y > 0, xb / y, np.inf)
            eps_i = np.min(ratios)
            if np.isfinite(eps_i):
                ip = np.argmin(ratios)
            else:
                neg_ratios = np.where(y < 0, xb / y, -np.inf)
                if np.any(neg_ratios > -np.inf):
                    ip = np.argmax(neg_ratios)
        elif nstep == 2:
            ratios = np.where(y > 0, xb / y, np.inf)
            eps_i = np.min(ratios)
            if np.isfinite(eps_i):
                ip = np.argmin(ratios)
            else:
                ind_out = 4
                break
        else:  # nstep == 3
            pos = (y > 0) & (xb > 0)
            if not np.any(pos):
                ind_out = 4
                break
            ratios = np.where(pos, xb / y, np.inf)
            ip = np.argmin(ratios)

        if ip == -1:
            ind_out = 4
            break

        # Update xb
        theta = xb[ip] / y[ip]
        xb -= theta * y
        xb[ip] = theta
        # Zero small negative values
        xb[(xb < 0) & (xb > -rerr_mx * np.abs(xb))] = 0.0

        # Update basis inverse
        bi_row = bi[ip, :].copy()
        for i in range(m):
            if i != ip:
                bi[i] -= bi_row * (y[i] / y[ip])
        bi[ip] /= y[ip]

        # Update ibasis and basis
        iout = ibasis_arr[ip]
        ibasis_arr[ip] = jp
        basis[iout] = 0
        basis[jp] = 1

        # Check accuracy
        if rerr > 1e-2:
            if ict >= 5:
                # Reinvert
                ibeg, iend = 0, m - 1
                reorder = np.zeros(m, dtype=int)
                for i in range(m):
                    if ibasis_arr[i] >= n0:
                        reorder[ibeg] = ibasis_arr[i]
                        ibeg += 1
                    else:
                        reorder[iend] = ibasis_arr[i]
                        iend -= 1
                ibasis_arr = reorder
                ierr, _ = _crout1(bi, iend, idx)
                if ierr != 0:
                    ind_out = 3
                    break
                for i in range(m):
                    xb[i] = np.dot(bi[i], b0)
                    if abs(xb[i]) < rerr_mx * max(abs(xb[i]), 0.0):
                        xb[i] = 0.0
                bflag = 1
                ict = 0
                compute_reduced_costs()
                continue

        # Update reduced costs if in phase III
        if nstep == 3:
            const = r[jp]
            for j in range(n):
                if not basis[j]:
                    if j < n0:
                        sum_ = np.dot(bi[ip], a[:, j])
                    elif j < ns:
                        sum_ = bi[ip, j - n0]
                    else:
                        sum_ = -bi[ip, j - n0]
                    r[j] -= const * sum_
                    if r[j] < 0 and abs(r[j]) < rerr_mx * abs(c[j] if j < n0 else 0.0):
                        r[j] = 0.0

    # Fill solution array
    for i in range(m):
        if ibasis_arr[i] < n:
            x[ibasis_arr[i]] = xb[i]
    z = np.dot(c, x[:n0]) if nstep == 3 else 0.0
    return ind_out, x[:n], z, iter_count


def _crout1(A, iend, index):
    """Crout's method for matrix inversion (in-place). Returns (ierr, jp)."""
    m = A.shape[0]
    n = m
    # Work in column-major order for simplicity
    a = A.T.flatten()
    ka = n
    max_idx = ka * n
    mcol = iend * ka

    if iend > 0:
        kcol = 0
        for k in range(iend):
            kk = kcol + k
            nk = kcol + n
            for lk in range(kk, nk):
                if abs(a[lk]) > 0:
                    l = lk - kcol
                    index[k] = l
                    if k != l:
                        lj0 = mcol + l
                        for lj in range(lj0, max_idx, ka):
                            a[lj] = -a[lj]
                        for kj in range(kk, max_idx, ka):
                            c = a[kj]
                            a[kj] = a[lk + (kj - kk)]
                            a[lk + (kj - kk)] = c
                    break
            kcol += ka

    jp = 0
    ierr = 0
    pmin = 0.0
    ibeg = iend
    if ibeg == n:
        pass
    else:
        k = ibeg
        km1 = iend
        kp1 = k + 1
        kcol = mcol
        kk = kcol + k
        for kcount in range(ibeg, n-1):
            l = k
            s = abs(a[kk])
            for i in range(kp1, n):
                ik = kcol + i
                c = abs(a[ik])
                if s < c:
                    l = i
                    s = c
            if k > ibeg and s >= pmin:
                pass
            else:
                jp = k
                pmin = s
                if s == 0.0:
                    ierr = 1
                    return ierr, jp
            index[k] = l
            if k != l:
                kj0 = mcol + k
                lj = mcol + l
                for kj in range(kj0, max_idx, ka):
                    c = a[kj]
                    a[kj] = a[lj]
                    a[lj] = c
                    lj += ka
            c = a[kk]
            if k > ibeg:
                kl = mcol + k
                temp = np.zeros(n)
                for l in range(ibeg, km1):
                    temp[l] = a[kl]
                    kl += ka
                kj0 = kk + ka
                for kj in range(kj0, max_idx, ka):
                    jcol = kj - k
                    dsum = -a[kj]
                    for l in range(ibeg, km1):
                        lj = jcol + l
                        dsum += temp[l] * a[lj]
                    a[kj] = -dsum / c
            else:
                kj0 = kk + ka
                for kj in range(kj0, max_idx, ka):
                    a[kj] = a[kj] / c
            km1 = k
            k = kp1
            kp1 = k + 1
            kcol += ka
            kk = kcol + k
            for l in range(ibeg, km1):
                lk = kcol + l
                temp[l] = a[lk]
            for i in range(k, n):
                il = mcol + i
                dsum = 0.0
                for l in range(ibeg, km1):
                    dsum += a[il] * temp[l]
                    il += ka
                a[il] -= dsum

    ncol = max_idx - ka
    nn = ncol + n
    if n > 1:
        c = abs(a[nn])
        if c <= pmin:
            jp = n
            if c == 0.0:
                ierr = 1
                return ierr, jp

    # Replace L with inverse of L
    if ibeg < n:
        jj = mcol + ibeg
        inc = ka + 1
        for j in range(ibeg, n-1):
            a[jj] = 1.0 / a[jj]
            temp_j = a[jj]
            kj = jj
            for km1 in range(j, n-1):
                k = km1 + 1
                kj += 1
                dsum = 0.0
                kl = kj
                for l in range(j, km1):
                    dsum += a[kl] * temp_l
                    kl += ka
                a[kj] = -dsum / a[kl]
                temp_l = a[kj]
            jj += inc
        a[nn] = 1.0 / a[nn]
    else:
        a[nn] = 1.0 / a[nn]

    # Solve UX = Y where Y is inverse of L
    for nmk in range(1, n):
        k = n - nmk
        lmin = max(ibeg, k+1)
        kl = (lmin - 1) * ka + k
        temp = np.zeros(n)
        for l in range(lmin, n):
            temp[l] = a[kl]
            a[kl] = 0.0
            kl += ka
        kj0 = mcol + k
        for kj in range(kj0, max_idx, ka):
            dsum = -a[kj]
            lj = (kj - k) + lmin
            for l in range(lmin, n):
                dsum += temp[l] * a[lj]
                lj += 1
            a[kj] = -dsum

    # Column interchanges
    jcol = ncol - ka
    for nmj in range(1, n):
        j = n - nmj
        k = index[j]
        if j != k:
            ij = jcol
            ik = (k - 1) * ka
            for i in range(n):
                ij += 1
                ik += 1
                c = a[ij]
                a[ij] = a[ik]
                a[ik] = c
        jcol -= ka

    A[:] = a.reshape((n, n), order='F').T
    return ierr, jp

# Nutrient minimums.
nutrients = {
    "Calories (kcal)": 3,
    "Protein (g)": 70,
    "Calcium (g)": 0.8,
    "Iron (mg)": 12,
    "Vitamin A (KIU)": 5,
    "Vitamin B1 (mg)": 1.8,
    "Vitamin B2 (mg)": 2.7,
    "Niacin (mg)": 18,
    "Vitamin C (mg)": 75,
}

# Commodity, Unit, 1939 price (cents), Calories (kcal), Protein (g),
# Calcium (g), Iron (mg), Vitamin A (KIU), Vitamin B1 (mg), Vitamin B2 (mg),
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
        b0=np.r_[*nutrients.values()],
        c=-np.ones(len(data)),
        numge=len(nutrients),
    )
    assert ind == 0
    assert x.size == len(nutrients) + len(data)
    assert np.count_nonzero(x) == len(nutrients)
    assert [a for a, b in zip(nutrients, x[len(data) :]) if not b] == [
        "Calories (kcal)",
        "Calcium (g)",
        "Vitamin A (KIU)",
        "Vitamin B2 (mg)",
        "Vitamin C (mg)",
    ]
    assert np.isclose(z, -0.10866227746009827)
    assert iter == 8


test_smplx()
