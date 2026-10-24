# Claude Haiku 4.5 C Optimization Experiment

A [discord 🧵](https://discord.com/channels/1415980515806412813/1438623705700761701) prompted me
to wonder whether a different ordering of function parameter could lead to faster code for
[5th.c](https://github.com/jburgy/blog/blob/main/forth/5th.c).  I realized it would be a tedious
bit of work and remembered that tedium is just what LLMs excel at.

[chat.md](https://github.com/jburgy/blog/blob/main/forth/5th-opt/chat.md) is a record of my
interaction with [Claude Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5) via
[GitHub Copilot](https://code.visualstudio.com/docs/copilot/overview).  I did not keep all
intermediate files as they are repetitive.  Instead, [reorder.awk](https://github.com/jburgy/blog/blob/main/forth/5th-opt/reorder.awk)
generates any ordering from the current `5th.c`.  A parameter left out of the order goes last, so
`target-ip-sp-rsp` puts `target` first and `env` last.

```bash
$ awk -v order=sp-rsp-ip-env -f 5th-opt/reorder.awk 5th.c > reordered.c
$ clang -S -O3 -target x86_64-apple-macos reordered.c -o reordered.s
$ grep -c mov reordered.s
836
```

`make 5th-order-sp-rsp-ip-env` builds the reordered interpreter directly.  The other `*.diff` files
here are patches against `5th.c` (`make 5th-NAME` applies and builds them).
