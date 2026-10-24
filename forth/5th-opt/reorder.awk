# Reorder the five parameters (env sp rsp ip target) of every word in 5th.c.
#   awk -v order=sp-rsp-ip-env -f reorder.awk 5th.c > out.c
# A parameter left out of `order` goes last (target-ip-sp-rsp is target,ip,sp,rsp,env).
BEGIN {
    n = split("env sp rsp ip target", canon, " ")
    m = split(order, want, "-")
    for (i = 1; i <= m; i++) seen[want[i]]++
    for (i = 1; i <= n; i++) if (!seen[canon[i]]) want[++m] = canon[i]
    for (i = 1; i <= n; i++) for (j = 1; j <= n; j++) if (canon[j] == want[i]) pick[i] = j
    if (m != n) { print "reorder.awk: order must name each of: env sp rsp ip target" > "/dev/stderr"; exit 1 }

    # Every parameter list in 5th.c: types, declarations, and the calls that pass them.
    # The attribute variant comes first so it travels with `target`.
    nl = split("struct interp_t *, intptr_t *, union instr_t **, union instr_t *, union instr_t *"       \
        "|struct interp_t *env, intptr_t *sp, union instr_t **rsp, union instr_t *ip, union instr_t *target __attribute__((unused))" \
        "|struct interp_t *env, intptr_t *sp, union instr_t **rsp, union instr_t *ip, union instr_t *target" \
        "|env, sp, rsp, ip + 1, ip->word|env, sp, rsp, ip, ip->word|env, sp, rsp, ip, target" \
        "|&env, env.s0, env.r0, ip, ip->word", lists, "|")
}
{
    for (k = 1; k <= nl; k++)
        if ((p = index($0, lists[k])) > 0) {
            split(lists[k], item, ", ")
            out = item[pick[1]]
            for (i = 2; i <= n; i++) out = out ", " item[pick[i]]
            $0 = substr($0, 1, p - 1) out substr($0, p + length(lists[k]))
            sites++
            break
        }
    print
}
END {
    if (m == n && sites != 10) { printf "reorder.awk: expected 10 parameter lists in 5th.c, found %d\n", sites > "/dev/stderr"; exit 1 }
}
