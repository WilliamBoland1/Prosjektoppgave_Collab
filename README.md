# Prosjektoppgave_Collab

Shared repository for the project assignment.

## Setup

```bash
git clone https://github.com/WilliamBoland1/Prosjektoppgave_Collab.git
cd Prosjektoppgave_Collab

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

## Working in this repo with two people

**Rule:** `main` is the shared, always-working version. Nobody commits directly to `main`.
Each of us works on our own branch and merges into `main` through a pull request.

| Branch | Owner |
| --- | --- |
| `main` | shared — merged code only |
| `william` | William |
| `partner` | (rename to the other person's name) |

### One-time: create your own branch

```bash
git checkout main
git pull
git checkout -b william       # your own branch name
git push -u origin william
```

### Every work session

```bash
git checkout william          # make sure you are on your own branch
git pull origin main          # get the newest shared code first
# ... do your work ...
git add .
git commit -m "Short description of what you did"
git push
```

### When your work is ready to share

1. Go to the repo on GitHub → **Pull requests** → **New pull request**.
2. Base: `main` ← compare: your branch. Create the pull request.
3. The other person looks it over and clicks **Merge**.
4. Both of us then run `git checkout main && git pull` to get the merged version.

After merging you can keep using the same branch — just remember to `git pull origin main`
into it before starting new work.

### If you get a merge conflict

Git marks the conflicting lines in the file like this:

```
<<<<<<< HEAD
your version
=======
their version
>>>>>>> main
```

Open the file, keep the lines that should survive, delete the `<<<<<<<`, `=======` and
`>>>>>>>` markers, then:

```bash
git add <the file>
git commit
git push
```

### Good habits

- Pull before you start, push when you stop — small commits are easier to merge.
- Don't edit the same file at the same time if you can avoid it; agree on who owns what.
- Keep data files and virtual environments out of git (see `.gitignore`).
- Write commit messages in plain language: *what* changed, not "update".
