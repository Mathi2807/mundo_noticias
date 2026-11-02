#!/usr/bin/env python3
"""Emisor de Mundo Noticias: transmite sin parar a YouTube y Twitch los bucles que fabrica `producir.yml`.

- Descarga los bucles terminados (artefactos de las corridas exitosas de producir.yml) y los emite en orden.
- Un solo ffmpeg mantiene la conexión abierta entre bucles (sin cortes al cambiar de video).
- Si no hay bucles nuevos, repite los anteriores; si no hay ninguno, emite una pantalla de espera.
- Pasadas `--horas` horas pide a GitHub el relevo (lanza otra corrida de emitir.yml) y termina limpiamente.
Claves: variables de entorno YOUTUBE_KEY y TWITCH_KEY (secretos del repositorio). Nunca se imprimen.
"""
import argparse, glob, json, os, subprocess, sys, time

RAIZ = os.path.dirname(os.path.abspath(__file__))
YT = 'rtmp://a.rtmp.youtube.com/live2/'
TW = 'rtmp://live.twitch.tv/app/'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


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
                            '--limit', '8', '--json', 'databaseId'], capture_output=True, text=True, timeout=60)
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


def codificador(dest, kbps):
    salida = '|'.join(dest)
    return ['ffmpeg', '-loglevel', 'warning', '-fflags', '+discardcorrupt', '-f', 'mpegts', '-i', 'pipe:0',
            '-map', '0:v:0', '-map', '0:a:0', '-vf', 'scale=1280:720,fps=25,format=yuv420p',
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
    enc = subprocess.Popen(codificador(dest, a.kbps), stdin=subprocess.PIPE)
    try:
        while time.time() < fin:
            if not pidio_relevo and time.time() >= relevo and not a.cola_local:
                log('Pidiendo el relevo a GitHub...')
                subprocess.run(['gh', 'workflow', 'run', 'emitir.yml', '--repo', a.repo], capture_output=True)
                pidio_relevo = True
            archivos = sincronizar(a.cola, a.repo, a.cola_local)
            nuevos = [f for f in archivos if f not in reproducidos]
            if nuevos:
                ruta = nuevos[0]
            elif archivos:
                ruta = min(archivos, key=lambda f: reproducidos.get(f, 0))   # repite el menos reciente
            else:
                ruta = None
            if ruta:
                log('Emitiendo', ruta)
                reproducidos[ruta] = time.time()
                d = duracion(ruta)
                cmd = archivo_ts(ruta, not a.sin_tiempo_real, acum); acum += d
            else:
                log('Sin bucles todavía: pantalla de espera')
                cmd = espera_ts(a.espera_seg, acum); acum += a.espera_seg
            p = subprocess.Popen(cmd, stdout=enc.stdin)
            while p.poll() is None:
                if time.time() >= fin:
                    p.terminate(); break
                if enc.poll() is not None:
                    log('El codificador terminó; salgo.'); p.terminate(); sys.exit(2)
                time.sleep(1)
    finally:
        try:
            enc.stdin.close(); enc.wait(timeout=30)
        except Exception:
            enc.kill()
    log('Fin de esta corrida de emisión.')


if __name__ == '__main__':
    main()
