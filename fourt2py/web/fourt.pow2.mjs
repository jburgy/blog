// fourt.pow2.mjs -- a specialized version of fourt.pure.mjs restricted to
// exactly what fourt2py/web/demo.mjs actually needs: one dimension, a
// power-of-two length, and the complex transform (ICASE=1, IFORM=1).
//
// Fixing those three things statically eliminates most of FOURT's
// generality:
//   - n a power of two => NTWO always ends up equal to NP2, so NON2P is
//     always 1 -- the digit-reversal shuffle and the whole "main loop for
//     factors not equal to two" (the mixed-radix Horner recurrence) are
//     dead code and are simply not here.
//   - one dimension => no outer per-dimension loop, no NP0/NPREV
//     bookkeeping, no ICASE 2/3/4 (those only exist for NDIM>1 or real
//     input), no factor-finding loop or IFACT array (every factor is 2, so
//     nothing needs to be discovered).
//   - NP1 is therefore always 2, which makes I1RNG always 2 too -- so the
//     radix-4 butterfly's "for i1 in 0..i1rng step 2" loop only ever runs
//     once, at i1=0, and has been inlined away rather than looped.
//   - FOURT.F's own doc comment says WORK is unnecessary when every
//     dimension is a power of two, so there's no `work` parameter at all.
//
// What's left is the bit-reversal shuffle and the radix-4/radix-2 butterfly
// passes, nothing else. Same `|0` type-coercion habit as fourt.pure.mjs,
// same reasoning for not bothering with the rest of the asm.js ceremony.
//
// Signature intentionally drops `nn`, `ndim`, `iform` and `work` from
// fourt.pure.mjs's -- this isn't a drop-in replacement, it's a narrower
// tool for a narrower job. fourt2py/web/demo.mjs uses this directly, at
// N=256; fourt2py/wasm/fourt.c and fourt.pure.mjs remain as the general,
// non-power-of-two-capable versions. See ./benchmark.mjs for how this
// compares to wasm and to the general pure-JS port.

export function fourt(data, n, isign) {
    n = n | 0;
    isign = isign | 0;

    const twopi = 8.0 * Math.atan(1.0);
    const rthlf = Math.sqrt(0.5);

    const np1 = 2 | 0;
    const ntot = (2 * n) | 0;
    const ntwo = (2 * n) | 0; // n is a power of two, so NTWO always reaches NP2.

    // Bit-reversal shuffle (NON2P<=1 is guaranteed here, so this is the
    // only shuffle fourt.pure.mjs would ever reach for this input anyway).
    {
        const np2 = ntot;
        const np2hf = (np2 / 2) | 0;
        let j = 0 | 0;
        for (let i2 = 0 | 0; (i2 | 0) < (np2 | 0); i2 = (i2 + np1) | 0) {
            if ((j | 0) < (i2 | 0)) {
                const tempr = data[i2];
                const tempi = data[i2 + 1];
                data[i2] = data[j];
                data[i2 + 1] = data[j + 1];
                data[j] = tempr;
                data[j + 1] = tempi;
            }
            let m2 = np2hf | 0;
            while ((j | 0) >= (m2 | 0)) {
                j = (j - m2) | 0;
                m2 = (m2 / 2) | 0;
                if ((m2 | 0) < (np1 | 0)) {
                    break;
                }
            }
            j = (j + m2) | 0;
        }
    }

    // Main loop for factors of two. Guard matches fourt.pure.mjs's
    // `ntwo > np1` exactly; for n=1 (ntwo=2=np1) there's nothing to do and
    // this is skipped, same as the general version.
    if ((ntwo | 0) > (np1 | 0)) {
        const np1tw = (np1 + np1) | 0;
        let ipar = (ntwo / np1) | 0;
        while ((ipar | 0) > 2) {
            ipar = (ipar / 4) | 0;
        }

        if ((ipar | 0) === 2) {
            for (let k1 = 0 | 0; (k1 | 0) < (ntot | 0); k1 = (k1 + np1tw) | 0) {
                const k2 = (k1 + np1) | 0;
                const tempr = data[k2];
                const tempi = data[k2 + 1];
                data[k2] = data[k1] - tempr;
                data[k2 + 1] = data[k1 + 1] - tempi;
                data[k1] = data[k1] + tempr;
                data[k1 + 1] = data[k1 + 1] + tempi;
            }
        }

        for (let mmax = np1 | 0; (mmax | 0) < ((ntwo / 2) | 0); mmax = (mmax + mmax) | 0) {
            const lmax = ((np1tw | 0) > ((mmax / 2) | 0) ? np1tw : (mmax / 2) | 0) | 0;
            const useTwiddle = (mmax | 0) > (np1 | 0) ? 1 : 0;
            let wr = 0.0;
            let wi = 0.0;

            for (let l = np1 | 0; (l | 0) <= (lmax | 0); l = (l + np1tw) | 0) {
                let m = l | 0;
                if (useTwiddle) {
                    let theta = (-twopi * l) / (4 * mmax);
                    if ((isign | 0) >= 0) {
                        theta = -theta;
                    }
                    wr = Math.cos(theta);
                    wi = Math.sin(theta);
                }

                for (;;) {
                    let w2r = 0.0;
                    let w2i = 0.0;
                    let w3r = 0.0;
                    let w3i = 0.0;
                    if (useTwiddle) {
                        w2r = wr * wr - wi * wi;
                        w2i = 2.0 * wr * wi;
                        w3r = w2r * wr - w2i * wi;
                        w3i = w2r * wi + w2i * wr;
                    }

                    // i1 only ever takes the value 0 here (I1RNG is always
                    // NP1=2), so fourt.pure.mjs's `for i1 in 0..i1rng` loop
                    // is gone; `kmin = i1 + ipar*m` with i1=0 is just
                    // `ipar*m`, and the end-of-pass update
                    // `kmin = 4*(kmin-i1)+i1` is just `4*kmin`.
                    let kmin = (useTwiddle ? Math.imul(ipar, m) : 0) | 0;
                    let kdif = Math.imul(ipar, mmax) | 0;
                    for (let kstep = (4 * kdif) | 0; (kstep | 0) <= (ntwo | 0); ) {
                        for (let k1 = kmin | 0; (k1 | 0) < (ntot | 0); k1 = (k1 + kstep) | 0) {
                            const k2 = (k1 + kdif) | 0;
                            const k3 = (k2 + kdif) | 0;
                            const k4 = (k3 + kdif) | 0;
                            let u1r, u1i, u2r, u2i, u3r, u3i, u4r, u4i;
                            if (!useTwiddle) {
                                u1r = data[k1] + data[k2];
                                u1i = data[k1 + 1] + data[k2 + 1];
                                u2r = data[k3] + data[k4];
                                u2i = data[k3 + 1] + data[k4 + 1];
                                u3r = data[k1] - data[k2];
                                u3i = data[k1 + 1] - data[k2 + 1];
                                if ((isign | 0) < 0) {
                                    u4r = data[k3 + 1] - data[k4 + 1];
                                    u4i = data[k4] - data[k3];
                                } else {
                                    u4r = data[k4 + 1] - data[k3 + 1];
                                    u4i = data[k3] - data[k4];
                                }
                            } else {
                                const t2r = w2r * data[k2] - w2i * data[k2 + 1];
                                const t2i = w2r * data[k2 + 1] + w2i * data[k2];
                                const t3r = wr * data[k3] - wi * data[k3 + 1];
                                const t3i = wr * data[k3 + 1] + wi * data[k3];
                                const t4r = w3r * data[k4] - w3i * data[k4 + 1];
                                const t4i = w3r * data[k4 + 1] + w3i * data[k4];
                                u1r = data[k1] + t2r;
                                u1i = data[k1 + 1] + t2i;
                                u2r = t3r + t4r;
                                u2i = t3i + t4i;
                                u3r = data[k1] - t2r;
                                u3i = data[k1 + 1] - t2i;
                                if ((isign | 0) < 0) {
                                    u4r = t3i - t4i;
                                    u4i = t4r - t3r;
                                } else {
                                    u4r = t4i - t3i;
                                    u4i = t3r - t4r;
                                }
                            }
                            data[k1] = u1r + u2r;
                            data[k1 + 1] = u1i + u2i;
                            data[k2] = u3r + u4r;
                            data[k2 + 1] = u3i + u4i;
                            data[k3] = u1r - u2r;
                            data[k3 + 1] = u1i - u2i;
                            data[k4] = u3r - u4r;
                            data[k4 + 1] = u3i - u4i;
                        }
                        kmin = (4 * kmin) | 0;
                        kdif = kstep;
                        kstep = (4 * kdif) | 0;
                    }

                    m = (m + lmax) | 0;
                    if ((m | 0) > (mmax | 0)) {
                        break;
                    }
                    const tempr = wr;
                    if ((isign | 0) < 0) {
                        wr = (wr + wi) * rthlf;
                        wi = (wi - tempr) * rthlf;
                    } else {
                        wr = (wr - wi) * rthlf;
                        wi = (tempr + wi) * rthlf;
                    }
                }
            }

            ipar = (3 - ipar) | 0;
        }
    }

    if ((isign | 0) !== 1) {
        const ntothf = (ntot / 2) | 0;
        for (let itot = 0 | 0; (itot | 0) < (ntot | 0); itot = (itot + 1) | 0) {
            data[itot] = data[itot] / ntothf;
        }
    }
}
