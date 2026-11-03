"""Clips verticales (9:16) de 60 a 90 s para Shorts, TikTok, Reels y Facebook, hechos a partir del bucle ya renderizado.
Cada clip junta 2-4 notas seguidas de Josué, con subtítulos grandes, título de la nota y una invitación a tus redes.
Salen como .mp4 + .txt (título y descripción sugeridos con fuentes y enlaces)."""
import json, os, re, subprocess, tempfile, textwrap
from datetime import datetime, timedelta

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .render import Capa, fuente, _ajustar

W, H = 720, 1280
FPS = 25
SW, SH = 1280, 720                      # tamaño del video fuente
CROP = (250, 80, 970, 540)              # zona de Josué dentro del cuadro fuente (x0, y0, x1, y1): 720 x 460
Y_JOSUE = 150
PAD_ANTES, PAD_DESPUES = 0.75, 0.45
MIN_S, MAX_S = 60.0, 92.0
NO_CLIP = ('titulares', 'resumen', 'cierre')
NO_CLIP_PREF = ('pausa', 'promo', 'sabias', 'efemeride')
AZUL, OSCURO = (91, 147, 245), (7, 23, 63)


def _texto_c(draw, xy, txt, f, fill, **kw):
    draw.text(xy, txt, font=f, fill=fill, anchor='mm', **kw)


def _marca():
    im = Image.new('RGBA', (W, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = fuente('ExtraBold', 46)
    a, b = d.textlength('MUNDO ', font=f), d.textlength('NOTICIAS', font=f)
    x = (W - a - b) / 2
    d.text((x, 34), 'MUNDO ', font=f, fill=(255, 255, 255, 255), anchor='lm', stroke_width=3, stroke_fill=(5, 15, 40, 255))
    d.text((x + a, 34), 'NOTICIAS', font=f, fill=AZUL + (255,), anchor='lm', stroke_width=3, stroke_fill=(5, 15, 40, 255))
    d.rounded_rectangle((W / 2 - 112, 70, W / 2 + 112, 106), radius=18, fill=(5, 18, 52, 215))
    d.ellipse((W / 2 - 92, 80, W / 2 - 76, 96), fill=(255, 80, 80, 255))
    _texto_c(d, (W / 2 + 12, 88), 'EN VIVO 24/7', fuente('ExtraBold', 22), (255, 255, 255, 255))
    return Capa(im, 0, 36)


def _tarjeta(seccion, titular, sub):
    im = Image.new('RGBA', (672, 196), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 671, 195), radius=24, fill=(244, 247, 255, 240))
    d.rounded_rectangle((0, 0, 14, 195), radius=7, fill=AZUL + (255,))
    d.text((34, 24), seccion.upper(), font=fuente('ExtraBold', 22), fill=(40, 90, 200, 255), anchor='lm')
    f, lineas = _ajustar(d, titular, 'ExtraBold', 616, 98, max_tam=40, min_tam=26)
    y = 44
    for l in lineas[:2]:
        d.text((34, y), l, font=f, fill=OSCURO + (255,)); y += f.size * 1.1
    fs = fuente('SemiBold', 21); s = sub
    while d.textlength(s, font=fs) > 616 and len(s) > 10:
        s = s[:-2].rstrip() + '…'
    d.text((34, 168), s, font=fs, fill=(43, 62, 112, 255), anchor='lm')
    return Capa(im, 24, 640)


def _cta():
    im = Image.new('RGBA', (672, 92), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, 671, 91), radius=22, fill=(5, 18, 52, 220))
    _texto_c(d, (336, 31), 'Síguenos: YouTube · Twitch · Discord', fuente('ExtraBold', 28), (255, 255, 255, 255))
    _texto_c(d, (336, 66), 'twitch.tv/mundonoticiastv  ·  discord.gg/g7f8SF6eqb', fuente('SemiBold', 21), (190, 210, 255, 255))
    return Capa(im, 24, 1060)


def _subtitulo(txt):
    im = Image.new('RGBA', (W, 200), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lineas = textwrap.wrap(txt, 19)[:3]
    f = fuente('ExtraBold', 56)
    y0 = 100 - (len(lineas) - 1) * 31
    for i, l in enumerate(lineas):
        d.text((W / 2, y0 + i * 62), l, font=f, fill=(255, 255, 255, 255), anchor='mm', stroke_width=7, stroke_fill=(5, 15, 40, 255))
    return Capa(im, 0, 850)


def _trozos(guion, t0, t1):
    """Reparte las palabras del guion entre t0 y t1 (proporcional a las letras) en trozos de 3-5 palabras."""
    pal = guion.split()
    trozos, cur = [], []
    for p in pal:
        cur.append(p)
        if len(cur) >= 5 or len(' '.join(cur)) >= 26 or re.search(r'[.;:!?]$', p):
            trozos.append(cur); cur = []
    if cur:
        trozos.append(cur)
    letras = [sum(len(w) + 1 for w in t) for t in trozos]
    tot = float(sum(letras)) or 1.0
    out, t = [], t0
    for tr, n in zip(trozos, letras):
        d = (t1 - t0) * n / tot
        out.append((t, t + d, ' '.join(tr))); t += d
    return out


def elegir_grupos(segmentos, maximo=5):
    """Agrupa notas consecutivas (originales, no de repaso) hasta 60-92 s. Devuelve listas de segmentos."""
    cand = [s for k, s in enumerate(segmentos) if k > 0 and s['tipo'] == 'voz' and s['id'] not in NO_CLIP and not s['id'].startswith(NO_CLIP_PREF)
            and not s.get('extra') and not s.get('repaso') and s.get('guion')]
    grupos, cur, tot = [], [], 0.0
    for s in cand:
        d = s['dur_real'] - 0.75
        if tot + d <= MAX_S:
            cur.append(s); tot += d
        elif tot >= MIN_S:
            grupos.append(cur); cur, tot = [s], d
        # si aún no llega al mínimo y esta nota no cabe, se salta
        if tot >= MIN_S and tot >= MAX_S - 12:
            grupos.append(cur); cur, tot = [], 0.0
        if len(grupos) >= maximo:
            break
    if cur and tot >= MIN_S and len(grupos) < maximo:
        grupos.append(cur)
    return grupos


def _cortar(video, grupo, tmp):
    partes = []
    for i, s in enumerate(grupo):
        ini = s['inicio_s'] + 0.7
        dur = s['dur_real'] - 0.7 - 0.05
        ruta = os.path.join(tmp, 'p%d.mp4' % i)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '%.3f' % ini, '-i', video, '-t', '%.3f' % dur, '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-crf', '18', '-r', str(FPS), '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-ac', '2', ruta], check=True)
        partes.append(ruta)
    lst = os.path.join(tmp, 'l.txt'); open(lst, 'w').write(''.join("file '%s'\n" % p for p in partes))
    unido = os.path.join(tmp, 'unido.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', unido], check=True)
    return unido


def _componer(unido, grupo, salida):
    # línea de tiempo del clip: cada nota empieza donde terminó la anterior
    marca, cta = _marca(), _cta()
    tarjetas, subs, t = [], [], 0.0
    for s in grupo:
        dur = s['dur_real'] - 0.75
        tarjetas.append((t, t + dur, _tarjeta(s['seccion'], s['titular'], s.get('sub', ''))))
        v0 = t + (PAD_ANTES - 0.7)
        for a, b, txt in _trozos(s['guion'], v0, t + dur - PAD_DESPUES):
            subs.append((a, b, _subtitulo(txt)))
        t += dur
    total = t
    rd = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', unido, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (SW, SH), '-'], stdout=subprocess.PIPE)
    wr = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-', '-i', unido,
                           '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
                           '-af', 'afade=t=in:st=0:d=0.2,afade=t=out:st=%.2f:d=0.4' % max(0, total - 0.5), '-shortest', '-movflags', '+faststart', salida], stdin=subprocess.PIPE)
    n, x0, y0, x1, y1 = 0, CROP[0], CROP[1], CROP[2], CROP[3]
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sm = cv2.cvtColor(cv2.imread(os.path.join(raiz, 'assets', 'set_musica.png')), cv2.COLOR_BGR2RGB)
    limpio = cv2.resize(sm, (SW, SH), interpolation=cv2.INTER_AREA)           # set sin rótulos: sirve de parche y de fondo
    fondo = (cv2.resize(cv2.resize(sm, (72, 128), interpolation=cv2.INTER_AREA), (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) * 0.6).astype(np.uint8)
    nbytes = SW * SH * 3
    try:
        while True:
            buf = rd.stdout.read(nbytes)
            if len(buf) < nbytes:
                break
            fr = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            tt = n / FPS
            fr = fr.copy()
            fr[88:184, x0:500] = limpio[88:184, x0:500]          # tapa el chip de sección del video original
            bg = fondo.copy()
            bg[Y_JOSUE:Y_JOSUE + (y1 - y0)] = fr[y0:y1, x0:x1]
            marca.sobre(bg)
            for a, b, c in tarjetas:
                if a <= tt < b: c.sobre(bg); break
            for a, b, c in subs:
                if a <= tt < b: c.sobre(bg); break
            cta.sobre(bg)
            wr.stdin.write(bg.tobytes()); n += 1
    finally:
        rd.stdout.close(); rd.wait()
        wr.stdin.close(); rc = wr.wait()
    if rc != 0:
        raise RuntimeError('ffmpeg (clip) terminó con código %d' % rc)
    return total


def _descripcion(grupo, redes, hashtags='#CostaRica #NoticiasCR #MundoNoticias #Noticias'):
    titulo = grupo[0]['titular'].rstrip('.')
    if len(titulo) > 84:
        titulo = titulo[:83].rstrip() + '…'
    l = [titulo + ' | Mundo Noticias', '', 'En este clip:']
    for s in grupo:
        l.append('• %s — Fuente: %s%s' % (s['titular'], s.get('fuente') or 'Mundo Noticias', (' · ' + s['url']) if s.get('url') else ''))
    l += ['', 'Noticias de Costa Rica y el mundo, 24/7, con Josué (presentador y voz generados con IA).',
          'YouTube: ' + redes['youtube']['url'], 'Twitch: ' + redes['twitch']['url'], 'Discord: ' + redes['discord']['url'], '', hashtags]
    return '\n'.join(l)


def generar(video, lista_json, salida, redes, maximo=5):
    d = json.load(open(lista_json, encoding='utf-8'))
    os.makedirs(salida, exist_ok=True)
    try:
        cr = datetime.fromisoformat(d['destino_utc']) + timedelta(hours=-6)
    except Exception:
        cr = datetime.utcnow() + timedelta(hours=-6)
    base = 'clip_%s' % cr.strftime('%Y%m%d_%H%M')
    grupos = elegir_grupos(d['segmentos'], maximo)
    hechos = 0
    for i, g in enumerate(grupos, 1):
        nombre = os.path.join(salida, '%s_%02d' % (base, i))
        with tempfile.TemporaryDirectory() as tmp:
            try:
                unido = _cortar(video, g, tmp)
                dur = _componer(unido, g, nombre + '.mp4')
            except Exception as e:
                print('Clip %d falló: %s' % (i, e), flush=True); continue
        open(nombre + '.txt', 'w', encoding='utf-8').write(_descripcion(g, redes))
        print('Clip %s: %.0f s, %d notas' % (os.path.basename(nombre), dur, len(g)), flush=True); hechos += 1
    return hechos
