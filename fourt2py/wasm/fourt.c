// fourt.c -- idiomatic C rewrite of FOURT.F (Norman Brenner's mixed-radix
// FFT), using native 0-based array indexing and structured control flow
// (if/else/for/while/break/continue) instead of labeled GOTOs. See
// ../FOURT.F for the Fortran source; the previous commit has a literal,
// label-for-label transliteration of it (`git show HEAD~:fourt2py/wasm/fourt.c`)
// for side-by-side comparison, in case this rewrite needs reverting.
//
// A few GOTOs survive, in the classic "goto cleanup" style for early exits
// to a shared tail (search for `goto` below); everything else is
// structured. The one subtlety worth flagging for reviewers: the radix-4
// butterfly loop's `l`/`m` counters are deliberately left at their
// Fortran-original (not shifted) values, because they are used directly in
// a trig/twiddle-factor formula where the *absolute* numeric value matters,
// not just as array offsets -- shifting them would change the computed
// angle. They still combine correctly with the (now 0-based) `i1` to
// produce a correct 0-based `kmin` (see the comment at that call site).
//
// DATA holds interleaved real/imaginary doubles, one complex number per 2
// consecutive entries (same storage convention as the Fortran). NN(i) in
// the Fortran becomes nn[i] directly (nn is already a plain 0-based C array
// of length ndim). IFACT is a local scratch array, also 0-based here.

#include <math.h>
#include <stdbool.h>

void fourt_(double *data, int *nn, int ndim, int isign, int iform, double *work) {
    int ifact[32];
    const double twopi = 8.0 * atan(1.0);
    const double rthlf = sqrt(0.5);

    int np0 = 0, np1, np2;
    int nprev = 0;

    if (ndim < 1) {
        goto normalize;
    }

    int ntot = 2;
    for (int idim = 0; idim < ndim; ++idim) {
        if (nn[idim] <= 0) {
            goto normalize;
        }
        ntot *= nn[idim];
    }

    // Main loop for each dimension.
    np1 = 2;
    for (int idim = 0; idim < ndim; ++idim) {
        int n = nn[idim];
        np2 = np1 * n;
        if (n < 1) {
            goto normalize;
        }
        if (n == 1) {
            // Nothing to transform along this dimension.
            np0 = np1;
            np1 = np2;
            nprev = n;
            continue;
        }

        // Is n a power of two, and if not, what are its factors?
        int m = n;
        int ntwo = np1;
        int if_ = 0;
        int idiv = 2;
        int iquot = 0, irem = 0;
        bool prime_tail = false;
        for (;;) {
            iquot = m / idiv;
            irem = m - idiv * iquot;
            if (iquot < idiv) {
                prime_tail = true;
                break;
            }
            if (irem != 0) {
                break;
            }
            ntwo += ntwo;
            ifact[if_++] = idiv;
            m = iquot;
        }

        int inon2;
        if (prime_tail) {
            inon2 = if_;
            if (irem == 0) {
                ntwo += ntwo;
            } else {
                ifact[if_++] = m;
            }
        } else {
            idiv = 3;
            inon2 = if_;
            for (;;) {
                iquot = m / idiv;
                irem = m - idiv * iquot;
                if (iquot < idiv) {
                    break;
                }
                if (irem == 0) {
                    ifact[if_++] = idiv;
                    m = iquot;
                } else {
                    idiv += 2;
                }
            }
            ifact[if_++] = m;
        }
        int non2p = np2 / ntwo;

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
        int ifmin = 0;
        int i1rng = np1;
        int icase;
        if (!(iform <= 0 && idim < 3)) {
            icase = 1;
        } else if (idim > 0) {
            icase = 2;
            i1rng = np0 * (1 + nprev / 2);
        } else if (ntwo <= np1) {
            icase = 3;
        } else {
            icase = 4;
            ifmin = 1;
            ntwo /= 2;
            n /= 2;
            np2 /= 2;
            ntot /= 2;
            for (int j = 0; j < ntot; ++j) {
                data[j] = data[2 * j];
            }
        }

        // Shuffle data by bit reversal (n a power of two: non2p<=1, no
        // working array needed) or by digit reversal for general n.
        if (non2p <= 1) {
            int np2hf = np2 / 2;
            int j = 0;
            for (int i2 = 0; i2 < np2; i2 += np1) {
                if (j < i2) {
                    int i1max = i2 + np1 - 2;
                    for (int i1 = i2; i1 <= i1max; i1 += 2) {
                        for (int i3 = i1; i3 < ntot; i3 += np2) {
                            int j3 = j + i3 - i2;
                            double tempr = data[i3];
                            double tempi = data[i3 + 1];
                            data[i3] = data[j3];
                            data[i3 + 1] = data[j3 + 1];
                            data[j3] = tempr;
                            data[j3 + 1] = tempi;
                        }
                    }
                }
                int m2 = np2hf;
                // Careful: this is `J-M` compared against the literal 0 in
                // the Fortran, with J a shifted (0-based) position and M an
                // unshifted stride -- the comparison boundary itself shifts
                // (J<=M, not J<M, is the 0-based "stop" condition here).
                while (j >= m2) {
                    j -= m2;
                    m2 /= 2;
                    if (m2 < np1) {
                        break;
                    }
                }
                j += m2;
            }
        } else {
            int nwork = 2 * n;
            for (int i1 = 0; i1 < np1; i1 += 2) {
                for (int i3 = i1; i3 < ntot; i3 += np2) {
                    int j = i3;
                    for (int i = 0; i < nwork; i += 2) {
                        if (icase == 3) {
                            work[i] = data[j];
                            work[i + 1] = 0.0;
                        } else {
                            work[i] = data[j];
                            work[i + 1] = data[j + 1];
                        }
                        int ifp2 = np2;
                        int ifx = ifmin;
                        for (;;) {
                            int ifp1 = ifp2 / ifact[ifx];
                            j += ifp1;
                            if (j < i3 + ifp2) {
                                break;
                            }
                            j -= ifp2;
                            ifp2 = ifp1;
                            ifx += 1;
                            if (ifp2 <= np1) {
                                break;
                            }
                        }
                    }
                    int i2max = i3 + np2 - np1;
                    int i = 0;
                    for (int i2 = i3; i2 <= i2max; i2 += np1) {
                        data[i2] = work[i];
                        data[i2 + 1] = work[i + 1];
                        i += 2;
                    }
                }
            }
        }

        // Main loop for factors of two. w=exp(isign*2*pi*sqrt(-1)*m /
        // (4*mmax)); check for w=isign*sqrt(-1) and repeat for
        // w=w*(1+isign*sqrt(-1))/sqrt(2).
        if (ntwo > np1) {
            int np1tw = np1 + np1;
            int ipar = ntwo / np1;
            while (ipar > 2) {
                ipar /= 4;
            }

            if (ipar == 2) {
                for (int i1 = 0; i1 < i1rng; i1 += 2) {
                    for (int k1 = i1; k1 < ntot; k1 += np1tw) {
                        int k2 = k1 + np1;
                        double tempr = data[k2];
                        double tempi = data[k2 + 1];
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
            for (int mmax = np1; mmax < ntwo / 2; mmax += mmax) {
                int lmax = np1tw > mmax / 2 ? np1tw : mmax / 2;
                bool use_twiddle = mmax > np1;
                double wr = 0.0, wi = 0.0;

                for (int l = np1; l <= lmax; l += np1tw) {
                    int m = l;
                    if (use_twiddle) {
                        double theta = -twopi * (double)l / (double)(4 * mmax);
                        if (isign >= 0) {
                            theta = -theta;
                        }
                        wr = cos(theta);
                        wi = sin(theta);
                    }

                    for (;;) {
                        double w2r = 0.0, w2i = 0.0, w3r = 0.0, w3i = 0.0;
                        if (use_twiddle) {
                            w2r = wr * wr - wi * wi;
                            w2i = 2.0 * wr * wi;
                            w3r = w2r * wr - w2i * wi;
                            w3i = w2r * wi + w2i * wr;
                        }

                        for (int i1 = 0; i1 < i1rng; i1 += 2) {
                            // See the file comment: l/m keep their Fortran
                            // numeric values on purpose, so this matches
                            // `I1+IPAR*M` from the original exactly once i1
                            // is the (now 0-based) position.
                            int kmin = use_twiddle ? i1 + ipar * m : i1;
                            int kdif = ipar * mmax;
                            for (int kstep = 4 * kdif; kstep <= ntwo; kdif = kstep, kstep = 4 * kdif) {
                                for (int k1 = kmin; k1 < ntot; k1 += kstep) {
                                    int k2 = k1 + kdif;
                                    int k3 = k2 + kdif;
                                    int k4 = k3 + kdif;
                                    double u1r, u1i, u2r, u2i, u3r, u3i, u4r, u4i;
                                    if (!use_twiddle) {
                                        u1r = data[k1] + data[k2];
                                        u1i = data[k1 + 1] + data[k2 + 1];
                                        u2r = data[k3] + data[k4];
                                        u2i = data[k3 + 1] + data[k4 + 1];
                                        u3r = data[k1] - data[k2];
                                        u3i = data[k1 + 1] - data[k2 + 1];
                                        if (isign < 0) {
                                            u4r = data[k3 + 1] - data[k4 + 1];
                                            u4i = data[k4] - data[k3];
                                        } else {
                                            u4r = data[k4 + 1] - data[k3 + 1];
                                            u4i = data[k3] - data[k4];
                                        }
                                    } else {
                                        double t2r = w2r * data[k2] - w2i * data[k2 + 1];
                                        double t2i = w2r * data[k2 + 1] + w2i * data[k2];
                                        double t3r = wr * data[k3] - wi * data[k3 + 1];
                                        double t3i = wr * data[k3 + 1] + wi * data[k3];
                                        double t4r = w3r * data[k4] - w3i * data[k4 + 1];
                                        double t4i = w3r * data[k4 + 1] + w3i * data[k4];
                                        u1r = data[k1] + t2r;
                                        u1i = data[k1 + 1] + t2i;
                                        u2r = t3r + t4r;
                                        u2i = t3i + t4i;
                                        u3r = data[k1] - t2r;
                                        u3i = data[k1 + 1] - t2i;
                                        if (isign < 0) {
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
                                kmin = 4 * (kmin - i1) + i1;
                            }
                        }

                        m += lmax;
                        if (m > mmax) {
                            break;
                        }
                        double tempr = wr;
                        if (isign < 0) {
                            wr = (wr + wi) * rthlf;
                            wi = (wi - tempr) * rthlf;
                        } else {
                            wr = (wr - wi) * rthlf;
                            wi = (tempr + wi) * rthlf;
                        }
                    }
                }

                ipar = 3 - ipar;
            }
        }

        // Main loop for factors not equal to two. w=exp(isign*2*pi*sqrt(-1)
        // *(j1+j2-i3-1)/ifp2).
        if (non2p > 1) {
            int ifp1 = ntwo;
            int ifx = inon2;
            for (;;) {
                int ifp2 = ifact[ifx] * ifp1;
                double theta = -twopi / (double)ifact[ifx];
                if (isign >= 0) {
                    theta = -theta;
                }
                double thtm = theta / (double)(ifp1 / np1);
                double wstpr = cos(theta);
                double wstpi = sin(theta);
                double wmstr = cos(thtm);
                double wmsti = sin(thtm);
                double wminr = 1.0;
                double wmini = 0.0;

                for (int j1 = 0; j1 < ifp1; j1 += np1) {
                    int i1max = j1 + i1rng - 2;
                    for (int i1 = j1; i1 <= i1max; i1 += 2) {
                        for (int i3 = i1; i3 < ntot; i3 += np2) {
                            int i = 0;
                            double wr = wminr, wi = wmini;
                            int j2max = i3 + ifp2 - ifp1;
                            for (int j2 = i3; j2 <= j2max; j2 += ifp1) {
                                double twowr = wr + wr;
                                int jmin = i3;
                                int j3max = j2 + np2 - ifp2;
                                for (int j3 = j2; j3 <= j3max; j3 += ifp2) {
                                    int j = jmin + ifp2 - ifp1;
                                    double sr = data[j];
                                    double si = data[j + 1];
                                    double oldsr = 0.0, oldsi = 0.0;
                                    j -= ifp1;
                                    while (j > jmin) {
                                        double stmpr = sr, stmpi = si;
                                        sr = twowr * sr - oldsr + data[j];
                                        si = twowr * si - oldsi + data[j + 1];
                                        oldsr = stmpr;
                                        oldsi = stmpi;
                                        j -= ifp1;
                                    }
                                    work[i] = wr * sr - wi * si - oldsr + data[j];
                                    work[i + 1] = wi * sr + wr * si - oldsi + data[j + 1];
                                    jmin += ifp2;
                                    i += 2;
                                }
                                double wtemp = wr * wstpi;
                                wr = wr * wstpr - wi * wstpi;
                                wi = wi * wstpr + wtemp;
                            }
                            i = 0;
                            for (int j2 = i3; j2 <= j2max; j2 += ifp1) {
                                int j3max = j2 + np2 - ifp2;
                                for (int j3 = j2; j3 <= j3max; j3 += ifp2) {
                                    data[j3] = work[i];
                                    data[j3 + 1] = work[i + 1];
                                    i += 2;
                                }
                            }
                        }
                    }
                    double wtemp = wminr * wmsti;
                    wminr = wminr * wmstr - wmini * wmsti;
                    wmini = wmini * wmstr + wtemp;
                }

                ifx += 1;
                ifp1 = ifp2;
                if (ifp1 >= np2) {
                    break;
                }
            }
        }

        // Dispatch on which of the four cases above we're completing.
        if (icase == 2) {
            // Complete a real transform for the 2nd, 3rd, etc. dimension by
            // conjugate symmetries.
            if (i1rng < np1) {
                for (int i3 = 0; i3 < ntot; i3 += np2) {
                    int i2max = i3 + np2 - np1;
                    for (int i2 = i3; i2 <= i2max; i2 += np1) {
                        int imax = i2 + np1 - 2;
                        int imin = i2 + i1rng;
                        int jmax = 2 * i3 + np1 - imin + (i2 > i3 ? np2 : 0);
                        int j;
                        if (idim > 1) {
                            j = jmax + np0;
                            for (int i = imin; i <= imax; i += 2) {
                                data[i] = data[j];
                                data[i + 1] = -data[j + 1];
                                j -= 2;
                            }
                        }
                        j = jmax;
                        for (int i = imin; i <= imax; i += np0) {
                            data[i] = data[j];
                            data[i + 1] = -data[j + 1];
                            j -= np0;
                        }
                    }
                }
            }
        } else if (icase == 4) {
            // Complete a real transform in the 1st dimension, n even, by
            // conjugate symmetries.
            int nhalf = n;
            n += n;
            double theta = -twopi / (double)n;
            if (isign >= 0) {
                theta = -theta;
            }
            double wstpr = cos(theta);
            double wstpi = sin(theta);
            double wr = wstpr, wi = wstpi;
            int imin = 2;
            int jmin = 2 * nhalf - 2;

            while (imin < jmin) {
                int j = jmin;
                for (int i = imin; i < ntot; i += np2) {
                    double sumr = (data[i] + data[j]) / 2.0;
                    double sumi = (data[i + 1] + data[j + 1]) / 2.0;
                    double difr = (data[i] - data[j]) / 2.0;
                    double difi = (data[i + 1] - data[j + 1]) / 2.0;
                    double tempr = wr * sumi + wi * difr;
                    double tempi = wi * sumi - wr * difr;
                    data[i] = sumr + tempr;
                    data[i + 1] = difi + tempi;
                    data[j] = sumr - tempr;
                    data[j + 1] = -difi + tempi;
                    j += np2;
                }
                imin += 2;
                jmin -= 2;
                double wtemp = wr * wstpi;
                wr = wr * wstpr - wi * wstpi;
                wi = wi * wstpr + wtemp;
            }

            if (imin == jmin && isign < 0) {
                for (int i = imin; i < ntot; i += np2) {
                    data[i + 1] = -data[i + 1];
                }
            }

            np2 += np2;
            ntot += ntot;
            int j = ntot;
            int imax = ntot / 2;
            // Sweep inward from both ends of the (now doubled) buffer,
            // mirroring the first half into the second half by conjugate
            // symmetry, shrinking the swept range (via imax=imin) each pass
            // until the two ends meet.
            for (;;) {
                imin = imax - 2 * nhalf;
                int i = imin;
                for (;;) {
                    i += 2;
                    j -= 2;
                    if (i >= imax) {
                        break;
                    }
                    data[j] = data[i];
                    data[j + 1] = -data[i + 1];
                }
                data[j] = data[imin] - data[imin + 1];
                data[j + 1] = 0.0;
                if (i >= j) {
                    break;
                }
                for (;;) {
                    i -= 2;
                    j -= 2;
                    if (i <= imin) {
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

normalize:
    if (isign == 1) {
        return;
    }
    int ntot2 = 2;
    for (int idim = 0; idim < ndim; ++idim) {
        ntot2 *= nn[idim];
    }
    int ntothf = ntot2 / 2;
    for (int itot = 0; itot < ntot2; ++itot) {
        data[itot] /= ntothf;
    }
}
