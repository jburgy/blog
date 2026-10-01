#include <math.h>

#define DATA(i) data[(i) - 1]
#define NN(i) nn[(i) - 1]
#define WORK(i) work[(i) - 1]
#define IFACT(i) ifact[(i) - 1]

void fourt_(double *data, int *nn, int ndim, int isign, int iform, double *work) {
    int ifact[32];

    double twopi, rthlf;
    double theta, thtm, wstpr, wstpi, wminr, wmini, wmstr, wmsti;
    double wr, wi, w2r, w2i, w3r, w3i, wtemp, twowr;
    double tempr, tempi, t2r, t2i, t3r, t3i, t4r, t4i;
    double u1r, u1i, u2r, u2i, u3r, u3i, u4r, u4i;
    double sr, si, oldsr, oldsi, stmpr, stmpi;
    double sumr, sumi, difr, difi;

    int np0, np1, np2, np2hf, np1tw, nprev, ntot, ntwo, non2p;
    int idim, n, m, if_, idiv, iquot, irem, inon2;
    int ifmin, i1rng, icase, nwork, ifp1, ifp2;
    int i, i1, i1max, i2, i2max, i3, imin, imax, itot;
    int j, j1, j2, j2max, j3, j3max, jmax, jmin;
    int ipar, mmax, lmax, l, k1, k2, k3, k4, kmin, kdif, kstep;
    int nhalf, ntothf;

    twopi = 8.0 * atan(1.0);
    rthlf = sqrt(0.5);
    np0 = 0;
    nprev = 0;

    if (ndim - 1 < 0) {
        goto L920;
    }
    goto L1;

L1: /* Fortran label 1 */
    ntot = 2;
    for (idim = 1; idim <= ndim; ++idim) {
        if (NN(idim) <= 0) {
            goto L920;
        }
L2:    /* Fortran label 2 */
        ntot = ntot * NN(idim);
    }

    np1 = 2;
    for (idim = 1; idim <= ndim; ++idim) {
        n = NN(idim);
        np2 = np1 * n;
        if (n - 1 < 0) {
            goto L920;
        } else if (n - 1 == 0) {
            goto L900;
        } else {
            goto L5;
        }

L5:     /* Fortran label 5 */
        m = n;
        ntwo = np1;
        if_ = 1;
        idiv = 2;

L10:    /* Fortran label 10 */
        iquot = m / idiv;
        irem = m - idiv * iquot;
        if (iquot - idiv < 0) {
            goto L50;
        } else {
            goto L11;
        }

L11:    /* Fortran label 11 */
        if (irem < 0) {
            goto L20;
        } else if (irem == 0) {
            goto L12;
        } else {
            goto L20;
        }

L12:    /* Fortran label 12 */
        ntwo = ntwo + ntwo;
        IFACT(if_) = idiv;
        if_ = if_ + 1;
        m = iquot;
        goto L10;

L20:    /* Fortran label 20 */
        idiv = 3;
        inon2 = if_;

L30:    /* Fortran label 30 */
        iquot = m / idiv;
        irem = m - idiv * iquot;
        if (iquot - idiv < 0) {
            goto L60;
        } else {
            goto L31;
        }

L31:    /* Fortran label 31 */
        if (irem < 0) {
            goto L40;
        } else if (irem == 0) {
            goto L32;
        } else {
            goto L40;
        }

L32:    /* Fortran label 32 */
        IFACT(if_) = idiv;
        if_ = if_ + 1;
        m = iquot;
        goto L30;

L40:    /* Fortran label 40 */
        idiv = idiv + 2;
        goto L30;

L50:    /* Fortran label 50 */
        inon2 = if_;
        if (irem < 0) {
            goto L60;
        } else if (irem == 0) {
            goto L51;
        } else {
            goto L60;
        }

L51:    /* Fortran label 51 */
        ntwo = ntwo + ntwo;
        goto L70;

L60:    /* Fortran label 60 */
        IFACT(if_) = m;

L70:    /* Fortran label 70 */
        non2p = np2 / ntwo;
        ifmin = 1;
        i1rng = np1;
        if (iform <= 0 && idim < 4) {
            goto L71;
        }
        icase = 1;
        goto L100;

L71:    /* Fortran label 71 */
        if (idim <= 1) {
            goto L72;
        }
        icase = 2;
        i1rng = np0 * (1 + nprev / 2);
        goto L100;

L72:    /* Fortran label 72 */
        if (ntwo > np1) {
            goto L73;
        }
        icase = 3;
        goto L100;

L73:    /* Fortran label 73 */
        icase = 4;
        ifmin = 2;
        ntwo = ntwo / 2;
        n = n / 2;
        np2 = np2 / 2;
        ntot = ntot / 2;

        i = -1;
        for (j = 1; j <= ntot; ++j) {
            i = i + 2;
            DATA(j) = DATA(i);
L80:        /* Fortran label 80 */
            ;
        }

L100:   /* Fortran label 100 */
        if (non2p - 1 <= 0) {
            goto L101;
        }
        goto L200;

L101:   /* Fortran label 101 */
        np2hf = np2 / 2;
        j = 1;
        for (i2 = 1; i2 <= np2; i2 += np1) {
            if (j - i2 < 0) {
                goto L121;
            }
            goto L130;

L121:       /* Fortran label 121 */
            i1max = i2 + np1 - 2;
            for (i1 = i2; i1 <= i1max; i1 += 2) {
                for (i3 = i1; i3 <= ntot; i3 += np2) {
                    j3 = j + i3 - i2;
                    tempr = DATA(i3);
                    tempi = DATA(i3 + 1);
                    DATA(i3) = DATA(j3);
                    DATA(i3 + 1) = DATA(j3 + 1);
                    DATA(j3) = tempr;
L125:               /* Fortran label 125 */
                    DATA(j3 + 1) = tempi;
                }
            }

L130:       /* Fortran label 130 */
            m = np2hf;
L140:       /* Fortran label 140 */
            if (j - m <= 0) {
                goto L150;
            }

L141:       /* Fortran label 141 */
            j = j - m;
            m = m / 2;
            if (m - np1 < 0) {
                goto L150;
            }
            goto L140;

L150:       /* Fortran label 150 */
            j = j + m;
        }
        goto L300;

L200:   /* Fortran label 200 */
        nwork = 2 * n;
        for (i1 = 1; i1 <= np1; i1 += 2) {
            for (i3 = i1; i3 <= ntot; i3 += np2) {
                j = i3;
                for (i = 1; i <= nwork; i += 2) {
                    if (icase - 3 < 0) {
                        goto L210;
                    } else if (icase - 3 == 0) {
                        goto L220;
                    } else {
                        goto L210;
                    }

L210:               /* Fortran label 210 */
                    WORK(i) = DATA(j);
                    WORK(i + 1) = DATA(j + 1);
                    goto L240;

L220:               /* Fortran label 220 */
                    WORK(i) = DATA(j);
                    WORK(i + 1) = 0.0;

L240:               /* Fortran label 240 */
                    ifp2 = np2;
                    if_ = ifmin;
L250:               /* Fortran label 250 */
                    ifp1 = ifp2 / IFACT(if_);
                    j = j + ifp1;
                    if (j - i3 - ifp2 < 0) {
                        goto L260;
                    }
                    goto L255;

L255:               /* Fortran label 255 */
                    j = j - ifp2;
                    ifp2 = ifp1;
                    if_ = if_ + 1;
                    if (ifp2 - np1 <= 0) {
                        goto L260;
                    }
                    goto L250;

L260:               /* Fortran label 260 */
                    ;
                }
                i2max = i3 + np2 - np1;
                i = 1;
                for (i2 = i3; i2 <= i2max; i2 += np1) {
                    DATA(i2) = WORK(i);
                    DATA(i2 + 1) = WORK(i + 1);
L270:               /* Fortran label 270 */
                    i = i + 2;
                }
            }
        }

L300:   /* Fortran label 300 */
        if (ntwo - np1 <= 0) {
            goto L600;
        }
        goto L305;

L305:   /* Fortran label 305 */
        np1tw = np1 + np1;
        ipar = ntwo / np1;

L310:   /* Fortran label 310 */
        if (ipar - 2 < 0) {
            goto L350;
        } else if (ipar - 2 == 0) {
            goto L330;
        } else {
            goto L320;
        }

L320:   /* Fortran label 320 */
        ipar = ipar / 4;
        goto L310;

L330:   /* Fortran label 330 */
        for (i1 = 1; i1 <= i1rng; i1 += 2) {
            for (k1 = i1; k1 <= ntot; k1 += np1tw) {
                k2 = k1 + np1;
                tempr = DATA(k2);
                tempi = DATA(k2 + 1);
                DATA(k2) = DATA(k1) - tempr;
                DATA(k2 + 1) = DATA(k1 + 1) - tempi;
                DATA(k1) = DATA(k1) + tempr;
L340:           /* Fortran label 340 */
                DATA(k1 + 1) = DATA(k1 + 1) + tempi;
            }
        }

L350:   /* Fortran label 350 */
        mmax = np1;
L360:   /* Fortran label 360 */
        if (mmax - ntwo / 2 < 0) {
            goto L370;
        }
        goto L600;

L370:   /* Fortran label 370 */
        lmax = (np1tw > mmax / 2) ? np1tw : (mmax / 2);
        for (l = np1; l <= lmax; l += np1tw) {
            m = l;
            if (mmax - np1 <= 0) {
                goto L420;
            }

L380:       /* Fortran label 380 */
            theta = -twopi * (double)l / (double)(4 * mmax);
            if (isign < 0) {
                goto L400;
            }

L390:       /* Fortran label 390 */
            theta = -theta;

L400:       /* Fortran label 400 */
            wr = cos(theta);
            wi = sin(theta);

L410:       /* Fortran label 410 */
            w2r = wr * wr - wi * wi;
            w2i = 2.0 * wr * wi;
            w3r = w2r * wr - w2i * wi;
            w3i = w2r * wi + w2i * wr;

L420:       /* Fortran label 420 */
            for (i1 = 1; i1 <= i1rng; i1 += 2) {
                kmin = i1 + ipar * m;
                if (mmax - np1 <= 0) {
                    goto L430;
                }
                goto L440;

L430:           /* Fortran label 430 */
                kmin = i1;

L440:           /* Fortran label 440 */
                kdif = ipar * mmax;
L450:           /* Fortran label 450 */
                kstep = 4 * kdif;
                if (kstep - ntwo <= 0) {
                    goto L460;
                }
                goto L530;

L460:           /* Fortran label 460 */
                for (k1 = kmin; k1 <= ntot; k1 += kstep) {
                    k2 = k1 + kdif;
                    k3 = k2 + kdif;
                    k4 = k3 + kdif;
                    if (mmax - np1 <= 0) {
                        goto L470;
                    }
                    goto L480;

L470:               /* Fortran label 470 */
                    u1r = DATA(k1) + DATA(k2);
                    u1i = DATA(k1 + 1) + DATA(k2 + 1);
                    u2r = DATA(k3) + DATA(k4);
                    u2i = DATA(k3 + 1) + DATA(k4 + 1);
                    u3r = DATA(k1) - DATA(k2);
                    u3i = DATA(k1 + 1) - DATA(k2 + 1);
                    if (isign < 0) {
                        goto L471;
                    }
                    goto L472;

L471:               /* Fortran label 471 */
                    u4r = DATA(k3 + 1) - DATA(k4 + 1);
                    u4i = DATA(k4) - DATA(k3);
                    goto L510;

L472:               /* Fortran label 472 */
                    u4r = DATA(k4 + 1) - DATA(k3 + 1);
                    u4i = DATA(k3) - DATA(k4);
                    goto L510;

L480:               /* Fortran label 480 */
                    t2r = w2r * DATA(k2) - w2i * DATA(k2 + 1);
                    t2i = w2r * DATA(k2 + 1) + w2i * DATA(k2);
                    t3r = wr * DATA(k3) - wi * DATA(k3 + 1);
                    t3i = wr * DATA(k3 + 1) + wi * DATA(k3);
                    t4r = w3r * DATA(k4) - w3i * DATA(k4 + 1);
                    t4i = w3r * DATA(k4 + 1) + w3i * DATA(k4);
                    u1r = DATA(k1) + t2r;
                    u1i = DATA(k1 + 1) + t2i;
                    u2r = t3r + t4r;
                    u2i = t3i + t4i;
                    u3r = DATA(k1) - t2r;
                    u3i = DATA(k1 + 1) - t2i;
                    if (isign < 0) {
                        goto L490;
                    }
                    goto L500;

L490:               /* Fortran label 490 */
                    u4r = t3i - t4i;
                    u4i = t4r - t3r;
                    goto L510;

L500:               /* Fortran label 500 */
                    u4r = t4i - t3i;
                    u4i = t3r - t4r;

L510:               /* Fortran label 510 */
                    DATA(k1) = u1r + u2r;
                    DATA(k1 + 1) = u1i + u2i;
                    DATA(k2) = u3r + u4r;
                    DATA(k2 + 1) = u3i + u4i;
                    DATA(k3) = u1r - u2r;
                    DATA(k3 + 1) = u1i - u2i;
                    DATA(k4) = u3r - u4r;
L520:               /* Fortran label 520 */
                    DATA(k4 + 1) = u3i - u4i;
                }
                kdif = kstep;
                kmin = 4 * (kmin - i1) + i1;
                goto L450;
            }

L530:       /* Fortran label 530 */
            m = m + lmax;
            if (m - mmax <= 0) {
                goto L540;
            }
            goto L570;

L540:       /* Fortran label 540 */
            if (isign < 0) {
                goto L550;
            }
            goto L560;

L550:       /* Fortran label 550 */
            tempr = wr;
            wr = (wr + wi) * rthlf;
            wi = (wi - tempr) * rthlf;
            goto L410;

L560:       /* Fortran label 560 */
            tempr = wr;
            wr = (wr - wi) * rthlf;
            wi = (tempr + wi) * rthlf;
            goto L410;

L570:       /* Fortran label 570 */
            ;
        }
        ipar = 3 - ipar;
        mmax = mmax + mmax;
        goto L360;

L600:   /* Fortran label 600 */
        if (non2p - 1 <= 0) {
            goto L700;
        }
        goto L601;

L601:   /* Fortran label 601 */
        ifp1 = ntwo;
        if_ = inon2;

L610:   /* Fortran label 610 */
        ifp2 = IFACT(if_) * ifp1;
        theta = -twopi / (double)IFACT(if_);
        if (isign >= 0) {
L611:       /* Fortran label 611 */
            theta = -theta;
        } else {
L612:       /* Fortran label 612 */
            ;
        }
        thtm = theta / (double)(ifp1 / np1);
        wstpr = cos(theta);
        wstpi = sin(theta);
        wmstr = cos(thtm);
        wmsti = sin(thtm);
        wminr = 1.0;
        wmini = 0.0;
        for (j1 = 1; j1 <= ifp1; j1 += np1) {
L613:       /* Fortran label 613 */
L614:       /* Fortran label 614 */
            i1max = j1 + i1rng - 2;
            for (i1 = j1; i1 <= i1max; i1 += 2) {
                for (i3 = i1; i3 <= ntot; i3 += np2) {
                    i = 1;
                    wr = wminr;
                    wi = wmini;
                    j2max = i3 + ifp2 - ifp1;
                    for (j2 = i3; j2 <= j2max; j2 += ifp1) {
                        twowr = wr + wr;
                        jmin = i3;
                        j3max = j2 + np2 - ifp2;
                        for (j3 = j2; j3 <= j3max; j3 += ifp2) {
                            j = jmin + ifp2 - ifp1;
                            sr = DATA(j);
                            si = DATA(j + 1);
                            oldsr = 0.0;
                            oldsi = 0.0;
                            j = j - ifp1;

L620:                       /* Fortran label 620 */
                            stmpr = sr;
                            stmpi = si;
                            sr = twowr * sr - oldsr + DATA(j);
                            si = twowr * si - oldsi + DATA(j + 1);
                            oldsr = stmpr;
                            oldsi = stmpi;
                            j = j - ifp1;
                            if (j - jmin <= 0) {
                                goto L621;
                            }
                            goto L620;

L621:                       /* Fortran label 621 */
                            WORK(i) = wr * sr - wi * si - oldsr + DATA(j);
                            WORK(i + 1) = wi * sr + wr * si - oldsi + DATA(j + 1);
                            jmin = jmin + ifp2;

L630:                       /* Fortran label 630 */
                            i = i + 2;
                        }

                        wtemp = wr * wstpi;
                        wr = wr * wstpr - wi * wstpi;
L640:                   /* Fortran label 640 */
                        wi = wi * wstpr + wtemp;
                    }
                    i = 1;
                    for (j2 = i3; j2 <= j2max; j2 += ifp1) {
                        j3max = j2 + np2 - ifp2;
                        for (j3 = j2; j3 <= j3max; j3 += ifp2) {
                            DATA(j3) = WORK(i);
                            DATA(j3 + 1) = WORK(i + 1);
                            i = i + 2;
                        }
                    }
                }
            }
            wtemp = wminr * wmsti;
            wminr = wminr * wmstr - wmini * wmsti;
L650:       /* Fortran label 650 */
            wmini = wmini * wmstr + wtemp;
        }
        if_ = if_ + 1;
        ifp1 = ifp2;
        if (ifp1 - np2 < 0) {
            goto L610;
        }
        goto L700;

L700:   /* Fortran label 700 */
        switch (icase) {
            case 1:
                goto L900;
            case 2:
                goto L800;
            case 3:
                goto L900;
            case 4:
                goto L701;
            default:
                goto L900;
        }

L701:   /* Fortran label 701 */
        nhalf = n;
        n = n + n;
        theta = -twopi / (double)n;
        if (isign < 0) {
            goto L703;
        }

L702:   /* Fortran label 702 */
        theta = -theta;

L703:   /* Fortran label 703 */
        wstpr = cos(theta);
        wstpi = sin(theta);
        wr = wstpr;
        wi = wstpi;
        imin = 3;
        jmin = 2 * nhalf - 1;
        goto L725;

L710:   /* Fortran label 710 */
        j = jmin;
        for (i = imin; i <= ntot; i += np2) {
            sumr = (DATA(i) + DATA(j)) / 2.0;
            sumi = (DATA(i + 1) + DATA(j + 1)) / 2.0;
            difr = (DATA(i) - DATA(j)) / 2.0;
            difi = (DATA(i + 1) - DATA(j + 1)) / 2.0;
            tempr = wr * sumi + wi * difr;
            tempi = wi * sumi - wr * difr;
            DATA(i) = sumr + tempr;
            DATA(i + 1) = difi + tempi;
            DATA(j) = sumr - tempr;
            DATA(j + 1) = -difi + tempi;
L720:       /* Fortran label 720 */
            j = j + np2;
        }
        imin = imin + 2;
        jmin = jmin - 2;
        wtemp = wr * wstpi;
        wr = wr * wstpr - wi * wstpi;
        wi = wi * wstpr + wtemp;

L725:   /* Fortran label 725 */
        if (imin - jmin < 0) {
            goto L710;
        } else if (imin - jmin == 0) {
            goto L730;
        }
        goto L740;

L730:   /* Fortran label 730 */
        if (isign < 0) {
            goto L731;
        }
        goto L740;

L731:   /* Fortran label 731 */
        for (i = imin; i <= ntot; i += np2) {
L735:       /* Fortran label 735 */
            DATA(i + 1) = -DATA(i + 1);
        }

L740:   /* Fortran label 740 */
        np2 = np2 + np2;
        ntot = ntot + ntot;
        j = ntot + 1;
        imax = ntot / 2 + 1;

L745:   /* Fortran label 745 */
        imin = imax - 2 * nhalf;
        i = imin;
        goto L755;

L750:   /* Fortran label 750 */
        DATA(j) = DATA(i);
        DATA(j + 1) = -DATA(i + 1);

L755:   /* Fortran label 755 */
        i = i + 2;
        j = j - 2;
        if (i - imax < 0) {
            goto L750;
        }
        goto L760;

L760:   /* Fortran label 760 */
        DATA(j) = DATA(imin) - DATA(imin + 1);
        DATA(j + 1) = 0.0;
        if (i - j < 0) {
            goto L770;
        }
        goto L780;

L765:   /* Fortran label 765 */
        DATA(j) = DATA(i);
        DATA(j + 1) = DATA(i + 1);

L770:   /* Fortran label 770 */
        i = i - 2;
        j = j - 2;
        if (i - imin <= 0) {
            goto L775;
        }
        goto L765;

L775:   /* Fortran label 775 */
        DATA(j) = DATA(imin) + DATA(imin + 1);
        DATA(j + 1) = 0.0;
        imax = imin;
        goto L745;

L780:   /* Fortran label 780 */
        DATA(1) = DATA(1) + DATA(2);
        DATA(2) = 0.0;
        goto L900;

L800:   /* Fortran label 800 -- NOTE: only reached when ndim>1 (ICASE=2 is
         * selected earlier only for IDIM>1; see the IDIM.LE.1 check near the
         * top of the per-dimension loop). fourt2py/web always calls this
         * function with ndim=1, and fourt2py's f2py binding -- the oracle
         * used to validate this port against the real Fortran -- only
         * accepts rank-1 arrays, so this branch has no test coverage here.
         * Kept for fidelity to the original multi-dimensional FOURT.F rather
         * than trimming untested code from an otherwise fully validated,
         * literal transliteration; validate against a multi-dimensional
         * oracle before relying on it. */
        if (i1rng - np1 < 0) {
            goto L805;
        }
        goto L900;

L805:   /* Fortran label 805 */
        for (i3 = 1; i3 <= ntot; i3 += np2) {
            i2max = i3 + np2 - np1;
            for (i2 = i3; i2 <= i2max; i2 += np1) {
                imax = i2 + np1 - 2;
                imin = i2 + i1rng;
                jmax = 2 * i3 + np1 - imin;
                if (i2 - i3 < 0) {
                    goto L820;
                } else if (i2 - i3 == 0) {
                    goto L820;
                }
                goto L810;

L810:           /* Fortran label 810 */
                jmax = jmax + np2;

L820:           /* Fortran label 820 */
                if (idim - 2 <= 0) {
                    goto L850;
                }
                goto L830;

L830:           /* Fortran label 830 */
                j = jmax + np0;
                for (i = imin; i <= imax; i += 2) {
                    DATA(i) = DATA(j);
                    DATA(i + 1) = -DATA(j + 1);
L840:               /* Fortran label 840 */
                    j = j - 2;
                }

L850:           /* Fortran label 850 */
                j = jmax;
                for (i = imin; i <= imax; i += np0) {
                    DATA(i) = DATA(j);
                    DATA(i + 1) = -DATA(j + 1);
L860:               /* Fortran label 860 */
                    j = j - np0;
                }
            }
        }

L900:   /* Fortran label 900 */
        np0 = np1;
        np1 = np2;

L910:   /* Fortran label 910 */
        nprev = n;
    }

L920:   /* Fortran label 920 */
    if (isign == 1) {
        return;
    }
    ntot = 2;
    for (idim = 1; idim <= ndim; ++idim) {
L930:   /* Fortran label 930 */
        ntot = ntot * NN(idim);
    }
    ntothf = ntot / 2;
    for (itot = 1; itot <= ntot; ++itot) {
L940:   /* Fortran label 940 */
        DATA(itot) = DATA(itot) / ntothf;
    }
}
