# Git cleanup (remove generated artifacts)

## 1) Add rules to .gitignore
Make sure `.gitignore` includes (example):
- `*.tar.gz`
- `*.sha256`
- `keenetic-maxprobe-*/`
- `output/`, `dist/`

## 2) If files were already committed, stop tracking them
Example for generated archives:
```sh
git rm --cached -r -- '*.tar.gz' -- '*.sha256' keenetic-maxprobe-* || true
git add .gitignore
git commit -m "Stop tracking generated artifacts"
```

## 3) Commit new files that должны быть в репозитории
Если у вас много изменений и untracked файлов:
```sh
git add -A
git commit -m "Update collectors, docs, and core script"
```

## 4) Remote / push troubleshooting
Check remotes:
```sh
git remote -v
```

Set correct origin:
```sh
git remote remove origin
git remote add origin https://github.com/Stak646/keenetic-maxprobe.git
git push -u origin main
```

If you want SSH:
```sh
git remote set-url origin git@github.com:Stak646/keenetic-maxprobe.git
git push -u origin main
```

