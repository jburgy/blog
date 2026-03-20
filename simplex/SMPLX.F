      SUBROUTINE SMPLX (A,B0,C,KA,M,N0,IND,IBASIS,X,Z,ITER,MXITER,
     *                       NUMLE,NUMGE,BI,WK,IWK)
C-----------------------------------------------------------------------
C     SIMPLEX PROCEDURE FOR SOLVING LINEAR PROGRAMMING PROBLEMS
C-----------------------------------------------------------------------
C     WRITTEN BY ALFRED H. MORRIS JR.
C        NAVAL SURFACE WEAPONS CENTER
C        DAHLGREN, VIRGINIA
C------------------------
C     INITIAL VERSION  DEC  1977
C     LAST UPDATE      OCT  1990
C------------------------
      DIMENSION A(KA,N0),B0(M),C(N0)
      DIMENSION IBASIS(M),BI(M,M)
      DIMENSION X(*),WK(*),IWK(*)
C------------------------
C     DIMENSION X(N0+NUMLE+NUMGE)
C     DIMENSION WK(2*M),IWK(2*M+N0)
C------------------------
C
C     ********** EPS0 IS A MACHINE DEPENDENT PARAMETER. ASSIGN EPS0
C                THE VALUE U WHERE U IS THE SMALLEST POSITIVE FLOATING
C                POINT NUMBER SUCH THAT 1.0 + U .GT. 1.0.
C
                          EPS0 = SPMPAR(1)
C
C------------------------
      RERRMN = 10.0*EPS0
      RERRMX = 1.E-4
      IF (EPS0 .LT. 1.E-13) RERRMX = 1.E-5
C
      IP = M + N0 + 1
      CALL SMPLX1(A,B0,C,KA,M,N0,IND,IBASIS,X,Z,ITER,MXITER,
     1            EPS0,RERRMN,RERRMX,RERR,NUMLE,NUMGE,BI,
     2            WK(1),WK(M+1),IWK(1),IWK(IP))
      RETURN
      END
      SUBROUTINE SMPLX1 (A,B0,C,KA,M,N0,IND,IBASIS,R,Z,ITER,MXITER,
     *     EPS0,RERRMN,RERRMX,RERR,NUMLE,NUMGE,BI,XB,Y,BASIS,INDEX)
C----------------------
C     NSTEP = 1   ELIMINATE THE NEGATIVE VARIABLES
C     NSTEP = 2   PHASE 1 OF THE SIMPLEX ALGORITHM
C     NSTEP = 3   PHASE 2 OF THE SIMPLEX ALGORITHM
C----------------------
C     MXITER = THE MAXIMUM NUMBER OF ITERATIONS PERMITTED
C     ITER = THE NUMBER OF THE CURRENT ITERATION
C     ICOUNT = THE NUMBER OF ITERATIONS SINCE THE LAST INVERSION
C----------------------
C     NUMLE = THE NUMBER OF .LE. CONSTRAINTS
C     NUMGE = THE NUMBER OF .GE. CONSTRAINTS
C----------------------
C     THE ROUTINE ASSUMES THAT THE .LE. CONSTRAINTS PRECEDE THE .GE.
C     CONSTRAINTS AND THAT THE .EQ. CONSTRAINTS COME LAST. THERE ARE
C     M CONSTRAINTS. X(N0+I) IS THE SLACK, SURPLUS, OR ARTIFICIAL
C     VARIABLE FOR THE I-TH CONSTRAINT (I=1,...,M).
C----------------------
C     N0 = THE NUMBER OF ORGINAL VARIABLES
C     NS = THE NUMBER OF ORGINAL AND SLACK VARIABLES
C     N  = THE NUMBER OF ORGINAL, SLACK, AND SURPLUS VARIABLES
C     NUM = THE TOTAL NUMBER OF VARIABLES
C----------------------
C     RERRMN = THE SMALLEST RELATIVE ERROR TOLERANCE USED
C     RERRMX = THE LARGEST RELATIVE ERROR TOLERACE USED
C     RERR   = THE ESTIMATED CURRENT RELATIVE ERROR
C----------------------
C     ASSUME THAT
C         B0 = (B0(1),...,B0(M))
C         C  = (C(1),...,C(N0))
C         Z  = C(1)*X(1)+...+C(N0)*X(N0)
C     THE PROBLEM IS TO MAXIMIZE Z SUBJECT TO
C         AX(LE,EQ,GE)B0
C         X.GE.0
C----------------------
C     ON INPUT IND CAN HAVE THE VALUES
C         IND = 0   NO BEGINNING BASIS IS PROVIDED BY THE USER
C         IND = 1   THE ARRAY IBASIS HAS BEEN SET BY THE USER
C     ON OUTPUT IND IS ASSIGNED ONE OF THE VALUES
C         IND = 0   Z WAS SUCCESSFULLY MAXIMIZED
C         IND = 1   THE PROBLEM HAS NO FEASIBLE SOLUTION
C         IND = 2   MXITER ITERATIONS WERE PERFORMED
C         IND = 3   SUFFICIENT ACCURACY CANNOT BE MAINTAINED
C         IND = 4   THE PROBLEM HAS AN UNBOUNDED SOLUTION
C         IND = 5   THERE IS AN INPUT ERROR
C         IND = 6   Z WAS POSSIBLY MAXIMIZED
C----------------------
C     BASIS IS AN INTEGER ARRAY OF DIMENSION N0+M. FOR J.LE.N
C         BASIS(J) = 1  IF X(J) IS A BASIC VARIABLE
C         BASIS(J) = 0  IF X(J) IS NOT A BASIC VARIABLE
C     IF THE BASIC VARIABLES ARE X(I1),...,X(IM) THEN
C         IBASIS = (I1,...,IM)
C     ALSO XB(1),...,XB(M) ARE THE CORRESPONDING VALUES OF THE
C     BASIC VARIABLES.
C----------------------
C     BI IS AN MXM ARRAY CONTAINING THE INVERSE OF THE BASIS MATRIX.
C----------------------
C     R IS AN ARRAY OF DIMENSION N. ON OUTPUT R CONTAINS THE CURRENT
C     VALUE OF X. DURING COMPUTATION R NORMALLY CONTAINS THE REDUCED
C     COSTS USED FOR THE SELECTION OF THE VARIABLE TO BE MADE BASIC.
C----------------------
      REAL A(KA,N0), B0(M), C(N0)
      REAL BI(M,M), XB(M), Y(M), R(*)
      INTEGER IBASIS(M), BASIS(*)
      INTEGER BFLAG, INDEX(M)
      DOUBLE PRECISION DSUM, DSUMP, DSUMN, DT
C----------------------
C
C     ****** XMAX IS A MACHINE DEPENDENT CONSTANT. XMAX IS THE
C            LARGEST POSITIVE FLOATING POINT NUMBER.
C
                 XMAX = SPMPAR(3)
C
C----------------------
      ITER = 0
      ICOUNT = 0
      MCHECK = MIN0(5,1 + M/15)
      Z = 0.0
C
C                CHECK FOR INPUT ERRORS
C
      MS = NUMLE + NUMGE
      IF (M .LT. 2 .OR. N0 .LT. 2 .OR. MS .GT. M .OR. KA .LT. M)
     *   GO TO 12
      DO 10 I = 1,M
         IF (B0(I) .LT. 0.0) GO TO 12
   10    XB(I) = 0.0
      RTOL = XMAX
      DO 11 I = 1,N0
         IF (C(I) .NE. 0.0) RTOL = AMIN1(ABS(C(I)),RTOL)
   11 CONTINUE
      RTOL = RERRMX*RTOL
      GO TO 20
C
   12 IND = 5
      RETURN
C
C     FORMATION OF THE IBASIS AND BASIS ARRAYS. (IF IND = 1
C     THEN THE IBASIS ARRAY IS DEFINED BY THE USER.)
C
   20 NS = N0 + NUMLE
      N = NS + NUMGE
      IF (IND .EQ. 0) GO TO 30
      NUM = N
      DO 21 I = 1,M
         IF (IBASIS(I) .GT. N) NUM = NUM + 1
   21 CONTINUE
      GO TO 32
   22 IF (IND .EQ. 0) GO TO 590
      IND = 0
C
   30 NUM = N0 + M
      DO 31 I = 1,M
   31    IBASIS(I) = N0 + I
   32 BFLAG = 0
      DO 33 I = 1,N
   33    BASIS(I) = 0
      DO 34 I = 1,M
         KI = IBASIS(I)
   34    BASIS(KI) = 1
      IF (IND .EQ. 1) GO TO 100
C
C          CALCULATION OF XB AND BI WHEN IND = 0
C
      RERR = RERRMN
      DO 41 J = 1,M
         XB(J) = B0(J)
         DO 40 I = 1,M
   40       BI(I,J) = 0.0
         BI(J,J) = 1.0
   41 CONTINUE
      IF (NUMGE .EQ. 0) GO TO 630
      JMIN = NUMLE + 1
      DO 42 J = JMIN,MS
         XB(J) = -XB(J)
         BI(J,J) = -1.0
   42 CONTINUE
      GO TO 601
C
C                  REORDER THE BASIS
C
  100 IBEG = 1
      IEND = M
      DO 102 I = 1,M
         IF (IBASIS(I) .LE. N0) GO TO 101
            INDEX(IBEG) = IBASIS(I)
            IBEG = IBEG + 1
            GO TO 102
  101    INDEX(IEND) = IBASIS(I)
         IEND = IEND - 1
  102 CONTINUE
      IF (IEND .EQ. M) GO TO 22
      DO 103 I = 1,M
  103    IBASIS(I) = INDEX(I)
C
C            REINVERSION OF THE BASIS MATRIX
C
      DO 132 J = 1,M
         KJ = IBASIS(J)
         IF (KJ .LE. N0) GO TO 110
         IF (KJ .LE. NS) GO TO 120
         IF (KJ .LE. N) GO TO 130
         GO TO 120
C
  110    DO 111 I = 1,M
  111       BI(I,J) = A(I,KJ)
         GO TO 132
C
  120    L = KJ - N0
         DO 121 I = 1,M
  121       BI(I,J) = 0.0
         BI(L,J) = 1.0
         GO TO 132
C
  130    L = KJ - N0
         DO 131 I = 1,M
  131       BI(I,J) = 0.0
         BI(L,J) = -1.0
  132 CONTINUE
C
      ICOUNT = 0
      CALL CROUT1 (BI, M, M, IEND, INDEX, Y, JCOL, IERR)
      IF (IERR .NE. 0) GO TO 580
C
C         CHECK THE ACCURACY OF BI AND RESET RERR
C
      BNORM = 0.0
      DO 142 J = 1,M
         KJ = IBASIS(J)
         IF (KJ .LE. N0) GO TO 140
            SUM = 1.0
            GO TO 142
  140    SUM = 0.0
         DO 141 I = 1,M
  141       SUM = SUM + ABS(A(I,KJ))
  142    BNORM = AMAX1(BNORM,SUM)
C
      BINORM = 0.0
      DO 151 J = 1,M
         SUM = 0.0
         DO 150 I = 1,M
  150       SUM = SUM + ABS(BI(I,J))
         BINORM = AMAX1(BINORM,SUM)
  151 CONTINUE
      RERR = AMAX1(RERRMN,EPS0*BNORM*BINORM)
      IF (RERR .GT. 1.E-2) GO TO 580
      BFLAG = 0
C
C                 RECALCULATION OF XB
C
  180 DO 183 I = 1,M
         DSUMP = 0.D0
         DSUMN = 0.D0
         DO 182 L = 1,M
            DT = BI(I,L)*B0(L)
            IF (DT .GT. 0.D0) GO TO 181
               DSUMN = DSUMN + DT
               GO TO 182
  181       DSUMP = DSUMP + DT
  182    CONTINUE
         XB(I) = DSUMP + DSUMN
         S = DSUMP
         T = DSUMN
         TOL = RERRMX*AMAX1(S,-T)
         IF (ABS(XB(I)) .LT. TOL) XB(I) = 0.0
  183 CONTINUE
      GO TO 601
C
C     FIND THE NEXT VECTOR A(--,JP) TO BE INSERTED INTO
C                       THE BASIS
C
  200 JP = 0
      RMIN = 0.0
      IF (NSTEP .EQ. 3) RMIN = -RTOL
      DO 201 J = 1,N0
         IF (BASIS(J) .NE. 0) GO TO 201
         IF (R(J) .GE. RMIN) GO TO 201
         JP = J
         RMIN = R(J)
  201 CONTINUE
      IF (N0 .EQ. N) GO TO 203
      JMIN = N0 + 1
      RMIN = RMIN*1.1
      DO 202 J = JMIN,N
         IF (BASIS(J) .NE. 0) GO TO 202
         IF (R(J) .GE. RMIN) GO TO 202
         JP = J
         RMIN = R(J)
  202 CONTINUE
  203 IF (JP .NE. 0) GO TO 300
      IF (NSTEP - 2) 800,230,250
C
C     INSERT THE VALUES OF THE ORGINAL, SLACK, AND SURPLUS
C             VARIABLES INTO R. THEN TERMINATE.
C
  220 DO 221 J = 1,N
  221    R(J) = 0.0
      DO 222 I = 1,M
         KI = IBASIS(I)
         IF (KI .LE. N) R(KI) = XB(I)
  222 CONTINUE
      RETURN
C
C             COMPLETION OF THE NSTEP = 2 CASE
C
  230 DO 231 I = 1,M
         IF (IBASIS(I) .LE. N) GO TO 231
         IF (XB(I) .GT. 0.0) GO TO 800
  231 CONTINUE
      GO TO 680
C
  240 IF (ICOUNT .GE. 5) GO TO 100
      IND = 1
      GO TO 220
C
C             COMPLETION OF THE NSTEP = 3 CASE
C
  250 IF (RERR .GT. 1.E-2) GO TO 251
         IND = 0
         GO TO 800
  251 IF (ICOUNT .GE. 5) GO TO 100
      IND = 6
      GO TO 800
C
C     IF MXITER ITERATIONS HAVE NOT BEEN PERFORMED THEN
C     BEGIN THE NEXT ITERATION. COMPUTE THE JP-TH COLUMN
C               OF BI*A AND STORE IT IN Y.
C
  300 IF (ITER .LT. MXITER) GO TO 301
         IND = 2
         GO TO 220
  301 ITER = ITER + 1
      ICOUNT = ICOUNT + 1
      IF (JP .GT. NS) GO TO 330
      IF (JP .GT. N0) GO TO 320
C
      NROW = 0
      AMAX = 0.0
      DO 305 I = 1,M
         IF (A(I,JP) .EQ. 0.0) GO TO 305
         NROW = NROW + 1
         INDEX(NROW) = I
         AMAX = AMAX1(ABS(A(I,JP)),AMAX)
  305 CONTINUE
      IF (NROW .NE. 0) GO TO 310
      IND = 4
      GO TO 220
C
  310 RERR1 = RERRMX*AMAX
      DO 313 I = 1,M
         DSUM = 0.D0
         DO 311 LL = 1,NROW
            L = INDEX(LL)
            DSUM = DSUM + DBLE(BI(I,L)*A(L,JP))
  311    CONTINUE
         Y(I) = DSUM
         IF (ABS(Y(I)) .GE. 5.E-3) GO TO 313
         BMAX = 0.0
         DO 312 L = 1,M
            BMAX = AMAX1(ABS(BI(I,L)),BMAX)
  312    CONTINUE
         TOL = RERR1*BMAX
         IF (ABS(Y(I)) .LT. TOL) Y(I) = 0.0
  313 CONTINUE
      GO TO 350
C
  320 L = JP - N0
      DO 321 I = 1,M
         Y(I) = BI(I,L)
  321 CONTINUE
      GO TO 350
C
  330 L = JP - N0
      DO 331 I = 1,M
         Y(I) = -BI(I,L)
  331 CONTINUE
C
  350 DO 351 I = 1,M
         IF (Y(I) .NE. 0.0) GO TO 360
  351 CONTINUE
      R(JP) = 0.0
      ITER = ITER - 1
      ICOUNT = ICOUNT - 1
      GO TO 200
C
  360 IF (NSTEP - 2) 400,430,440
C
C     FINDING THE VARIABLE XB(IP) TO BE MADE NONBASIC
C               FOR THE NSTEP = 1 CASE
C
  400 NPOS = 0
      IP = 0
      EPS = 0.0
      EPSI = XMAX
      DO 403 I = 1,M
         IF (XB(I) .LT. 0.0 .OR. Y(I) .LE. 0.0) GO TO 403
         RATIO = XB(I)/Y(I)
         IF (RATIO - EPSI) 401,402,403
  401    EPSI = RATIO
         NPOS = 1
         INDEX(1) = I
         GO TO 403
  402    NPOS = NPOS + 1
         INDEX(NPOS) = I
  403 CONTINUE
      IF (NPOS .EQ. 0) GO TO 420
      IF (EPSI .EQ. 0.0) GO TO 460
C
      DO 410 I = 1,M
         IF (XB(I) .GE. 0.0 .OR. Y(I) .GE. 0.0) GO TO 410
         RATIO = XB(I)/Y(I)
         IF (RATIO .GT. EPSI) GO TO 410
         IF (RATIO .LT. EPS) GO TO 410
         EPS = RATIO
         IP = I
  410 CONTINUE
      IF (IP .NE. 0) GO TO 500
      GO TO 460
C
  420 DO 421 I = 1,M
         IF (XB(I) .GE. 0.0 .OR. Y(I) .GE. 0.0) GO TO 421
         RATIO = XB(I)/Y(I)
         IF (RATIO .LT. EPS) GO TO 421
         EPS = RATIO
         IP = I
  421 CONTINUE
      GO TO 500
C
C     FINDING THE VARIABLE XB(IP) TO BE MADE NONBASIC
C               FOR THE NSTEP = 2 CASE
C
  430 NPOS = 0
      EPSI = XMAX
      DO 433 I = 1,M
         IF (Y(I) .LE. 0.0) GO TO 433
         RATIO = XB(I)/Y(I)
         IF (RATIO - EPSI) 431,432,433
  431    EPSI = RATIO
         NPOS = 1
         INDEX(1) = I
         GO TO 433
  432    NPOS = NPOS + 1
         INDEX(NPOS) = I
  433 CONTINUE
      GO TO 450
C
C     FINDING THE VARIABLE XB(IP) TO BE MADE NONBASIC
C               FOR THE NSTEP = 3 CASE
C
  440 NPOS = 0
      EPSI = XMAX
      DO 445 I = 1,M
         IF (Y(I)) 441,445,442
  441    IF (IBASIS(I) .LE. N) GO TO 445
         IP = I
         GO TO 500
  442    RATIO = XB(I)/Y(I)
         IF (RATIO - EPSI) 443,444,445
  443       EPSI = RATIO
            NPOS = 1
            INDEX(1) = I
            GO TO 445
  444       NPOS = NPOS + 1
            INDEX(NPOS) = I
  445 CONTINUE
C
  450 IF (NPOS .NE. 0) GO TO 460
      IF (ICOUNT .GE. 5) GO TO 100
      IND = 4
      GO TO 220
C
C              TIE BREAKING PROCEDURE
C
  460 IP = INDEX(1)
      IF (NPOS .EQ. 1) GO TO 500
      IP = 0
      BMIN = XMAX
      CMIN = XMAX
      DO 464 II = 1,NPOS
         I = INDEX(II)
         L = IBASIS(I)
         IF (L .GT. N0) GO TO 461
            IF (C(L) .LE. 0.0) CMIN = AMIN1(0.0,CMIN)
            IF (C(L) .GT. CMIN) GO TO 464
            IMIN = I
            CMIN = C(L)
            GO TO 464
  461    IF (L .LE. N) GO TO 462
            IP = I
            GO TO 500
  462    LROW = L - N0
         S = B0(LROW)
         IF (LROW .GT. NUMLE) GO TO 463
            IF (S .GT. BMIN) GO TO 464
            IP = I
            BMIN = S
            GO TO 464
  463    S = -S
         BMIN = AMIN1(0.0,BMIN)
         IF (S .GT. BMIN) GO TO 464
         IP = I
         BMIN = S
  464 CONTINUE
      IF (CMIN .LE. 0.0 .OR. IP .EQ. 0) IP = IMIN
C
C               TRANSFORMATION OF XB
C
  500 IF (XB(IP) .EQ. 0.0) GO TO 510
      CONST = XB(IP)/Y(IP)
      DO 501 I = 1,M
         S = XB(I)
         XB(I) = XB(I) - CONST*Y(I)
         IF (XB(I) .GE. 0.0) GO TO 501
         IF (S .GE. 0.0 .OR. XB(I) .GE. RERRMX*S) XB(I) = 0.0
  501 CONTINUE
      XB(IP) = CONST
C
C               TRANSFORMATION OF BI
C
  510 DO 512 J = 1,M
         IF (BI(IP,J) .EQ. 0.0) GO TO 512
         CONST = BI(IP,J)/Y(IP)
         DO 511 I = 1,M
  511       BI(I,J) = BI(I,J) - CONST*Y(I)
         BI(IP,J) = CONST
  512 CONTINUE
C
C             UPDATING IBASIS AND BASIS
C
      IOUT = IBASIS(IP)
      IBASIS(IP) = JP
      BASIS(IOUT) = 0
      BASIS(JP) = 1
      IF (IOUT .GT. N) NUM = NUM - 1
C
C        CHECK THE ACCURACY OF BI AND RESET RERR
C
      IF (RERR .GT. 1.E-2) GO TO 530
      K = 0
      DO 521 J = 1,M
         KJ = IBASIS(J)
         IF (KJ .GT. N0) GO TO 521
         SUM = 0.0
         DO 520 L = 1,M
            IF (A(L,KJ) .NE. 0.0) SUM = SUM + BI(J,L)*A(L,KJ)
  520    CONTINUE
         RERR = AMAX1(RERR,ABS(1.0 - SUM))
         K = K + 1
         IF (K .GE. MCHECK) GO TO 522
  521 CONTINUE
  522 IF (RERR .LE. 1.E-2) GO TO 600
C
C        THE ACCURACY CRITERIA ARE NOT SATISFIED
C
  530 IF (ICOUNT .LT. 5) GO TO 600
      BFLAG = 1
      GO TO 100
C
  580 IF (ITER .EQ. 0) GO TO 12
      IF (BFLAG .EQ. 0) GO TO 590
      BFLAG = 0
      DO 581 IP = 1,M
         IF (JP .EQ. IBASIS(IP)) GO TO 582
  581 CONTINUE
  582 IBASIS(IP) = IOUT
      BASIS(JP) = 0
      BASIS(IOUT) = 1
      IF (IOUT .GT. N) NUM = NUM + 1
      GO TO 100
C
  590 IND = 3
      GO TO 220
C
C       SET UP THE R ARRAY FOR THE NSTEP = 1 CASE
C
  600 IF (NSTEP - 2) 601,630,700
  601 DO 602 J = 1,M
         IF (XB(J) .LT. 0.0) GO TO 610
  602 CONTINUE
      GO TO 630
C
  610 NSTEP = 1
      M0 = 0
      DO 611 L = 1,M
         IF (XB(L) .GE. 0.0) GO TO 611
         M0 = M0 + 1
         INDEX(M0) = L
  611 CONTINUE
C
      DO 623 J = 1,M
         DSUMP = 0.D0
         DSUMN = 0.D0
         DO 622 LL = 1,M0
            L = INDEX(LL)
            IF (BI(L,J)) 620,622,621
  620       DSUMN = DSUMN + DBLE(BI(L,J))
            GO TO 622
  621       DSUMP = DSUMP + DBLE(BI(L,J))
  622    CONTINUE
         Y(J) = DSUMP + DSUMN
         S = DSUMP
         T = DSUMN
         TOL = RERRMX*AMAX1(S,-T)
         IF (ABS(Y(J)) .LT. TOL) Y(J) = 0.0
  623 CONTINUE
      GO TO 650
C
C       SET UP THE R ARRAY FOR THE NSTEP = 2 CASE
C
  630 IF (N .EQ. NUM) GO TO 680
      NSTEP = 2
      M0 = 0
      DO 631 L = 1,M
         IF (IBASIS(L) .LE. N) GO TO 631
         M0 = M0 + 1
         INDEX(M0) = L
  631 CONTINUE
C
      DO 643 J = 1,M
         DSUMP = 0.D0
         DSUMN = 0.D0
         DO 642 LL = 1,M0
            L = INDEX(LL)
            IF (BI(L,J)) 640,642,641
  640       DSUMN = DSUMN + DBLE(BI(L,J))
            GO TO 642
  641       DSUMP = DSUMP + DBLE(BI(L,J))
  642    CONTINUE
         Y(J) = -(DSUMP + DSUMN)
         S = DSUMP
         T = DSUMN
         TOL = RERRMX*AMAX1(S,-T)
         IF (ABS(Y(J)) .LT. TOL) Y(J) = 0.0
  643 CONTINUE
C
  650 DO 652 J = 1,N0
         SUM = 0.0
         IF (BASIS(J) .NE. 0) GO TO 652
         DO 651 L = 1,M
            IF (A(L,J) .NE. 0.0) SUM = SUM + Y(L)*A(L,J)
  651    CONTINUE
  652    R(J) = SUM
C
  660 IF (N0 .EQ. NS) GO TO 670
      JMIN = N0 + 1
      DO 661 J = JMIN,NS
         R(J) = 0.0
         IF (BASIS(J) .NE. 0) GO TO 661
         JJ = J - N0
         R(J) = Y(JJ)
  661 CONTINUE
C
  670 IF (NS .EQ. N) GO TO 200
      JMIN = NS + 1
      DO 671 J = JMIN,N
         R(J) = 0.0
         IF (BASIS(J) .NE. 0) GO TO 671
         JJ = J - N0
         R(J) = -Y(JJ)
  671 CONTINUE
      GO TO 200
C
C      SET UP A NEW R ARRAY FOR THE NSTEP = 3 CASE
C
  680 NSTEP = 3
      DO 682 J = 1,M
         DSUM = 0.D0
         DO 681 L = 1,M
            IL = IBASIS(L)
            IF (IL .LE. N0) DSUM = DSUM + DBLE(C(IL)*BI(L,J))
  681    CONTINUE
  682    Y(J) = DSUM
C
      DO 691 J = 1,N0
         R(J) = 0.0
         IF (BASIS(J) .NE. 0) GO TO 691
         DSUM = -C(J)
         DO 690 L = 1,M
            IF (A(L,J) .NE. 0.0) DSUM = DSUM + DBLE(Y(L)*A(L,J))
  690    CONTINUE
         R(J) = DSUM
         IF (R(J) .GE. 0.0) GO TO 691
         TOL = RERRMX*ABS(C(J))
         IF (ABS(R(J)) .LT. TOL) R(J) = 0.0
  691 CONTINUE
      GO TO 660
C
C       UPDATE THE R ARRAY FOR THE NSTEP = 3 CASE
C
  700 CONST = R(JP)
      DO 703 J = 1,N0
         IF (BASIS(J) .EQ. 0) GO TO 701
            R(J) = 0.0
            GO TO 703
  701    SUM = 0.0
         DO 702 L = 1,M
            IF (A(L,J) .NE. 0.0) SUM = SUM + BI(IP,L)*A(L,J)
  702    CONTINUE
         R(J) = R(J) - CONST*SUM
         IF (R(J) .GE. 0.0) GO TO 703
         TOL = RERRMX*ABS(C(J))
         IF (ABS(R(J)) .LT. TOL) R(J) = 0.0
  703 CONTINUE
C
  710 IF (N0 .EQ. NS) GO TO 720
      JMIN = N0 + 1
      DO 712 J = JMIN,NS
         IF (BASIS(J) .EQ. 0) GO TO 711
            R(J) = 0.0
            GO TO 712
  711    JJ = J - N0
         R(J) = R(J) - CONST*BI(IP,JJ)
  712 CONTINUE
C
  720 IF (NS .EQ. N) GO TO 200
      JMIN = NS + 1
      DO 722 J = JMIN,N
         IF (BASIS(J) .EQ. 0) GO TO 721
            R(J) = 0.0
            GO TO 722
  721    JJ = J - N0
         R(J) = R(J) + CONST*BI(IP,JJ)
  722 CONTINUE
      GO TO 200
C-----------------------------------------------------------------------
C               REFINE XB AND STORE THE RESULT IN Y
C-----------------------------------------------------------------------
  800 DO 801 I = 1,M
         Y(I) = 0.0
  801 CONTINUE
C
      M0 = 0
      DO 831 J = 1,M
         KJ = IBASIS(J)
         IF (KJ .LE. N0) GO TO 810
         IF (KJ .LE. NS) GO TO 820
         IF (KJ .LE. N) GO TO 830
         GO TO 820
C
  810    M0 = M0 + 1
         INDEX(M0) = J
         GO TO 831
C
  820    L = KJ - N0
         Y(L) = XB(J)
         GO TO 831
C
  830    L = KJ - N0
         Y(L) = -XB(J)
  831 CONTINUE
C
      IF (M0 .NE. 0) GO TO 841
         DO 840 I = 1,M
  840       R(I) = B0(I) - Y(I)
         GO TO 850
  841 DO 843 I = 1,M
         DSUM = Y(I)
         DO 842 JJ = 1,M0
            J = INDEX(JJ)
            KJ = IBASIS(J)
            DSUM = DSUM + DBLE(A(I,KJ)*XB(J))
  842    CONTINUE
         R(I) = B0(I) - DSUM
  843 CONTINUE
C
  850 RERR1 = AMIN1(RERRMX,RERR)
      DO 856 I = 1,M
         Y(I) = 0.0
         IF (XB(I)) 851,856,852
  851    SGN = -1.0
         DSUMP = 0.D0
         DSUMN = XB(I)
         GO TO 853
  852    SGN = 1.0
         DSUMP = XB(I)
         DSUMN = 0.D0
  853    DO 855 L = 1,M
            DT = BI(I,L)*R(L)
            IF (DT .GT. 0.D0) GO TO 854
               DSUMN = DSUMN + DT
               GO TO 855
  854       DSUMP = DSUMP + DT
  855    CONTINUE
         W = DSUMP + DSUMN
         IF (W .EQ. 0.0) GO TO 856
         IF (SGN .NE. SIGN(1.0,W)) GO TO 856
         S = DSUMP
         T = DSUMN
         TOL = RERR1*AMAX1(S,-T)
         IF (ABS(W) .GT. TOL) Y(I) = W
  856 CONTINUE
      IF (NSTEP - 2) 860,870,880
C
C         CHECK THE REFINEMENT (NSTEP = 1)
C
  860 DO 861 I = 1,M
         IF (Y(I) .GE. 0.0) GO TO 861
         IF (Y(I) .LT. -RERRMX) GO TO 240
         Y(I) = 0.0
  861    XB(I) = Y(I)
      GO TO 630
C
C         CHECK THE REFINEMENT (NSTEP = 2)
C
  870 DO 871 I = 1,M
         IF (IBASIS(I) .LE. N) GO TO 871
         IF (Y(I) .GT. RERRMX) GO TO 240
         Y(I) = 0.0
  871    XB(I) = Y(I)
      GO TO 680
C
C              COMPUTE Z  (NSTEP = 3)
C
  880 DSUM = 0.D0
      DO 881 I = 1,M
         KI = IBASIS(I)
         IF (KI .GT. N0) GO TO 881
         DSUM = DSUM + DBLE(C(KI)*Y(I))
  881    XB(I) = Y(I)
      Z = DSUM
      GO TO 220
      END
      REAL FUNCTION SPMPAR (I)
C-----------------------------------------------------------------------
C
C     SPMPAR PROVIDES THE SINGLE PRECISION MACHINE CONSTANTS FOR
C     THE COMPUTER BEING USED. IT IS ASSUMED THAT THE ARGUMENT
C     I IS AN INTEGER HAVING ONE OF THE VALUES 1, 2, OR 3. IF THE
C     SINGLE PRECISION ARITHMETIC BEING USED HAS M BASE B DIGITS AND
C     ITS SMALLEST AND LARGEST EXPONENTS ARE EMIN AND EMAX, THEN
C
C        SPMPAR(1) = B**(1 - M), THE MACHINE PRECISION,
C
C        SPMPAR(2) = B**(EMIN - 1), THE SMALLEST MAGNITUDE,
C
C        SPMPAR(3) = B**EMAX*(1 - B**(-M)), THE LARGEST MAGNITUDE.
C
C-----------------------------------------------------------------------
C     WRITTEN BY
C        ALFRED H. MORRIS, JR.
C        NAVAL SURFACE WARFARE CENTER
C        DAHLGREN VIRGINIA
C-----------------------------------------------------------------------
      INTEGER EMIN, EMAX
C
      IF (I .GT. 1) GO TO 10
         B = IPMPAR(4)
         M = IPMPAR(5)
         SPMPAR = B**(1 - M)
         RETURN
C
   10 IF (I .GT. 2) GO TO 20
         B = IPMPAR(4)
         EMIN = IPMPAR(6)
         ONE = FLOAT(1)
         BINV = ONE/B
         W = B**(EMIN + 2)
         SPMPAR = ((W * BINV) * BINV) * BINV
         RETURN
C
   20 IBETA = IPMPAR(4)
      M = IPMPAR(5)
      EMAX = IPMPAR(7)
C
      B = IBETA
      BM1 = IBETA - 1
      ONE = FLOAT(1)
      Z = B**(M - 1)
      W = ((Z - ONE)*B + BM1)/(B*Z)
C
      Z = B**(EMAX - 2)
      SPMPAR = ((W * Z) * B) * B
      RETURN
      END
      INTEGER FUNCTION IPMPAR (I)
C-----------------------------------------------------------------------
C
C     IPMPAR PROVIDES THE INTEGER MACHINE CONSTANTS FOR THE COMPUTER
C     THAT IS USED. IT IS ASSUMED THAT THE ARGUMENT I IS AN INTEGER
C     HAVING ONE OF THE VALUES 1-10. IPMPAR(I) HAS THE VALUE ...
C
C  INTEGERS.
C
C     ASSUME INTEGERS ARE REPRESENTED IN THE N-DIGIT, BASE-A FORM
C
C               SIGN ( X(N-1)*A**(N-1) + ... + X(1)*A + X(0) )
C
C               WHERE 0 .LE. X(I) .LT. A FOR I=0,...,N-1.
C
C     IPMPAR(1) = A, THE BASE.
C
C     IPMPAR(2) = N, THE NUMBER OF BASE-A DIGITS.
C
C     IPMPAR(3) = A**N - 1, THE LARGEST MAGNITUDE.
C
C  FLOATING-POINT NUMBERS.
C
C     IT IS ASSUMED THAT THE SINGLE AND DOUBLE PRECISION FLOATING
C     POINT ARITHMETICS HAVE THE SAME BASE, SAY B, AND THAT THE
C     NONZERO NUMBERS ARE REPRESENTED IN THE FORM
C
C               SIGN (B**E) * (X(1)/B + ... + X(M)/B**M)
C
C               WHERE X(I) = 0,1,...,B-1 FOR I=1,...,M,
C               X(1) .GE. 1, AND EMIN .LE. E .LE. EMAX.
C
C     IPMPAR(4) = B, THE BASE.
C
C  SINGLE-PRECISION
C
C     IPMPAR(5) = M, THE NUMBER OF BASE-B DIGITS.
C
C     IPMPAR(6) = EMIN, THE SMALLEST EXPONENT E.
C
C     IPMPAR(7) = EMAX, THE LARGEST EXPONENT E.
C
C  DOUBLE-PRECISION
C
C     IPMPAR(8) = M, THE NUMBER OF BASE-B DIGITS.
C
C     IPMPAR(9) = EMIN, THE SMALLEST EXPONENT E.
C
C     IPMPAR(10) = EMAX, THE LARGEST EXPONENT E.
C
C-----------------------------------------------------------------------
C
C     TO DEFINE THIS FUNCTION FOR THE COMPUTER BEING USED, ACTIVATE
C     THE DATA STATMENTS FOR THE COMPUTER BY REMOVING THE C FROM
C     COLUMN 1. (ALL THE OTHER DATA STATEMENTS SHOULD HAVE C IN
C     COLUMN 1.)
C
C     IF DATA STATEMENTS ARE NOT GIVEN FOR THE COMPUTER BEING USED,
C     THEN THE FORTRAN MANUAL FOR THE COMPUTER NORMALLY GIVES THE
C     CONSTANTS IPMPAR(1), IPMPAR(2), AND IPMPAR(3) FOR THE INTEGER
C     ARITHMETIC. HOWEVER, HELP MAY BE NEEDED TO OBTAIN THE CONSTANTS
C     IPMPAR(4),...,IPMPAR(10) FOR THE SINGLE AND DOUBLE PRECISION
C     ARITHMETICS. THE SUBROUTINES MACH AND RADIX ARE PROVIDED FOR
C     THIS PURPOSE.
C
C-----------------------------------------------------------------------
C
C     IPMPAR IS AN ADAPTATION OF THE FUNCTION I1MACH, WRITTEN BY
C     P.A. FOX, A.D. HALL, AND N.L. SCHRYER (BELL LABORATORIES).
C     IPMPAR WAS FORMED BY A.H. MORRIS (NSWC). THE CONSTANTS ARE
C     FROM BELL LABORATORIES, NSWC, AND OTHER SOURCES.
C
C-----------------------------------------------------------------------
      INTEGER IMACH(10)
C
C     MACHINE CONSTANTS FOR THE ALLIANT FX/8.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE AMDAHL MACHINES.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /   16 /
C     DATA IMACH( 5) /    6 /
C     DATA IMACH( 6) /  -64 /
C     DATA IMACH( 7) /   63 /
C     DATA IMACH( 8) /   14 /
C     DATA IMACH( 9) /  -64 /
C     DATA IMACH(10) /   63 /
C
C     MACHINE CONSTANTS FOR THE AT&T 3B SERIES, AT&T
C     PC 7300, AND AT&T 6300.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE BURROUGHS 1700 SYSTEM.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   33 /
C     DATA IMACH( 3) / 8589934591 /
C     DATA IMACH( 4) /    2 /
C     DATA IMACH( 5) /   24 /
C     DATA IMACH( 6) / -256 /
C     DATA IMACH( 7) /  255 /
C     DATA IMACH( 8) /   60 /
C     DATA IMACH( 9) / -256 /
C     DATA IMACH(10) /  255 /
C
C     MACHINE CONSTANTS FOR THE BURROUGHS 5700 SYSTEM.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   39 /
C     DATA IMACH( 3) / 549755813887 /
C     DATA IMACH( 4) /    8 /
C     DATA IMACH( 5) /   13 /
C     DATA IMACH( 6) /  -50 /
C     DATA IMACH( 7) /   76 /
C     DATA IMACH( 8) /   26 /
C     DATA IMACH( 9) /  -50 /
C     DATA IMACH(10) /   76 /
C
C     MACHINE CONSTANTS FOR THE BURROUGHS 6700/7700 SYSTEMS.
C
C     DATA IMACH( 1) /      2 /
C     DATA IMACH( 2) /     39 /
C     DATA IMACH( 3) / 549755813887 /
C     DATA IMACH( 4) /      8 /
C     DATA IMACH( 5) /     13 /
C     DATA IMACH( 6) /    -50 /
C     DATA IMACH( 7) /     76 /
C     DATA IMACH( 8) /     26 /
C     DATA IMACH( 9) / -32754 /
C     DATA IMACH(10) /  32780 /
C
C     MACHINE CONSTANTS FOR THE CDC 6000/7000 SERIES
C     COMPUTERS, AND THE CDC CYBER 990 AND 995 (NOS
C     OPERATING SYSTEM).
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   48 /
C     DATA IMACH( 3) / 281474976710655 /
C     DATA IMACH( 4) /    2 /
C     DATA IMACH( 5) /   48 /
C     DATA IMACH( 6) / -974 /
C     DATA IMACH( 7) / 1070 /
C     DATA IMACH( 8) /   95 /
C     DATA IMACH( 9) / -926 /
C     DATA IMACH(10) / 1070 /
C
C     MACHINE CONSTANTS FOR THE CDC CYBER 990 AND 995
C     (NOS/VE OPERATING SYSTEM).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    63 /
C     DATA IMACH( 3) / 9223372036854775807 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    48 /
C     DATA IMACH( 6) / -4096 /
C     DATA IMACH( 7) /  4095 /
C     DATA IMACH( 8) /    96 /
C     DATA IMACH( 9) / -4096 /
C     DATA IMACH(10) /  4095 /
C
C     MACHINE CONSTANTS FOR THE CONVEX COMPUTERS
C     (NATIVE MODE).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -127 /
C     DATA IMACH( 7) /   127 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1023 /
C     DATA IMACH(10) /  1023 /
C
C     MACHINE CONSTANTS FOR THE CONVEX COMPUTERS
C     (IEEE MODE).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE CRAY 2, X-MP, AND Y-MP
C     (CFT77 COMPILER USING THE 64 BIT INTEGER ARITHMETIC).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    63 /
C     DATA IMACH( 3) / 9223372036854775807 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    48 /
C     DATA IMACH( 6) / -8188 /
C     DATA IMACH( 7) /  8189 /
C     DATA IMACH( 8) /    96 /
C     DATA IMACH( 9) / -8188 /
C     DATA IMACH(10) /  8189 /
C
C     MACHINE CONSTANTS FOR THE CRAY 2, X-MP, AND Y-MP
C     (CFT77 COMPILER USING THE 46 BIT INTEGER ARITHMETIC).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    46 /
C     DATA IMACH( 3) / 70368744177663 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    48 /
C     DATA IMACH( 6) / -8188 /
C     DATA IMACH( 7) /  8189 /
C     DATA IMACH( 8) /    96 /
C     DATA IMACH( 9) / -8188 /
C     DATA IMACH(10) /  8189 /
C
C     MACHINE CONSTANTS FOR THE DATA GENERAL ECLIPSE S/200.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   15 /
C     DATA IMACH( 3) / 32767 /
C     DATA IMACH( 4) /   16 /
C     DATA IMACH( 5) /    6 /
C     DATA IMACH( 6) /  -64 /
C     DATA IMACH( 7) /   63 /
C     DATA IMACH( 8) /   14 /
C     DATA IMACH( 9) /  -64 /
C     DATA IMACH(10) /   63 /
C
C     MACHINE CONSTANTS FOR THE HARRIS 220.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   23 /
C     DATA IMACH( 3) / 8388607 /
C     DATA IMACH( 4) /    2 /
C     DATA IMACH( 5) /   23 /
C     DATA IMACH( 6) / -127 /
C     DATA IMACH( 7) /  127 /
C     DATA IMACH( 8) /   38 /
C     DATA IMACH( 9) / -127 /
C     DATA IMACH(10) /  127 /
C
C     MACHINE CONSTANTS FOR THE HONEYWELL 600/6000
C     AND DPS 8/70 SERIES.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   35 /
C     DATA IMACH( 3) / 34359738367 /
C     DATA IMACH( 4) /    2 /
C     DATA IMACH( 5) /   27 /
C     DATA IMACH( 6) / -127 /
C     DATA IMACH( 7) /  127 /
C     DATA IMACH( 8) /   63 /
C     DATA IMACH( 9) / -127 /
C     DATA IMACH(10) /  127 /
C
C     MACHINE CONSTANTS FOR THE HP 9000.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -126 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE IBM 360/370 SERIES,
C     THE IBM 3033, THE ICL 2900, THE ITEL AS/6, THE
C     XEROX SIGMA 5/7/9, AND THE SEL SYSTEMS 85/86.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /   16 /
C     DATA IMACH( 5) /    6 /
C     DATA IMACH( 6) /  -64 /
C     DATA IMACH( 7) /   63 /
C     DATA IMACH( 8) /   14 /
C     DATA IMACH( 9) /  -64 /
C     DATA IMACH(10) /   63 /
C
C     MACHINE CONSTANTS FOR THE IBM PC.
C
      DATA IMACH( 1) /     2 /
      DATA IMACH( 2) /    31 /
      DATA IMACH( 3) / 2147483647 /
      DATA IMACH( 4) /     2 /
      DATA IMACH( 5) /    24 /
      DATA IMACH( 6) /  -125 /
      DATA IMACH( 7) /   128 /
      DATA IMACH( 8) /    53 /
      DATA IMACH( 9) / -1021 /
      DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE MACINTOSH II - ABSOFT
C     MACFORTRAN II.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE PDP-11 FORTRAN SUPPORTING
C     32-BIT INTEGER ARITHMETIC.
C
C     DATA IMACH( 1) /    2 /
C     DATA IMACH( 2) /   31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /    2 /
C     DATA IMACH( 5) /   24 /
C     DATA IMACH( 6) / -127 /
C     DATA IMACH( 7) /  127 /
C     DATA IMACH( 8) /   56 /
C     DATA IMACH( 9) / -127 /
C     DATA IMACH(10) /  127 /
C
C     MACHINE CONSTANTS FOR THE SEQUENT BALANCE 8000.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE SILICON GRAPHICS IRIS-4D
C     SERIES (MIPS R3000 PROCESSOR).
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE SUN 3.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -125 /
C     DATA IMACH( 7) /   128 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1021 /
C     DATA IMACH(10) /  1024 /
C
C     MACHINE CONSTANTS FOR THE UNIVAC 1100 SERIES.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    35 /
C     DATA IMACH( 3) / 34359738367 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    27 /
C     DATA IMACH( 6) /  -128 /
C     DATA IMACH( 7) /   127 /
C     DATA IMACH( 8) /    60 /
C     DATA IMACH( 9) / -1024 /
C     DATA IMACH(10) /  1023 /
C
C     MACHINE CONSTANTS FOR THE VAX AND MICROVAX
C     COMPUTERS - F AND D FLOATING ARITHMETICS.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -127 /
C     DATA IMACH( 7) /   127 /
C     DATA IMACH( 8) /    56 /
C     DATA IMACH( 9) /  -127 /
C     DATA IMACH(10) /   127 /
C
C     MACHINE CONSTANTS FOR THE VAX AND MICROVAX
C     COMPUTERS - F AND G FLOATING ARITHMETICS.
C
C     DATA IMACH( 1) /     2 /
C     DATA IMACH( 2) /    31 /
C     DATA IMACH( 3) / 2147483647 /
C     DATA IMACH( 4) /     2 /
C     DATA IMACH( 5) /    24 /
C     DATA IMACH( 6) /  -127 /
C     DATA IMACH( 7) /   127 /
C     DATA IMACH( 8) /    53 /
C     DATA IMACH( 9) / -1023 /
C     DATA IMACH(10) /  1023 /
C
      IPMPAR = IMACH(I)
      RETURN
      END
      SUBROUTINE CROUT1(A,KA,N,IEND,INDEX,TEMP,JP,IERR)
C     ******************************************************************
C     CROUT PROCEDURE FOR INVERTING MATRICES
C     ******************************************************************
C     A IS A MATRIX OF ORDER N WHERE N IS GREATER THAN OR EQUAL TO 1.
C     THE INVERSE OF A IS COMPUTED AND STORED IN A.
C
C     KA = LENGTH OF THE COLUMNS OF THE ARRAY A
C     JP = THE NUMBER OF THE COLUMN THAT CONTAINS THE SMALLEST PIVOT
C
C     IEND MAY BE 0,1,...,N-1.  IT IS ASSUMED THAT EACH OF THE FIRST
C     IEND COLUMNS OF THE MATRIX A CONTAINS ONLY ONE NONZERO ELEMENT
C     AND THAT THE NONZERO ELEMENT IS 1 OR -1.
C
C     INDEX IS AN ARRAY OF DIMENSION N-1 OR LARGER THAT IS USED BY THE
C     ROUTINE FOR KEEPING TRACK OF THE ROW INTERCHANGES THAT ARE MADE.
C
C     TEMP IS A TEMPORARY STORAGE ARRAY.
C
C     IERR REPORTS THE STATUS OF THE RESULTS. IF A IS NONSINGULAR THEN
C     THE INVERSE OF A IS COMPUTED AND IERR=0. OTHERWISE IF A IS FOUND
C     TO BE SINGULAR THEN IERR=1 AND THE ROUTINE TERMINATES.
C     --------------------
      DIMENSION A(*),INDEX(*),TEMP(N)
      DOUBLE PRECISION DSUM
      MAX = KA*N
      MCOL = IEND*KA
      IF (IEND .EQ. 0) GO TO 100
C
C           PROCESS THE FIRST IEND COLUMNS OF A
C
      KCOL = 0
      DO 32 K = 1,IEND
      KK = KCOL + K
      NK = KCOL + N
      DO 10 LK = KK,NK
      IF (A(LK)) 20,10,30
   10 CONTINUE
      JP = K
      GO TO 300
C
   20 L = LK - KCOL
      LJ0 = MCOL + L
      DO 21 LJ = LJ0,MAX,KA
   21 A(LJ) = -A(LJ)
C
   30 L = LK - KCOL
      INDEX(K) = L
      IF (K .EQ. L) GO TO 32
      LJ = LK
      DO 31 KJ = KK,MAX,KA
      C = A(KJ)
      A(KJ) = A(LJ)
      A(LJ) = C
   31 LJ = LJ + KA
   32 KCOL = KCOL + KA
C
C           PROCESS THE REMAINING COLUMNS OF A
C
  100 NM1 = N - 1
      JP = 1
      IERR = 0
      PMIN = 0.0
      IBEG = IEND + 1
      IF (IBEG .EQ. N) GO TO 190
C
      K = IBEG
      KM1 = IEND
      KP1 = K + 1
      KCOL = MCOL
      KK = KCOL + K
      DO 172 KCOUNT = IBEG,NM1
C
C     SEARCH FOR THE K-TH PIVOT ELEMENT (K=IBEG,...,N-1)
C
      L = K
      S = ABS(A(KK))
      DO 110 I = KP1,N
      IK = KCOL + I
      C = ABS(A(IK))
      IF (S .GE. C) GO TO 110
      L = I
      S = C
  110 CONTINUE
C
      IF (K.GT.IBEG .AND. S.GE.PMIN) GO TO 120
      JP = K
      PMIN = S
      IF (S .EQ. 0.0) GO TO 300
C
C              INTERCHANGING ROWS K AND L
C
  120 INDEX(K) = L
      IF (K .EQ. L) GO TO 130
      KJ0 = MCOL + K
      LJ  = MCOL + L
      DO 121 KJ = KJ0,MAX,KA
      C = A(KJ)
      A(KJ) = A(LJ)
      A(LJ) = C
  121 LJ = LJ + KA
C
C       COMPUTE THE K-TH ROW OF U (K=IBEG,...,N-1)
C
  130 C = A(KK)
      IF (K .GT. IBEG) GO TO 140
      KJ0 = KK + KA
      DO 131 KJ = KJ0,MAX,KA
  131 A(KJ) = A(KJ)/C
      GO TO 160
C
  140 KL = MCOL + K
      DO 141 L = IBEG,KM1
      TEMP(L) = A(KL)
  141 KL = KL + KA
C
      KJ0 = KK + KA
      DO 151 KJ = KJ0,MAX,KA
      JCOL = KJ - K
      DSUM = -A(KJ)
        DO 150 L = IBEG,KM1
        LJ = JCOL + L
  150   DSUM = DSUM + DBLE(TEMP(L))*DBLE(A(LJ))
  151 A(KJ) = SNGL(-DSUM)/C
C
C      COMPUTE THE K-TH COLUMN OF L (K=IBEG+1,...,N)
C
  160 KM1 = K
      K = KP1
      KP1 = K + 1
      KCOL = KCOL + KA
      KK = KCOL + K
      DO 161 L = IBEG,KM1
      LK = KCOL + L
  161 TEMP(L) = A(LK)
C
      DO 171 I = K,N
      IL = MCOL + I
      DSUM = 0.D0
        DO 170 L = IBEG,KM1
        DSUM = DSUM + DBLE(A(IL))*DBLE(TEMP(L))
  170   IL = IL + KA
  171 A(IL) = DBLE(A(IL)) - DSUM
  172 CONTINUE
C
C           CHECK THE N-TH PIVOT ELEMENT
C
  190 NCOL = MAX - KA
      NN = NCOL + N
      C = ABS(A(NN))
      IF (C .GT. PMIN) GO TO 200
      JP = N
      IF (C .EQ. 0.0) GO TO 300
C
C          REPLACE L WITH THE INVERSE OF L
C
  200 IF (IBEG .EQ. N) GO TO 213
      JJ = MCOL + IBEG
      I = KA + 1
      DO 212 J = IBEG,NM1
      A(JJ) = 1.0/A(JJ)
      TEMP(J) = A(JJ)
      KJ = JJ
        DO 211 KM1 = J,NM1
        K = KM1 + 1
        KJ = KJ + 1
        DSUM = 0.D0
        KL = KJ
          DO 210 L = J,KM1
          DSUM = DSUM + DBLE(A(KL)*TEMP(L))
  210     KL = KL + KA
        A(KJ) = SNGL(-DSUM)/A(KL)
  211   TEMP(K) = A(KJ)
  212 JJ = JJ + I
  213 A(NN) = 1.0/A(NN)
      IF (N .EQ. 1) RETURN
C
C       SOLVE UX = Y WHERE Y IS THE INVERSE OF L
C
      DO 242 NMK = 1,NM1
      K = N - NMK
      LMIN = MAX0(IBEG,K+1)
      KL = (LMIN-1)*KA + K
        DO 230 L = LMIN,N
        TEMP(L) = A(KL)
        A(KL) = 0.0
  230   KL = KL + KA
C
      KJ0 = MCOL + K
        DO 241 KJ = KJ0,MAX,KA
        DSUM = -A(KJ)
        LJ = (KJ - K) + LMIN
          DO 240 L = LMIN,N
          DSUM = DSUM + DBLE(TEMP(L)*A(LJ))
  240     LJ = LJ + 1
  241   A(KJ) = -DSUM
  242 CONTINUE
C
C                 COLUMN INTERCHANGES
C
      JCOL = NCOL - KA
      DO 251 NMJ = 1,NM1
      J = N - NMJ
      K = INDEX(J)
      IF (J .EQ. K) GO TO 251
      IJ = JCOL
      IK = (K-1)*KA
        DO 250 I = 1,N
        IJ = IJ + 1
        IK = IK + 1
        C = A(IJ)
        A(IJ) = A(IK)
  250   A(IK) = C
  251 JCOL = JCOL - KA
      RETURN
C
C                    ERROR RETURN
C
  300 IERR = 1
      RETURN
      END
