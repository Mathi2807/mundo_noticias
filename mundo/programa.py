"""Parrilla: arma un bucle (lista de segmentos) para la franja horaria y lo produce en video+audio."""
import json, math, os, random, subprocess, wave
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np

from . import musica as mus
from . import voz as vozmod
from .animacion import Josue, envolvente_boca
from .redactor import ETIQUETAS, redactar, titular_corto
from .render import capas, limpiar_barra, W, H
from .pase import barrido, swoosh, SEG_PASE
from .ticker import Ticker

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 25
SR = 44100
PAD_ANTES, PAD_DESPUES = 0.75, 0.45     # la voz entra después del barrido de pase


def cargar_parrilla():
    return json.load(open(os.path.join(RAIZ, 'config', 'parrilla.json'), encoding='utf-8'))


def franja_actual(ahora_utc, parrilla):
    loc = ahora_utc + timedelta(hours=parrilla['zona_horaria_utc'])
    m = loc.hour * 60 + loc.minute
    for f in parrilla['franjas']:
        a = int(f['desde'][:2]) * 60 + int(f['desde'][3:])
        b = int(f['hasta'][:2]) * 60 + int(f['hasta'][3:])
        if a <= m < b:
            return f, (b - m), loc
    return parrilla['franjas'][0], 60, loc


def saludo(loc):
    h = loc.hour
    return 'Buenos días' if h < 12 else ('Buenas tardes' if h < 18 else 'Buenas noches')


MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def fecha_larga(loc):
    return '%s %d de %s de %d' % (DIAS[loc.weekday()].capitalize(), loc.day, MESES[loc.month - 1], loc.year)


def item_noticia(c):
    """Candidata del filtro -> ítem de programa (con guion redactado)."""
    sec = c['seccion']
    c['seccion_txt'] = ETIQUETAS.get(sec, 'Nacionales' if sec not in ETIQUETAS else ETIQUETAS[sec])
    guion, motor, problemas = redactar(c)
    if problemas:
        return None
    if c.get('repaso'):
        guion = 'Repasamos una noticia de hoy. ' + guion
    fecha = (c.get('fecha') or '')[:10]
    sub = 'Fuente: %s' % c['fuente']
    if fecha:
        y, m, d = fecha.split('-')
        sub += ' · %d %s %s' % (int(d), MESES[int(m) - 1][:3], y)
    return {'id': c['id'], 'seccion': c['seccion_txt'], 'set': 'deportes' if sec == 'deportes' else 'noticias',
            'titular': titular_corto(c['titulo'], 120), 'sub': sub, 'fuente': c['fuente'], 'url': c['url'], 'guion': guion,
            'motor': motor, 'tipo': c.get('tipo', 'interes'), 'repaso': bool(c.get('repaso'))}


def _est(it):
    """Segundos aproximados que dura una nota hablada (antes de sintetizar la voz)."""
    return len((it.get('guion') or '').split()) / 2.5 + PAD_ANTES + PAD_DESPUES + 1


def _pausa(pista, franja, k):
    t = ['Escuchas «%s», música creada por Mundo Noticias. Seguimos en %s.',
         'Eso fue «%s», una pieza original de Mundo Noticias. Esto es %s.',
         'Música original de Mundo Noticias: «%s». Continuamos en %s.'][k % 3]
    g = t % (pista['titulo'], franja['nombre'])
    return {'tipo': 'voz', 'item': {'id': 'pausa%d' % k, 'seccion': 'Mundo Noticias', 'set': 'noticias', 'titular': franja['nombre'],
                                    'sub': 'Música generada por Mundo Noticias · sin derechos de terceros', 'guion': g}}


def armar_bucle(franja, loc, notas, extras, pistas, objetivo_min, parrilla, rng):
    """Devuelve la lista de segmentos del bucle. notas: ítems ya redactados; extras: clima/tipo de cambio.
    Las notas se reparten parejo entre las canciones, para que no haya una pared de música ni una de voz."""
    segs = []
    meta = objetivo_min * 60
    if franja['tipo'] == 'musica':
        t, k = 0.0, 0
        while t < meta:
            p = pistas[k % len(pistas)]
            segs.append({'tipo': 'musica', 'pista': p, 'dur': p['dur']}); t += p['dur']; k += 1
        return segs
    reales = [n for n in notas if not n.get('extra')]
    titulares = [n['titular'] for n in reales[:5]]
    ahora_txt = fecha_larga(loc)
    guion_tit = '%s, soy Josué y esto es Mundo Noticias. Estos son los titulares. %s. Comenzamos.' % (
        saludo(loc), '. '.join(t.rstrip('.') for t in titulares) if titulares else 'Hoy te traemos lo más útil y lo mejor del día')
    segs.append({'tipo': 'voz', 'item': {'id': 'titulares', 'seccion': 'Titulares', 'set': 'noticias', 'titular': 'Titulares de hoy',
                                         'sub': 'Mundo Noticias · ' + ahora_txt, 'guion': guion_tit}})
    for e in extras.get('inicio', []):
        segs.append({'tipo': 'voz', 'item': e})
    cierre = {'tipo': 'voz', 'item': {'id': 'cierre', 'seccion': 'Mundo Noticias', 'set': 'noticias', 'titular': 'Gracias por acompañarnos',
                                      'sub': 'Presentador y voz generados con IA · Fuentes citadas en cada nota',
                                      'guion': 'Eso fue todo por ahora. Las noticias de este espacio vienen de fuentes oficiales, que mencionamos en cada nota. '
                                               'Josué y su voz son generados con inteligencia artificial. Nos encuentras en YouTube y Twitch como Mundo Noticias T V, y en Discord, con el enlace en la descripción. Gracias por acompañarnos en Mundo Noticias.'}}
    fijo = sum(_est(s['item']) for s in segs) + _est(cierre['item']) + sum(_est(e) for e in extras.get('fin', []))
    habla = sum(_est(n) for n in notas)
    dur_pista = sum(p['dur'] for p in pistas) / max(1, len(pistas))
    n_can = max(1, int(round((meta - fijo - habla) / dur_pista))) if pistas else 0
    # cada canción cierra un bloque; las notas se reparten parejo entre los bloques (máx. 5 por bloque)
    bloques = max(n_can, int(math.ceil(len(notas) / 5.0))) if notas else n_can
    reparto = [len(notas) // bloques + (1 if i < len(notas) % bloques else 0) for i in range(bloques)] if bloques else []
    cola, pj, seguidas = list(notas), 0, 0
    for i, cuantas in enumerate(reparto):
        for _ in range(cuantas):
            segs.append({'tipo': 'voz', 'item': cola.pop(0)})
        if i == len(reparto) // 2 and i > 0:       # resumen a mitad del bucle, para quien entra tarde
            vistas = [x['item']['titular'] for x in segs if x['tipo'] == 'voz' and x['item'].get('id') not in ('titulares',) and
                      x['item'].get('seccion') not in ('Clima', 'Tu bolsillo', 'Mundo Noticias', 'Comunidad', '¿Sabías que?', 'Hoy en la historia')][-4:]
            if len(vistas) >= 3:
                segs.append({'tipo': 'voz', 'item': {'id': 'resumen', 'seccion': 'Resumen', 'set': 'noticias', 'titular': 'Lo que va del día',
                             'sub': 'Mundo Noticias · ' + ahora_txt, 'guion': 'Si apenas nos acompañas, este es el resumen. ' + '. '.join(v.rstrip('.') for v in vistas) + '. Seguimos.'}})
        if pistas and i < n_can:
            p = pistas[pj % len(pistas)]; pj += 1
            segs.append({'tipo': 'musica', 'pista': p, 'dur': p['dur']})
            if cuantas == 0 or (i < len(reparto) - 1 and reparto[i + 1] == 0):
                segs.append(_pausa(p, franja, pj))       # canciones seguidas: Josué las presenta
    for e in extras.get('fin', []):
        segs.append({'tipo': 'voz', 'item': e})
    segs.append(cierre)
    return segs


def preparar_voces(segs, carpeta):
    """Sintetiza la voz de cada segmento hablado y calcula su duración y la apertura de boca por fotograma."""
    os.makedirs(carpeta, exist_ok=True)
    for s in segs:
        if s['tipo'] != 'voz':
            continue
        wav = os.path.join(carpeta, s['item']['id'] + '.wav')
        x, sr = vozmod.sintetizar(s['item']['guion'], wav)
        if sr != SR:  # remuestreo lineal simple
            n = int(len(x) * SR / sr)
            x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        s['voz'] = x
        s['dur'] = PAD_ANTES + len(x) / SR + PAD_DESPUES
        s['boca'] = np.concatenate([np.zeros(int(PAD_ANTES * FPS)), envolvente_boca(x, SR, FPS)])


class FlujoMusica:
    """Lee pistas WAV en bucle como muestras float estéreo."""
    def __init__(self, pistas):
        self.pistas, self.i, self.w, self.pos = pistas, 0, None, 0
        self.buf = np.zeros((0, 2), np.float32)

    def _abrir(self):
        if self.w:
            self.w.close()
        self.w = wave.open(self.pistas[self.i % len(self.pistas)]['ruta']); self.i += 1

    def leer(self, n):
        out = [self.buf]; tot = len(self.buf)
        while tot < n:
            if self.w is None or self.w.tell() >= self.w.getnframes():
                self._abrir()
            b = np.frombuffer(self.w.readframes(min(SR * 20, n - tot)), np.int16).reshape(-1, 2).astype(np.float32) / 32768
            out.append(b); tot += len(b)
        a = np.concatenate(out)
        self.buf = a[n:]
        return a[:n]


def escribir_audio(segs, pistas_fondo, ruta):
    """Mezcla voz + música de fondo (atenuada bajo la voz) y bloques de música; escribe un WAV estéreo."""
    fondo = FlujoMusica(pistas_fondo) if pistas_fondo else None
    bloque_i = 0
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        previo = 0.5
        sw = swoosh()
        for k, s in enumerate(segs):
            n = int(round(s['dur'] * SR))
            if s['tipo'] == 'voz':
                voz = np.zeros(n, np.float32)
                a = int(PAD_ANTES * SR)
                voz[a:a + len(s['voz'])] = s['voz'][: n - a]
                bed = fondo.leer(n) if fondo else np.zeros((n, 2), np.float32)
                # fondo ducking: 0.07 bajo la voz, sube un poco en las pausas
                act = np.abs(voz)
                k = SR // 5
                env = np.convolve((act > 0.01).astype(np.float32), np.ones(k, np.float32) / k, 'same')
                env = np.convolve(env, np.ones(k, np.float32) / k, 'same')
                g = 0.12 - 0.07 * np.clip(env * 1.6, 0, 1)
                mezcla = voz[:, None] * 0.92 + bed * g[:, None]
            else:
                with wave.open(s['pista']['ruta']) as pw:
                    m = np.frombuffer(pw.readframes(min(n, pw.getnframes())), np.int16).reshape(-1, 2).astype(np.float32) / 32768
                if len(m) < n:
                    m = np.concatenate([m, np.zeros((n - len(m), 2), np.float32)])
                f = min(int(2.5 * SR), n // 2)
                m[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
                mezcla = m * 0.55
            if k > 0:
                m = min(len(sw), len(mezcla)); mezcla[:m] += sw[:m]
            w.writeframes((np.clip(mezcla, -1, 1) * 32767).astype(np.int16).tobytes())


def escribir_video(segs, audio, salida, franja_nombre, loc, calidad=23, res='1280x720', ticker_items=None):
    """Anima cada segmento, une los segmentos con el pase de barrido, dibuja la barra de noticias y envía todo a ffmpeg."""
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-i', audio, '-vf', 'scale=%s:flags=lanczos,format=yuv420p' % res.replace('x', ':'), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(calidad), '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-shortest', salida]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    jos = {'noticias': Josue('traje', semilla=3), 'deportes': Josue('deportes', semilla=4)}
    set_mus = limpiar_barra(cv2.cvtColor(cv2.imread(os.path.join(RAIZ, 'assets', 'set_musica.png')), cv2.COLOR_BGR2RGB))
    ticker = Ticker(ticker_items or [])
    n_pase = int(round(SEG_PASE * FPS))
    t = 0.0
    ultimo = None
    try:
        for k, s in enumerate(segs):
            n = int(round(s['dur'] * FPS))
            if s['tipo'] == 'voz':
                it = s['item']
                j = jos[it['set']]
                cs = capas(it, franja_nombre)
            else:
                it = {'seccion': 'Música', 'titular': 'Ahora suena: ' + s['pista']['titulo'],
                      'sub': 'Música generada por Mundo Noticias · sin derechos de terceros', 'set': 'musica'}
                cs = capas(it, franja_nombre)
            for i in range(n):
                tt = t + i / FPS
                if s['tipo'] == 'voz':
                    ap = float(s['boca'][i]) if i < len(s['boca']) else 0.0
                    f = j.fotograma(tt, ap, hablando=ap > 0.05)
                else:
                    z = 1.0 + 0.006 * math.sin(2 * math.pi * tt / 18)
                    M = cv2.getRotationMatrix2D((W / 2, H * 0.55), 0, z)
                    M[0, 2] += 3 * math.sin(2 * math.pi * tt / 23)
                    f = cv2.warpAffine(set_mus, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                for c in cs:
                    c.sobre(f)
                if k > 0 and i < n_pase and ultimo is not None:
                    f = barrido(ultimo, f, (i + 1) / n_pase)
                if i == n - 1:
                    ultimo = f.copy()          # último cuadro sin la barra: la barra se dibuja siempre encima y animada
                ticker.sobre(f, tt)
                p.stdin.write(f.tobytes())
            t += n / FPS
    finally:
        p.stdin.close()
        rc = p.wait()
    if rc != 0:
        raise RuntimeError('ffmpeg terminó con código %d' % rc)


def creditos(segs, franja, loc, rutas, extra_fuentes=()):
    lin = ['MUNDO NOTICIAS · %s · %s' % (franja['nombre'], fecha_larga(loc)), '',
           'Presentador (Josué), voz y guiones generados con inteligencia artificial.',
           'Los guiones se redactan con palabras propias a partir de las fuentes citadas.', '', 'FUENTES']
    vistos = set()
    for s in segs:
        it = s.get('item')
        if it and it.get('url') and it['url'] not in vistos:
            vistos.add(it['url']); lin.append('- %s: %s (%s)' % (it['fuente'], it['url'], it['seccion']))
    lin += ['', 'MÚSICA']
    for s in segs:
        if s['tipo'] == 'musica':
            lin.append('- "%s": música ambiental generada por código de Mundo Noticias (sin muestras ni obras de terceros).' % s['pista']['titulo'])
    lin += ['', 'VOZ', '- Piper TTS (licencia MIT) con la voz es_ES-davefx-medium (licencia CC0).',
            '', 'DATOS', '- Clima: MET Norway (CC BY 4.0). Tipo de cambio: Ministerio de Hacienda.']
    return '\n'.join(dict.fromkeys(lin)) if False else '\n'.join(lin) + '\n'
