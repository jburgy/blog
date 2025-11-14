# Claude Haiku 4.5 C Optimization Experiment

A [discord 🧵](https://discord.com/channels/1415980515806412813/1438623705700761701) prompted me
to wonder whether a different ordering of function parameter could lead to faster code for
[5th.c](https://github.com/jburgy/blog/blob/main/forth/5th.c).  I realized it would be a tedious
bit of work and remembered that tedium is just what LLMs excel at.

[chat.md](https://github.com/jburgy/blog/blob/main/forth/5th-opt/chat.md) is a record of my
interaction with [Claude Haiku 4.5](https://www.anthropic.com/news/claude-haiku-4-5) via
[GitHub Copilot](https://code.visualstudio.com/docs/copilot/overview).  I did not keep all
intermediate files as they are repetitive.  Instead, I kept patches which can be applied with

```bash
$ patch 5th.c 5th-opt/sp-rsp-ip-env.diff
$ clang -S -O3 5th.c -o 5th.s
$ grep -c mov 5th.s
640
```
