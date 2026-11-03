#!/usr/bin/env bash
# Publica los clips verticales en Releases ("Clips para publicar") para descargarlos desde el celular, y borra los de más de 3 días.
set -u
ls clips/*.mp4 >/dev/null 2>&1 || { echo "No hay clips que publicar"; exit 0; }
gh release view clips >/dev/null 2>&1 || gh release create clips --title "Clips para publicar" \
  --notes "Clips verticales de 60-90 s (.mp4) con su título y descripción sugeridos (.txt). Se borran solos a los 3 días."
gh release upload clips clips/* --clobber
lim=$(date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)
gh api "repos/$GITHUB_REPOSITORY/releases/tags/clips" --jq ".assets[] | select(.created_at < \"$lim\") | .id" | while read -r id; do
  gh api -X DELETE "repos/$GITHUB_REPOSITORY/releases/assets/$id" >/dev/null
done
exit 0
