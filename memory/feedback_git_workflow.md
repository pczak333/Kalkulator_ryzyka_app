---
name: feedback_git_workflow
description: "After every meaningful change, commit to Git and push to GitHub with a clear commit message"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: caebcf0c-663c-42dd-9de0-b2c3e77b559c
---

Commit and push to GitHub after every meaningful change (new file, updated spec, working feature, config change).

**Why:** User wants a save version always available on GitHub. Explicitly requested this as a standing instruction.

**How to apply:** After any substantive edit or addition, run `git add <files>`, `git commit -m "..."`, `git push origin main`. Use clear, descriptive messages. Never bundle unrelated changes into one commit. See also [[project_github]].
