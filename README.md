# Mundo Noticias · v1 técnica

Produce solo, sin tu celular ni intervención de nadie, bucles de 1-2 h de programación: noticias reales filtradas,
guion con la fuente citada, voz neuronal, Josué moviendo la boca y parpadeando, música ambiental y créditos.
**No incluye** la emisión en vivo a YouTube/Twitch (siguiente paso).

## Cómo funciona
1. `mundo/ingesta.py` lee 15 fuentes (RSS/HTML) respetando robots.txt; si una cae, las demás siguen (`estado/salud_fuentes.json`).
2. `mundo/filtro.py` excluye crimen, tragedias y farándula, puntúa utilidad pública y positividad, quita repetidos y equilibra 55 % interés / 45 % positivas.
3. `mundo/redactor.py` escribe el guion (modelo local opcional o resumen por extracción) con barreras: cita la fuente, no inventa cifras, longitud acotada.
4. `mundo/datos.py` añade clima (MET Norway) y dólar (Hacienda).
5. `mundo/voz.py` Piper + voz española CC0. `mundo/musica.py` música generada por código. `mundo/animacion.py` labios, parpadeo y movimiento.
6. `mundo/programa.py` arma el bucle según la franja (config/parrilla.json) y lo exporta con ffmpeg.

## Probar sin internet
`python3 main.py producir --offline --franja positivo --minutos 3 --interludio 0.3 --pista-min 0.4`

## Desplegar (desde el celular)
1. Crea un repositorio **público** vacío en GitHub (los públicos tienen minutos de Actions gratis) y sube esta carpeta.
2. Pestaña Actions → "Producir bucle" → Run workflow. Corre solo cada hora.
3. El video queda como artefacto (bucle.mp4, creditos.txt, lista.json). `estado/salud_fuentes.json` dice qué fuentes respondieron.

## Ajustes
Fuentes: `config/fuentes.json` · Horarios y franjas: `config/parrilla.json` · Redacción con IA propia: `MUNDO_LLM=transformers` + `requirements-llm.txt`.
