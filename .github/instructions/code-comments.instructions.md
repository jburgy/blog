---
description: Code comment style — state the current reason, not the edit history
applyTo: '**'
---

# Code comment style

A comment answers "why is this line/block here," never "what used to be here"
or "what we just changed." Git history and commit messages already own the
chronology; don't duplicate them in the code.

- Bad: `// previously used X, switched to Y because Z` · `// now handles the case we just found`
- Good: `// Y: Z` (state the current rule, skip the narration)

Keep comments to one line. Only comment code that isn't self-explanatory —
most lines need none.
