# Git cleanup (stop tracking generated artifacts)

If you accidentally committed generated archives/logs/output folders, do:

## 1) Add ignores

Edit `.gitignore` and add patterns for generated files (archives, logs, unpacked reports).

## 2) Stop tracking already committed artifacts (keep files locally)

Example:

```sh
git rm -r --cached keenetic-maxprobe-*.tar.gz *.log keenetic-maxprobe-*/
git add .gitignore
git commit -m "Stop tracking generated artifacts"
git push
```

## 3) If large files are already in history

Use `git filter-repo` (recommended) or BFG.

**git filter-repo example**:

```sh
# install: https://github.com/newren/git-filter-repo
git filter-repo --path-glob 'keenetic-maxprobe-*.tar.gz' --invert-paths
git filter-repo --path-glob '*.log' --invert-paths
git push --force --all
git push --force --tags
```

> Force push will rewrite history. If someone already cloned the repo, they need to re-clone.

## 4) Fix remote URL (common SSH mistake)

SSH remote must use colon `:` after github.com:

```sh
git remote set-url origin git@github.com:Stak646/keenetic-maxprobe.git
```

HTTPS variant:

```sh
git remote set-url origin https://github.com/Stak646/keenetic-maxprobe.git
```
