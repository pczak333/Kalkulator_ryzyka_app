---
name: project-branch-consolidation
description: "16.07.2026 — repo consolidated from 4 branches (main, etap2, two stale worktree branches) down to a single main branch, at the user's explicit request now that Etap 2 is considered complete. Standing fact: this project no longer uses a main/etap2 split — everything happens on main."
metadata:
  node_type: memory
  type: project
  originSessionId: 935a6952-4b75-47de-a4be-ad7f1b62d18b
---

## What happened

User: "w projekcie widzę 3 gałęzie... pora aby wszystko zcalić i mieć jedną
wersję" — right after finishing the visual redesign (Faza A+B, see
[[project_visual_redesign]]), asked to consolidate the repo to one branch.

Investigated before touching anything (all read-only):
- `main` was a **strict ancestor** of `etap2` — zero divergent commits on
  `main` since the branch point. This made the merge a trivial fast-forward,
  no conflicts, no merge commit needed.
- `worktree-jest-problem-z-w-a-ciw-stateless-teapot` — leftover from the
  07.07 wezwania-przedsądowe session ([[project_wezwania_przedsadowe]]). Its
  one substantive commit (378a5f0) had already been re-applied to `etap2` as
  a fresh commit (f6d673f) back on 07.07 — confirmed via
  `git log etap2..<branch>` showing only that already-superseded commit plus
  one stale status-note commit.
- `worktree-lucky-singing-parasol` — confirmed via
  `git merge-base --is-ancestor <branch> etap2` to be a **pure ancestor** of
  `etap2`'s own history (an old point `etap2` had already passed through) —
  zero unique commits, zero risk in deleting.

Asked the user one clarifying question before executing (this was a real
fork with lasting workflow consequences, not a technical detail to just
decide unilaterally): keep a `main`+`etap2` split going forward, or collapse
to `main` only. **User chose: single `main` branch, no dev branch.**

## Execution

1. `git checkout main` → `git merge etap2 --ff-only` (clean fast-forward,
   confirmed no conflicts possible ahead of time) → `git push origin main`.
2. `git worktree remove` the physical worktree directory *before* deleting
   its branch (required — git refuses to delete a branch that's still
   checked out in a worktree).
3. `git branch -D etap2 worktree-jest-problem-z-w-a-ciw-stateless-teapot
   worktree-lucky-singing-parasol` (local), then
   `git push origin --delete etap2 worktree-jest-problem-z-w-a-ciw-stateless-teapot`
   (remote — the parasol branch had no remote counterpart to begin with).
4. Updated `CLAUDE.md`'s "Branch strategy" and "Git workflow" sections to
   describe the new single-branch reality instead of the old main/etap2
   table — this was a real risk of going stale if left untouched (the doc
   would keep telling future sessions to push to a branch that no longer
   exists). Also fixed an unrelated, long-stale pointer to a memory file
   named `project-etap2-state.md` in CLAUDE.md's "Synchronizacja
   dokumentacji" section — that file was never actually the memory system
   (this repo uses `MEMORY.md` + per-topic files); noticed it while already
   touching that section, fixed it in the same pass.

## One thing checked and cleared, not left as a loose end

The merge deleted `app/.streamlit/secrets.toml` from tracking (it existed on
`main`'s old history but not on `etap2`, which had already untracked it,
see commit `bcbb06d "Usun secrets.toml ze sledzenia gita"`). Before assuming
this was fine, checked what that file actually contained historically via
`git show <commit>:app/.streamlit/secrets.toml` — it only ever held
`TEST_PANEL_PASSWORD = "krs-test-2024"`, the same non-sensitive default
already hardcoded as a fallback throughout the app and openly documented in
CLAUDE.md. No `ANTHROPIC_API_KEY`/Azure keys were ever committed — no
rotation needed, no incident. Worth remembering the check itself (verify
historical secret exposure by reading the actual committed content, don't
just assume from the filename) more than the specific non-finding.

## Standing fact going forward

This repo has **one branch: `main`**. Do not create or push to `etap2` (or
suggest branch-based workflows) unless the user explicitly asks for that
again — the whole point of this consolidation was to stop needing to think
about which branch something belongs on. `git push origin main` is now the
only push target; `CLAUDE.md`'s own git-workflow section reflects this.
