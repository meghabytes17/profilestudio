# Updating this repo (git bundle workflow)

Changes arrive as a small **git bundle** file (one file, full history). Because the
app is installed with `pip install -e .`, a `git pull` updates the running code with
no reinstall.

## One-time setup
```bat
cd C:\Users\Dagger\source\repos
git clone C:\path\to\incoming-profile-utility.bundle ipu
cd ipu
python -m venv .venv
.venv\Scripts\activate
pip install -e .
git remote add sandbox C:\path\to\incoming-profile-utility.bundle
```

## Each update
1. Save the new `.bundle` over the same path (overwrite the old file).
2. From the repo:
   ```bat
   git pull sandbox main
   ```
Success looks like `Fast-forward` and a list of changed files. The app reflects the
changes immediately — no `pip install` needed.

## Notes
- Bundles carry full history, so skipping an update is fine; one `git pull` catches up.
- "refusing to merge unrelated histories" means your clone and the bundle diverged
  (e.g. you started from a zip instead of a clone). Fix by cloning fresh from the
  latest bundle into a new folder and re-running `pip install -e .`.
- Your own local commits are preserved; pulls merge on top.
