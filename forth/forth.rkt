#lang racket/base
;; A tiny Forth with two interchangeable inner interpreters:
;;   run-cps   : the continuation k is a closure
;;   run-defun : the same continuation defunctionalized into data
;; Primitives pass results through the data stack `ds`, so every
;; continuation takes no arguments (as NEXT does in 5th.c).
(require racket/match racket/string)

;; ---- machine state -------------------------------------------------
(define ds '())
(define (push! x) (set! ds (cons x ds)))
(define (reset!) (set! ds '()))
(define (pop!)
  (when (null? ds) (error 'forth "stack underflow"))
  (begin0 (car ds) (set! ds (cdr ds))))

;; ---- words and compiled code --------------------------------------
;; code is a Racket procedure (primitive) or a vector of instructions
(struct word (name [code #:mutable]))
(struct lit (n))
(struct jump ([target #:mutable]))
(struct br jump ())
(struct brz jump ())

(define dict (make-hash))
(define-syntax-rule (defprim name body ...)
  (hash-set! dict name (word name (λ () body ...))))
(define-syntax-rule (defbinop name f)
  (defprim name (let* ([b (pop!)] [a (pop!)]) (push! (f a b)))))
(define (flag b) (if b -1 0))

(defbinop "+" +)
(defbinop "-" -)
(defbinop "*" *)
(defbinop "/" quotient)
(defbinop "MOD" remainder)
(defbinop "=" (λ (a b) (flag (= a b))))
(defbinop "<" (λ (a b) (flag (< a b))))
(defbinop ">" (λ (a b) (flag (> a b))))
(defprim "DUP" (let ([a (pop!)]) (push! a) (push! a)))
(defprim "DROP" (pop!))
(defprim "SWAP" (let* ([b (pop!)] [a (pop!)]) (push! b) (push! a)))
(defprim "OVER" (let* ([b (pop!)] [a (pop!)]) (push! a) (push! b) (push! a)))
(defprim "." (printf "~a " (pop!)))
(defprim "CR" (newline))

;; ---- inner interpreter 1: CPS -------------------------------------
(define (cps-code code i k)
  (if (= i (vector-length code))
      (k)
      (let ([next (λ () (cps-code code (add1 i) k))])
        (match (vector-ref code i)
          [(lit n) (push! n) (next)]
          [(br t) (cps-code code t k)]
          [(brz t) (if (zero? (pop!)) (cps-code code t k) (next))]
          [(? word? w) (cps-word w next)]))))

(define (cps-word w k)
  (define c (word-code w))
  (if (procedure? c) (begin (c) (k)) (cps-code c 0 k)))

(define (run-cps w) (cps-word w void))

;; ---- inner interpreter 2: defunctionalized ------------------------
;; The only continuation was (λ () (cps-code code (add1 i) k)); it becomes
;; a frame holding code, i and k. A frame is an (ip, rsp) entry and
;; apply-k is NEXT after EXIT.
(struct frame (code i k))

(define (apply-k k)
  (match k
    ['done (void)]
    [(frame code i k) (defun-code code i k)]))

(define (defun-code code i k)
  (if (= i (vector-length code))
      (apply-k k)
      (match (vector-ref code i)
        [(lit n) (push! n) (defun-code code (add1 i) k)]
        [(br t) (defun-code code t k)]
        [(brz t) (defun-code code (if (zero? (pop!)) t (add1 i)) k)]
        [(? word? w) (defun-word w (frame code (add1 i) k))])))

(define (defun-word w k)
  (define c (word-code w))
  (if (procedure? c) (begin (c) (apply-k k)) (defun-code c 0 k)))

(define (run-defun w) (defun-word w 'done))

(define executor (make-parameter run-defun))

;; ---- outer interpreter / compiler ---------------------------------
(define (run-forth src)
  (define toks (map string-upcase (string-split src)))
  (define (next!) (begin0 (car toks) (set! toks (cdr toks))))
  (define cur #f)    ; word being defined, or #f when interpreting
  (define code '())  ; reversed instructions of `cur`
  (define ctl '())   ; compile-time control-flow stack
  (define (emit! i) (set! code (cons i code)))
  (define (here) (length code)) ; ponytail: O(n) per call, fine at colon-definition sizes
  (define (pop-ctl!) (begin0 (car ctl) (set! ctl (cdr ctl))))
  (define (resolve! j) (set-jump-target! j (here)))
  (define (immediate tok)
    (match tok
      [(or "IF" "WHILE") (let ([j (brz #f)]) (emit! j) (set! ctl (cons j ctl)))]
      ["ELSE" (let ([j (br #f)]) (emit! j) (resolve! (pop-ctl!)) (set! ctl (cons j ctl)))]
      ["THEN" (resolve! (pop-ctl!))]
      ["BEGIN" (set! ctl (cons (here) ctl))]
      ["UNTIL" (emit! (brz (pop-ctl!)))]
      ["AGAIN" (emit! (br (pop-ctl!)))]
      ["REPEAT" (let* ([j (pop-ctl!)] [b (pop-ctl!)]) (emit! (br b)) (resolve! j))]
      [_ #f]))
  (let loop ()
    (unless (null? toks)
      (define tok (next!))
      (define n (string->number tok 10))
      (define w (hash-ref dict tok #f))
      (cond
        [(equal? tok "(") (let skip () (unless (equal? (next!) ")") (skip)))]
        [(equal? tok ":")
         (set! cur (word (next!) (vector)))
         (hash-set! dict (word-name cur) cur)
         (set! code '())]
        [(equal? tok ";")
         (set-word-code! cur (list->vector (reverse code)))
         (set! cur #f)]
        [(and cur (immediate tok)) (void)]
        [(exact-integer? n) (if cur (emit! (lit n)) (push! n))]
        [(not w) (error 'forth "unknown word: ~a" tok)]
        [cur (emit! w)]
        [else ((executor) w)])
      (loop))))

(module+ test
  (require rackunit racket/port)
  (define (out src) (with-output-to-string (λ () (reset!) (run-forth src))))
  (define programs
    '((": SQUARE DUP * ; 5 SQUARE ." . "25 ")
      (": FACT DUP 1 > IF DUP 1 - FACT * THEN ; 20 FACT ." . "2432902008176640000 ")
      (": SIGN DUP 0 < IF DROP -1 ELSE 0 > IF 1 ELSE 0 THEN THEN . ; -5 SIGN 7 SIGN 0 SIGN"
       . "-1 1 0 ")
      (": COUNT 0 BEGIN DUP . 1 + DUP 4 = UNTIL DROP ; COUNT" . "0 1 2 3 ")
      (": DOWN BEGIN DUP 0 > WHILE DUP . 1 - REPEAT DROP ; 3 DOWN" . "3 2 1 ")))
  (for ([p (in-list programs)])
    (for ([e (list run-cps run-defun)])
      (parameterize ([executor e])
        (check-equal? (out (car p)) (cdr p)))))
  ;; a million-iteration loop runs in bounded stack in both interpreters
  (for ([e (list run-cps run-defun)])
    (parameterize ([executor e])
      (check-equal? (out ": LOOP 0 BEGIN 1 + DUP 1000000 = UNTIL . ; LOOP") "1000000 "))))
