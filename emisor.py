#!/usr/bin/env python3
"""Emisor de Mundo Noticias: transmite sin parar a YouTube y Twitch los bucles que fabrica `producir.yml`.

- Descarga los bucles terminados (artefactos de las corridas exitosas de producir.yml) y los emite en orden.
- Un solo ffmpeg mantiene la conexión abierta entre bucles (sin cortes al cambiar de video).
- Usa la hora real: solo emite bucles de HOY (hora de Costa Rica) y de la franja que toca; si no hay, repite otros de hoy; si no hay ninguno, pantalla de espera.
- Pasadas `--horas` horas pide a GitHub el relevo (lanza otra corrida de emitir.yml) y termina limpiamente.
Claves: variables de entorno YOUTUBE_KEY y TWITCH_KEY (secretos del repositorio). Nunca se imprimen.
"""
import argparse, glob, json, os, subprocess, sys, time
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
YT = 'rtmp://a.rtmp.youtube.com/live2/'
TW = 'rtmp://live.twitch.tv/app/'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def cr(ahora=None):
    return (ahora or datetime.now(timezone.utc)) + timedelta(hours=-6)


def es_hora_de_calma(ahora=None):
    """True entre las 0:00 y las 4:30 de Costa Rica (UTC-6)."""
    loc = cr(ahora)
    return loc.hour * 60 + loc.minute < 4 * 60 + 30


def meta(ruta):
    """Lee lista.json junto al video: (dia_cr, es_calma, inicio_utc, fin_utc) o None."""
    try:
        d = json.load(open(os.path.join(os.path.dirname(ruta), 'lista.json'), encoding='utf-8'))
        ini = datetime.fromisoformat(d['destino_utc'])
        fin = datetime.fromisoformat(d['fin_utc']) if d.get('fin_utc') else ini + timedelta(minutes=90)
        return d.get('destino_dia_cr'), bool(d.get('calma', 'Calma' in d.get('franja', ''))), ini, fin
    except Exception:
        return None


TOL_MIN = 30        # un bucle puede salir hasta 30 min antes de su hora prevista o 30 min después de su final
MAX_EDAD_H = 3      # un noticiero de hace más de 3 h ya no se repite


def elegir(archivos, reproducidos, ahora=None):
    """Elige el bucle a emitir según la hora REAL (Costa Rica). Devuelve la ruta o None (None = poner música de relleno).
    1) de la franja que toca (de madrugada solo música; de 4:30 en adelante solo noticias),
    2) con su ventana horaria vigente: [inicio - 30 min, fin + 30 min],
    3) de entre ellos, uno aún no emitido, el de hora prevista más cercana a ahora; si todos se emitieron, el emitido hace más tiempo,
    4) si ninguno está vigente: uno de HOY de la franja con menos de 3 h de atraso; NUNCA de otro día."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = cr(ahora).strftime('%Y-%m-%d'); calma = es_hora_de_calma(ahora)
    tol = timedelta(minutes=TOL_MIN)
    info = {f: meta(f) for f in archivos}
    franja_ok = [f for f in archivos if info[f] and info[f][1] == calma]
    vigentes = [f for f in franja_ok if info[f][2] - tol <= ahora <= info[f][3] + tol]
    if not vigentes:
        vigentes = [f for f in franja_ok if info[f][0] == hoy and info[f][3] <= ahora and ahora - info[f][3] <= timedelta(hours=MAX_EDAD_H - 1.5)]
    if not vigentes:
        return None
    nuevos = [f for f in vigentes if f not in reproducidos]
    if nuevos:
        return min(nuevos, key=lambda f: abs((info[f][2] - ahora).total_seconds()))
    return min(vigentes, key=lambda f: reproducidos.get(f, 0))


def humor_de(ahora=None):
    loc = cr(ahora); m = loc.hour * 60 + loc.minute
    return 'calma' if m < 270 else ('despierta' if m < 720 else ('marcha' if m < 1080 else 'positivo'))


def texto_reloj(ahora=None):
    loc = cr(ahora); h = loc.hour % 12 or 12
    return 'Hora CR · %d:%02d %s' % (h, loc.minute, 'a. m.' if loc.hour < 12 else 'p. m.')


def escribir_reloj(ruta, ahora=None):
    t = ruta + '.tmp'
    open(t, 'w', encoding='utf-8').write(texto_reloj(ahora)); os.replace(t, ruta)


def preparar_relleno(carpeta):
    """Música de la franja actual + imagen del set, generadas aquí mismo. Devuelve (imagen, wav, título) o None."""
    try:
        sys.path.insert(0, RAIZ)
        import cv2
        from mundo import musica as mus
        from mundo.render import capas, limpiar_barra
        os.makedirs(carpeta, exist_ok=True)
        hum = humor_de()
        sem = int(time.time() // 900)
        wav = os.path.join(carpeta, 'relleno_%s_%d.wav' % (hum, sem))
        est, titulo = mus.generar_pista(hum, sem, 4.0)
        mus.guardar_wav(est, wav)
        img = limpiar_barra(cv2.cvtColor(cv2.imread(os.path.join(RAIZ, 'assets', 'set_musica.png')), cv2.COLOR_BGR2RGB))
        for c in capas({'seccion': 'Música', 'titular': 'Ahora suena: ' + titulo, 'sub': 'Música generada por Mundo Noticias · sin derechos de terceros'}, 'Mundo Noticias'):
            c.sobre(img)
        png = os.path.join(carpeta, 'relleno_%s_%d.png' % (hum, sem))
        cv2.imwrite(png, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        for viejo in glob.glob(os.path.join(carpeta, 'relleno_*')):
            if viejo not in (wav, png):
                try: os.remove(viejo)
                except OSError: pass
        return png, wav, titulo
    except Exception as e:
        log('No pude preparar el relleno musical:', type(e).__name__, str(e)[:100])
        return None


def relleno_ts(rel, offset):
    png, wav, _ = rel
    return ['ffmpeg', '-loglevel', 'error', '-re', '-loop', '1', '-framerate', '25', '-i', png, '-i', wav, '-shortest', '-output_ts_offset', '%.3f' % offset,
            '-vf', 'scale=1280:720,format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-g', '50', '-c:a', 'aac', '-f', 'mpegts', 'pipe:1']


def destinos(args):
    if args.destino_prueba:
        return ['[f=flv]' + args.destino_prueba]
    out = []
    if os.environ.get('YOUTUBE_KEY'):
        out.append('[f=flv:onfail=ignore]' + YT + os.environ['YOUTUBE_KEY'].strip())
    if os.environ.get('TWITCH_KEY'):
        out.append('[f=flv:onfail=ignore]' + TW + os.environ['TWITCH_KEY'].strip())
    return out


def sincronizar(cola, repo, local):
    """Descarga bucles nuevos. Devuelve lista de rutas mp4 ordenadas de la más vieja a la más nueva."""
    if local:
        return sorted(glob.glob(os.path.join(local, '*.mp4')))
    os.makedirs(cola, exist_ok=True)
    try:
        r = subprocess.run(['gh', 'run', 'list', '--repo', repo, '--workflow', 'producir.yml', '--status', 'success',
                            '--limit', '30', '--json', 'databaseId'], capture_output=True, text=True, timeout=60)
        ids = sorted(x['databaseId'] for x in json.loads(r.stdout or '[]'))
        for i in ids:
            d = os.path.join(cola, str(i))
            if os.path.exists(os.path.join(d, 'bucle.mp4')):
                continue
            log('Descargando bucle de la corrida', i)
            subprocess.run(['gh', 'run', 'download', str(i), '--repo', repo, '-n', 'bucle', '-D', d],
                           capture_output=True, timeout=600)
    except Exception as e:
        log('No pude consultar GitHub:', type(e).__name__, str(e)[:100])
    return sorted(glob.glob(os.path.join(cola, '*', 'bucle.mp4')), key=lambda p: int(os.path.basename(os.path.dirname(p))))


def duracion(ruta):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', ruta], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def espera_ts(seg, offset):
    """Pantalla de espera como flujo mpegts (imagen fija + silencio)."""
    img = os.path.join(RAIZ, 'assets', 'set_musica.png')
    return ['ffmpeg', '-loglevel', 'error', '-re', '-loop', '1', '-framerate', '25', '-t', str(seg), '-i', img,
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-t', str(seg), '-output_ts_offset', '%.3f' % offset, '-vf', 'scale=1280:720,format=yuv420p',
            '-c:v', 'libx264', '-preset', 'veryfast', '-g', '50', '-c:a', 'aac', '-shortest', '-f', 'mpegts', 'pipe:1']


def archivo_ts(ruta, re_, offset):
    cmd = ['ffmpeg', '-loglevel', 'error'] + (['-re'] if re_ else []) + ['-i', ruta, '-c', 'copy', '-output_ts_offset', '%.3f' % offset,
                                                                         '-f', 'mpegts', 'pipe:1']
    return cmd


def codificador(dest, kbps, reloj):
    salida = '|'.join(dest)
    return ['ffmpeg', '-loglevel', 'warning', '-fflags', '+discardcorrupt', '-f', 'mpegts', '-i', 'pipe:0',
            '-map', '0:v:0', '-map', '0:a:0', '-vf', 'scale=1280:720,fps=25,format=yuv420p,drawtext=fontfile=%s:textfile=%s:reload=1:fontcolor=white:fontsize=22:x=w-tw-34:y=80:box=1:boxcolor=0x051234@0.72:boxborderw=7' % (os.path.join(RAIZ, 'fuentes_tipograficas', 'Inter-ExtraBold.otf'), reloj),
            '-c:v', 'libx264', '-preset', 'veryfast', '-b:v', '%dk' % kbps, '-maxrate', '%dk' % kbps, '-bufsize', '%dk' % (kbps * 2),
            '-g', '50', '-keyint_min', '50', '-sc_threshold', '0', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
            '-f', 'tee', salida]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--horas', type=float, default=5.6, help='cuánto transmite esta corrida antes de relevarse')
    ap.add_argument('--relevo-a-horas', type=float, default=5.3, help='a qué hora pide la corrida siguiente')
    ap.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', ''))
    ap.add_argument('--cola', default='cola')
    ap.add_argument('--kbps', type=int, default=2500)
    ap.add_argument('--cola-local', default=None, help='(pruebas) carpeta con .mp4 en vez de GitHub')
    ap.add_argument('--destino-prueba', default=None, help='(pruebas) archivo .flv en vez de YouTube/Twitch')
    ap.add_argument('--sin-tiempo-real', action='store_true', help='(pruebas) no limitar a velocidad real')
    ap.add_argument('--espera-seg', type=int, default=20)
    a = ap.parse_args()

    dest = destinos(a)
    if not dest:
        log('No hay claves YOUTUBE_KEY / TWITCH_KEY: nada que transmitir.'); sys.exit(1)
    log('Destinos activos: %d' % len(dest))
    t0 = time.time()
    fin, relevo = t0 + a.horas * 3600, t0 + a.relevo_a_horas * 3600
    pidio_relevo = False
    acum = 0.0   # segundos ya enviados: mantiene los tiempos continuos entre bucles
    reproducidos = {}
    os.makedirs(a.cola, exist_ok=True)
    reloj = os.path.abspath(os.path.join(a.cola, 'reloj.txt')); escribir_reloj(reloj)
    enc = subprocess.Popen(codificador(dest, a.kbps, reloj), stdin=subprocess.PIPE)
    rel = None
    try:
        while time.time() < fin:
            if not pidio_relevo and time.time() >= relevo and not a.cola_local:
                log('Pidiendo el relevo a GitHub...')
                subprocess.run(['gh', 'workflow', 'run', 'emitir.yml', '--repo', a.repo], capture_output=True)
                pidio_relevo = True
            archivos = sincronizar(a.cola, a.repo, a.cola_local)
            ruta = elegir(archivos, reproducidos)
            calma0 = es_hora_de_calma()
            if ruta:
                log('Emitiendo', ruta)
                reproducidos[ruta] = time.time()
                cmd = archivo_ts(ruta, not a.sin_tiempo_real, acum); tope = duracion(ruta)
            else:
                if not rel or rel[2] is None or time.time() - rel_t > 900 or rel_h != humor_de():
                    rel = preparar_relleno(os.path.join(a.cola, 'relleno')); rel_t = time.time(); rel_h = humor_de()
                if rel:
                    log('Sin bucle vigente para esta hora: música de relleno (%s)' % rel[2])
                    cmd = relleno_ts(rel, acum); tope = 240.0
                else:
                    log('Sin bucle vigente: pantalla de espera')
                    cmd = espera_ts(a.espera_seg, acum); tope = float(a.espera_seg)
            t_ini = time.time()
            p = subprocess.Popen(cmd, stdout=enc.stdin)
            while p.poll() is None:
                escribir_reloj(reloj)
                if time.time() >= fin:
                    p.terminate(); break
                if es_hora_de_calma() != calma0:      # cambió la franja (0:00 o 4:30): se corta para entrar con lo que toca
                    log('Cambio de franja: corto este bucle'); p.terminate(); break
                if enc.poll() is not None:
                    log('El codificador terminó; salgo.'); p.terminate(); sys.exit(2)
                time.sleep(1)
            acum += min(tope, time.time() - t_ini) if not a.sin_tiempo_real else tope
    finally:
        try:
            enc.stdin.close(); enc.wait(timeout=30)
        except Exception:
            enc.kill()
    log('Fin de esta corrida de emisión.')


if __name__ == '__main__':
    main()
