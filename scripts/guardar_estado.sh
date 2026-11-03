#!/usr/bin/env bash
# Sube el estado (noticias ya usadas) con reintentos; varias corridas pueden hacerlo a la vez.
git config user.name "mundo-noticias-bot"; git config user.email "bot@users.noreply.github.com"
for i in 1 2 3 4; do
  git add estado/estado.json estado/salud_fuentes.json estado/ESTADO.md 2>/dev/null
  git commit -qm "Estado del programa" 2>/dev/null || exit 0
  if git pull -q --rebase -X theirs origin "$(git rev-parse --abbrev-ref HEAD)" && git push -q; then exit 0; fi
  sleep $((RANDOM % 8 + 3))
done
exit 0
