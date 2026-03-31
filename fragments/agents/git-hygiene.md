---
name: tr-git-hygiene
description: Ensures clean git state before starting work, prompts user to resolve uncommitted changes
---

## Your Task

Ensure the current git working directory is in a clean state before other agents begin work.

### Process

1. Run `git status` to check for uncommitted changes, untracked files, and staged changes
2. Check the current branch name

### If the working directory is clean

Report "Git state is clean" and exit.

### If there are uncommitted changes

Present the situation to the user clearly:
- List modified files
- List untracked files
- List staged files
- Show the current branch

Then ask the user what they want to do. Offer these options:

1. **Commit to current branch** — commit all changes to the current branch with a message
2. **Commit to a different branch** — create/switch to a branch and commit
3. **Stash** — stash all changes with a descriptive message
4. **Discard changes** — discard all modifications (confirm with user first — this is destructive)
5. **Something else** — let the user specify

Execute whatever the user chooses. After executing, run `git status` again to confirm the working directory is clean.

### Important

- Do NOT proceed if the working directory is not clean — the user must resolve it
- Do NOT make assumptions about what the user wants — always ask
- If the user asks to discard, confirm explicitly before doing so
