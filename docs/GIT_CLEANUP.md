# Как убрать ненужные файлы из Git

## 1) Перестать отслеживать (но оставить на диске)
Например, если случайно закоммитил архивы:
```bash
git rm -r --cached "*.tar.gz"
git commit -m "Stop tracking tarballs"
git push
```

## 2) Полностью удалить из истории (если были секреты)
Рекомендуется `git filter-repo` (лучше чем filter-branch).

### Установка (Windows)
```bash
pip install git-filter-repo
```

### Удалить, например, все tar.gz и логи из истории
```bash
git filter-repo --path-glob "*.tar.gz" --path-glob "*.log" --invert-paths
git push --force --all
git push --force --tags
```

После этого всем пользователям нужно заново клонировать репозиторий.

## 3) Если секрет утёк в историю
- поменяй секрет (токен/пароль),
- затем очисти историю как выше.
