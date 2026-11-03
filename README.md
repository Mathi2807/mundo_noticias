# Mundo Noticias

Canal de noticias 24/7 autónomo (YouTube + Twitch) con Josué, presentador generado con IA. Todo corre en GitHub Actions a ¢0.

- **Producir** (`producir.yml`): cada hora fabrica un bucle de 90 min (noticias reales filtradas, deportes, clima, dólar, ¿Sabías que?, música propia, pase de barrido y barra de noticias pasantes). Corren 2 a la vez.
- **Emitir** (`emitir.yml`, `emisor.py`): transmite solo bucles vigentes para la hora real de Costa Rica; reloj en pantalla; si no hay bucle vigente, música de relleno. Se releva solo.
- **Clips** (`mundo/clips.py`): tras cada bucle se generan clips verticales de 60-90 s (con título, subtítulos y tus redes) + un .txt con título/descripción sugeridos. Se descargan en la pestaña **Releases → "Clips para publicar"** (se borran solos a los 3 días).
- **Vigilante** (`vigilante.yml`): si el directo se cae, lo relanza.
- Redes que se promocionan: `config/redes.json`. Fuentes y ligas: `config/fuentes.json`. Franjas: `config/parrilla.json`.
- `estado/ESTADO.md`: resumen de la última producción y salud de las fuentes.
- Secretos necesarios: `YOUTUBE_KEY`, `TWITCH_KEY` (Settings → Secrets → Actions).
