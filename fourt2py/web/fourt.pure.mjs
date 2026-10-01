// fourt.pure.mjs -- a pure-JavaScript transliteration of ../wasm/fourt.c
// (itself an idiomatic C rewrite of ../FOURT.F), written the way "asm.js"
// code used to be written: every integer-typed local gets `|0` after each
// assignment so the engine never has to guess whether a variable might
// turn into a double, and the data/work buffers are typed arrays
// (Float64Array) instead of plain arrays, so array accesses are
// monomorphic.
//
// This deliberately skips the rest of the historical asm.js ceremony (the
// `function Module(stdlib, foreign, heap) { "use asm"; ... }` wrapper, a
// single shared ArrayBuffer "heap", and manual byte-offset pointer
// arithmetic into it) -- hence "pure" rather than "asmjs" in the name: this
// isn't a from-the-spec asm.js module, just JS written with the same
// type-coercion habits. That machinery existed so a *validator* could prove
// a whole module type-safe ahead of time and hand it to a separate
// fast-compilation path. Modern V8 dropped that separate path years ago --
// "use asm" is just a string literal to it now -- so reproducing it here
// would add real complexity for zero measurable benefit; the `|0`
// coercions are the part of the idiom that still gives the regular
// optimizing JIT a monomorphic type to key off of, with or without the
// pragma. See ./benchmark.mjs for numbers.
//
// Semantics match fourt.c exactly: DATA/WORK are interleaved [re, im, ...]
// Float64Arrays, 0-based, same ICASE/IFORM/ISIGN conventions as FOURT.F.

export function fourt(data, nn, ndim, isign, iform, work) {
    ndim = ndim | 0;
    isign = isign | 0;
    iform = iform | 0;

    const ifact = new Int32Array(32);
    const twopi = 8.0 * Math.atan(1.0);
    const rthlf = Math.sqrt(0.5);

    let np0 = 0 | 0;
    let np1 = 0 | 0;
    let np2 = 0 | 0;
    let nprev = 0 | 0;

    if ((ndim | 0) < 1) {
        normalize(data, nn, ndim, isign);
        return;
    }

    let ntot = 2 | 0;
    for (let idim = 0 | 0; (idim | 0) < (ndim | 0); idim = (idim + 1) | 0) {
        if ((nn[idim] | 0) <= 0) {
            normalize(data, nn, ndim, isign);
            return;
        }
        ntot = Math.imul(ntot, nn[idim] | 0) | 0;
    }

    // Main loop for each dimension.
    np1 = 2 | 0;
    for (let idim = 0 | 0; (idim | 0) < (ndim | 0); idim = (idim + 1) | 0) {
        let n = nn[idim] | 0;
        np2 = Math.imul(np1, n) | 0;
        if ((n | 0) < 1) {
            normalize(data, nn, ndim, isign);
            return;
        }
        if ((n | 0) === 1) {
            // Nothing to transform along this dimension.
            np0 = np1;
            np1 = np2;
            nprev = n;
            continue;
        }

        // Is n a power of two, and if not, what are its factors?
        let m = n | 0;
        let ntwo = np1 | 0;
        let if_ = 0 | 0;
        let idiv = 2 | 0;
        let iquot = 0 | 0;
        let irem = 0 | 0;
        let primeTail = 0 | 0;
        for (;;) {
            iquot = (m / idiv) | 0;
            irem = (m - Math.imul(idiv, iquot)) | 0;
            if ((iquot | 0) < (idiv | 0)) {
                primeTail = 1 | 0;
                break;
            }
            if ((irem | 0) !== 0) {
                break;
            }
            ntwo = (ntwo + ntwo) | 0;
            ifact[if_] = idiv;
            if_ = (if_ + 1) | 0;
            m = iquot;
        }

        let inon2 = 0 | 0;
        if (primeTail) {
            inon2 = if_;
            if ((irem | 0) === 0) {
                ntwo = (ntwo + ntwo) | 0;
            } else {
                ifact[if_] = m;
                if_ = (if_ + 1) | 0;
            }
        } else {
            idiv = 3 | 0;
            inon2 = if_;
            for (;;) {
                iquot = (m / idiv) | 0;
                irem = (m - Math.imul(idiv, iquot)) | 0;
                if ((iquot | 0) < (idiv | 0)) {
                    break;
                }
                if ((irem | 0) === 0) {
                    ifact[if_] = idiv;
                    if_ = (if_ + 1) | 0;
                    m = iquot;
                } else {
                    idiv = (idiv + 2) | 0;
                }
            }
            ifact[if_] = m;
            if_ = (if_ + 1) | 0;
        }
        const non2p = (np2 / ntwo) | 0;

        // Separate four cases --
        //   1. complex transform.
        //   2. real transform for the 2nd, 3rd, etc. dimension. Method --
        //      transform half the data, supplying the other half by
        //      conjugate symmetry.
        //   3. real transform for the 1st dimension, n odd. Method -- set
        //      the imaginary parts to zero.
        //   4. real transform for the 1st dimension, n even. Method --
        //      transform a complex array of length n/2 whose real parts
        //      are the even numbered real values and whose imaginary parts
        //      are the odd numbered real values. Separate and supply the
        //      second half by conjugate symmetry.
        let ifmin = 0 | 0;
        let i1rng = np1 | 0;
        let icase = 0 | 0;
        if (!((iform | 0) <= 0 && (idim | 0) < 3)) {
            icase = 1 | 0;
        } else if ((idim | 0) > 0) {
            icase = 2 | 0;
            i1rng = Math.imul(np0, (1 + ((nprev / 2) | 0)) | 0) | 0;
        } else if ((ntwo | 0) <= (np1 | 0)) {
            icase = 3 | 0;
        } else {
            icase = 4 | 0;
            ifmin = 1 | 0;
            ntwo = (ntwo / 2) | 0;
            n = (n / 2) | 0;
            np2 = (np2 / 2) | 0;
            ntot = (ntot / 2) | 0;
            for (let j = 0 | 0; (j | 0) < (ntot | 0); j = (j + 1) | 0) {
                data[j] = data[2 * j];
            }
        }

        // Shuffle data by bit reversal (n a power of two: non2p<=1, no
        // working array needed) or by digit reversal for general n.
        if ((non2p | 0) <= 1) {
            const np2hf = (np2 / 2) | 0;
            let j = 0 | 0;
            for (let i2 = 0 | 0; (i2 | 0) < (np2 | 0); i2 = (i2 + np1) | 0) {
                if ((j | 0) < (i2 | 0)) {
                    const i1max = (i2 + np1 - 2) | 0;
                    for (let i1 = i2 | 0; (i1 | 0) <= (i1max | 0); i1 = (i1 + 2) | 0) {
                        for (let i3 = i1 | 0; (i3 | 0) < (ntot | 0); i3 = (i3 + np2) | 0) {
                            const j3 = (j + i3 - i2) | 0;
                            const tempr = data[i3];
                            const tempi = data[i3 + 1];
                            data[i3] = data[j3];
                            data[i3 + 1] = data[j3 + 1];
                            data[j3] = tempr;
                            data[j3 + 1] = tempi;
                        }
                    }
                }
                let m2 = np2hf | 0;
                // Careful: this is `J-M` compared against the literal 0 in
                // the Fortran, with J a shifted (0-based) position and M an
                // unshifted stride -- the comparison boundary itself shifts
                // (J<=M, not J<M, is the 0-based "stop" condition here).
                while ((j | 0) >= (m2 | 0)) {
                    j = (j - m2) | 0;
                    m2 = (m2 / 2) | 0;
                    if ((m2 | 0) < (np1 | 0)) {
                        break;
                    }
                }
                j = (j + m2) | 0;
            }
        } else {
            const nwork = (2 * n) | 0;
            for (let i1 = 0 | 0; (i1 | 0) < (np1 | 0); i1 = (i1 + 2) | 0) {
                for (let i3 = i1 | 0; (i3 | 0) < (ntot | 0); i3 = (i3 + np2) | 0) {
                    let j = i3 | 0;
                    for (let i = 0 | 0; (i | 0) < (nwork | 0); i = (i + 2) | 0) {
                        if ((icase | 0) === 3) {
                            work[i] = data[j];
                            work[i + 1] = 0.0;
                        } else {
                            work[i] = data[j];
                            work[i + 1] = data[j + 1];
                        }
                        let ifp2 = np2 | 0;
                        let ifx = ifmin | 0;
                        for (;;) {
                            const ifp1 = (ifp2 / ifact[ifx]) | 0;
                            j = (j + ifp1) | 0;
                            if ((j | 0) < ((i3 + ifp2) | 0)) {
                                break;
                            }
                            j = (j - ifp2) | 0;
                            ifp2 = ifp1;
                            ifx = (ifx + 1) | 0;
                            if ((ifp2 | 0) <= (np1 | 0)) {
                                break;
                            }
                        }
                    }
                    const i2max = (i3 + np2 - np1) | 0;
                    let i = 0 | 0;
                    for (let i2 = i3 | 0; (i2 | 0) <= (i2max | 0); i2 = (i2 + np1) | 0) {
                        data[i2] = work[i];
                        data[i2 + 1] = work[i + 1];
                        i = (i + 2) | 0;
                    }
                }
            }
        }

        // Main loop for factors of two. w=exp(isign*2*pi*sqrt(-1)*m /
        // (4*mmax)); check for w=isign*sqrt(-1) and repeat for
        // w=w*(1+isign*sqrt(-1))/sqrt(2).
        if ((ntwo | 0) > (np1 | 0)) {
            const np1tw = (np1 + np1) | 0;
            let ipar = (ntwo / np1) | 0;
            while ((ipar | 0) > 2) {
                ipar = (ipar / 4) | 0;
            }

            if ((ipar | 0) === 2) {
                for (let i1 = 0 | 0; (i1 | 0) < (i1rng | 0); i1 = (i1 + 2) | 0) {
                    for (let k1 = i1 | 0; (k1 | 0) < (ntot | 0); k1 = (k1 + np1tw) | 0) {
                        const k2 = (k1 + np1) | 0;
                        const tempr = data[k2];
                        const tempi = data[k2 + 1];
                        data[k2] = data[k1] - tempr;
                        data[k2 + 1] = data[k1 + 1] - tempi;
                        data[k1] = data[k1] + tempr;
                        data[k1 + 1] = data[k1 + 1] + tempi;
                    }
                }
            }

            // The Fortran test is `IF(MMAX-NTWO/2)370,600,600`, i.e. continue
            // the doubling loop only while mmax < ntwo/2 (equal or greater
            // both exit).
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

                        for (let i1 = 0 | 0; (i1 | 0) < (i1rng | 0); i1 = (i1 + 2) | 0) {
                            // See the file comment at the top: l/m keep
                            // their Fortran numeric values on purpose, so
                            // this matches `I1+IPAR*M` from the original
                            // exactly once i1 is the (now 0-based) position.
                            let kmin = (useTwiddle ? (i1 + Math.imul(ipar, m)) : i1) | 0;
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
                                kmin = (4 * (kmin - i1) + i1) | 0;
                                kdif = kstep;
                                kstep = (4 * kdif) | 0;
                            }
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

        // Main loop for factors not equal to two. w=exp(isign*2*pi*sqrt(-1)
        // *(j1+j2-i3-1)/ifp2).
        if ((non2p | 0) > 1) {
            let ifp1 = ntwo | 0;
            let ifx = inon2 | 0;
            for (;;) {
                const ifp2 = Math.imul(ifact[ifx], ifp1) | 0;
                let theta = -twopi / ifact[ifx];
                if ((isign | 0) >= 0) {
                    theta = -theta;
                }
                const thtm = theta / ((ifp1 / np1) | 0);
                const wstpr = Math.cos(theta);
                const wstpi = Math.sin(theta);
                const wmstr = Math.cos(thtm);
                const wmsti = Math.sin(thtm);
                let wminr = 1.0;
                let wmini = 0.0;

                for (let j1 = 0 | 0; (j1 | 0) < (ifp1 | 0); j1 = (j1 + np1) | 0) {
                    const i1max = (j1 + i1rng - 2) | 0;
                    for (let i1 = j1 | 0; (i1 | 0) <= (i1max | 0); i1 = (i1 + 2) | 0) {
                        for (let i3 = i1 | 0; (i3 | 0) < (ntot | 0); i3 = (i3 + np2) | 0) {
                            let i = 0 | 0;
                            let wr = wminr;
                            let wi = wmini;
                            const j2max = (i3 + ifp2 - ifp1) | 0;
                            for (let j2 = i3 | 0; (j2 | 0) <= (j2max | 0); j2 = (j2 + ifp1) | 0) {
                                const twowr = wr + wr;
                                let jmin = i3 | 0;
                                const j3max = (j2 + np2 - ifp2) | 0;
                                for (let j3 = j2 | 0; (j3 | 0) <= (j3max | 0); j3 = (j3 + ifp2) | 0) {
                                    let j = (jmin + ifp2 - ifp1) | 0;
                                    let sr = data[j];
                                    let si = data[j + 1];
                                    let oldsr = 0.0;
                                    let oldsi = 0.0;
                                    j = (j - ifp1) | 0;
                                    while ((j | 0) > (jmin | 0)) {
                                        const stmpr = sr;
                                        const stmpi = si;
                                        sr = twowr * sr - oldsr + data[j];
                                        si = twowr * si - oldsi + data[j + 1];
                                        oldsr = stmpr;
                                        oldsi = stmpi;
                                        j = (j - ifp1) | 0;
                                    }
                                    work[i] = wr * sr - wi * si - oldsr + data[j];
                                    work[i + 1] = wi * sr + wr * si - oldsi + data[j + 1];
                                    jmin = (jmin + ifp2) | 0;
                                    i = (i + 2) | 0;
                                }
                                const wtemp = wr * wstpi;
                                wr = wr * wstpr - wi * wstpi;
                                wi = wi * wstpr + wtemp;
                            }
                            i = 0 | 0;
                            for (let j2 = i3 | 0; (j2 | 0) <= (j2max | 0); j2 = (j2 + ifp1) | 0) {
                                const j3max = (j2 + np2 - ifp2) | 0;
                                for (let j3 = j2 | 0; (j3 | 0) <= (j3max | 0); j3 = (j3 + ifp2) | 0) {
                                    data[j3] = work[i];
                                    data[j3 + 1] = work[i + 1];
                                    i = (i + 2) | 0;
                                }
                            }
                        }
                    }
                    const wtemp = wminr * wmsti;
                    wminr = wminr * wmstr - wmini * wmsti;
                    wmini = wmini * wmstr + wtemp;
                }

                ifx = (ifx + 1) | 0;
                ifp1 = ifp2;
                if ((ifp1 | 0) >= (np2 | 0)) {
                    break;
                }
            }
        }

        // Dispatch on which of the four cases above we're completing.
        if ((icase | 0) === 2) {
            // Complete a real transform for the 2nd, 3rd, etc. dimension by
            // conjugate symmetries.
            if ((i1rng | 0) < (np1 | 0)) {
                for (let i3 = 0 | 0; (i3 | 0) < (ntot | 0); i3 = (i3 + np2) | 0) {
                    const i2max = (i3 + np2 - np1) | 0;
                    for (let i2 = i3 | 0; (i2 | 0) <= (i2max | 0); i2 = (i2 + np1) | 0) {
                        const imax = (i2 + np1 - 2) | 0;
                        const imin = (i2 + i1rng) | 0;
                        const jmax = (2 * i3 + np1 - imin + ((i2 | 0) > (i3 | 0) ? np2 : 0)) | 0;
                        let j;
                        if ((idim | 0) > 1) {
                            j = (jmax + np0) | 0;
                            for (let i = imin | 0; (i | 0) <= (imax | 0); i = (i + 2) | 0) {
                                data[i] = data[j];
                                data[i + 1] = -data[j + 1];
                                j = (j - 2) | 0;
                            }
                        }
                        j = jmax | 0;
                        for (let i = imin | 0; (i | 0) <= (imax | 0); i = (i + np0) | 0) {
                            data[i] = data[j];
                            data[i + 1] = -data[j + 1];
                            j = (j - np0) | 0;
                        }
                    }
                }
            }
        } else if ((icase | 0) === 4) {
            // Complete a real transform in the 1st dimension, n even, by
            // conjugate symmetries.
            const nhalf = n | 0;
            n = (n + n) | 0;
            let theta = -twopi / n;
            if ((isign | 0) >= 0) {
                theta = -theta;
            }
            const wstpr = Math.cos(theta);
            const wstpi = Math.sin(theta);
            let wr = wstpr;
            let wi = wstpi;
            let imin = 2 | 0;
            let jmin = (2 * nhalf - 2) | 0;

            while ((imin | 0) < (jmin | 0)) {
                let j = jmin | 0;
                for (let i = imin | 0; (i | 0) < (ntot | 0); i = (i + np2) | 0) {
                    const sumr = (data[i] + data[j]) / 2.0;
                    const sumi = (data[i + 1] + data[j + 1]) / 2.0;
                    const difr = (data[i] - data[j]) / 2.0;
                    const difi = (data[i + 1] - data[j + 1]) / 2.0;
                    const tempr = wr * sumi + wi * difr;
                    const tempi = wi * sumi - wr * difr;
                    data[i] = sumr + tempr;
                    data[i + 1] = difi + tempi;
                    data[j] = sumr - tempr;
                    data[j + 1] = -difi + tempi;
                    j = (j + np2) | 0;
                }
                imin = (imin + 2) | 0;
                jmin = (jmin - 2) | 0;
                const wtemp = wr * wstpi;
                wr = wr * wstpr - wi * wstpi;
                wi = wi * wstpr + wtemp;
            }

            if ((imin | 0) === (jmin | 0) && (isign | 0) < 0) {
                for (let i = imin | 0; (i | 0) < (ntot | 0); i = (i + np2) | 0) {
                    data[i + 1] = -data[i + 1];
                }
            }

            np2 = (np2 + np2) | 0;
            ntot = (ntot + ntot) | 0;
            let j = ntot | 0;
            let imax = (ntot / 2) | 0;
            // Sweep inward from both ends of the (now doubled) buffer,
            // mirroring the first half into the second half by conjugate
            // symmetry, shrinking the swept range (via imax=imin) each pass
            // until the two ends meet.
            for (;;) {
                imin = (imax - 2 * nhalf) | 0;
                let i = imin | 0;
                for (;;) {
                    i = (i + 2) | 0;
                    j = (j - 2) | 0;
                    if ((i | 0) >= (imax | 0)) {
                        break;
                    }
                    data[j] = data[i];
                    data[j + 1] = -data[i + 1];
                }
                data[j] = data[imin] - data[imin + 1];
                data[j + 1] = 0.0;
                if ((i | 0) >= (j | 0)) {
                    break;
                }
                for (;;) {
                    i = (i - 2) | 0;
                    j = (j - 2) | 0;
                    if ((i | 0) <= (imin | 0)) {
                        break;
                    }
                    data[j] = data[i];
                    data[j + 1] = data[i + 1];
                }
                data[j] = data[imin] + data[imin + 1];
                data[j + 1] = 0.0;
                imax = imin;
            }
            data[0] = data[0] + data[1];
            data[1] = 0.0;
        }

        np0 = np1;
        np1 = np2;
        nprev = n;
    }

    normalize(data, nn, ndim, isign);
}

function normalize(data, nn, ndim, isign) {
    if ((isign | 0) === 1) {
        return;
    }
    let ntot = 2 | 0;
    for (let idim = 0 | 0; (idim | 0) < (ndim | 0); idim = (idim + 1) | 0) {
        ntot = Math.imul(ntot, nn[idim] | 0) | 0;
    }
    const ntothf = (ntot / 2) | 0;
    for (let itot = 0 | 0; (itot | 0) < (ntot | 0); itot = (itot + 1) | 0) {
        data[itot] = data[itot] / ntothf;
    }
}
