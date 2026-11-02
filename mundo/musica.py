"""Música ambiental generada por código (sin derechos de terceros): pads, notas suaves y reverberación.
Cada pista es determinista según su semilla. Licencia: la de este proyecto; sin muestras ni melodías ajenas."""
import math, os, wave
import numpy as np

SR = 44100
NOTAS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
# humor por franja: tonalidad, modo, bpm, brillo, densidad de notas, volumen de pads
HUMORES = {
    'calma':    {'tonica': 'A', 'modo': 'menor',  'bpm': 52, 'brillo': 0.25, 'notas': 0.35, 'nombres': ['Marea lenta', 'Luz de madrugada', 'Niebla en la montaña', 'Brisa nocturna', 'Cielo de Monteverde']},
    'despierta': {'tonica': 'D', 'modo': 'mayor', 'bpm': 78, 'brillo': 0.55, 'notas': 0.8, 'nombres': ['Primer café', 'Amanecer en el Valle', 'Rayos de sol', 'Camino a la escuela', 'Mañana de colibríes']},
    'marcha':   {'tonica': 'G', 'modo': 'mayor',  'bpm': 88, 'brillo': 0.6, 'notas': 0.9, 'nombres': ['Tarde en marcha', 'Ruta del mediodía', 'Calle soleada', 'Movimiento tico', 'Pasos ligeros']},
    'positivo': {'tonica': 'F', 'modo': 'mayor',  'bpm': 68, 'brillo': 0.45, 'notas': 0.6, 'nombres': ['Atardecer dorado', 'Buenas noticias', 'Hora azul', 'Luz cálida', 'Cierre del día']},
}
MAYOR, MENOR = [0, 2, 4, 5, 7, 9, 11], [0, 2, 3, 5, 7, 8, 10]
PROG_MAYOR = [[0, 2, 4], [4, 6, 8], [5, 7, 9], [3, 5, 7]]       # I  V  vi  IV (grados sobre la escala)
PROG_MENOR = [[0, 2, 4], [5, 7, 9], [2, 4, 6], [6, 8, 10]]      # i  VI III VII


def _f(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _pad(freqs, dur, brillo, rng):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for fr in freqs:
        for det in (-0.12, 0.0, 0.12):
            f = fr * 2 ** (det / 12)
            y += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) + brillo * 0.35 * np.sin(2 * np.pi * 2 * f * t + rng.uniform(0, 6.28))
    a, r = min(dur * 0.35, 2.2), min(dur * 0.4, 2.8)
    env = np.minimum(1, t / a) * np.minimum(1, (dur - t) / r)
    return (y * env ** 1.5 / (len(freqs) * 3)).astype(np.float32)


def _pluck(f, dur=2.4):
    t = np.arange(int(dur * SR)) / SR
    y = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)) * np.exp(-t * 2.2)
    y *= np.minimum(1, t / 0.008)
    return y.astype(np.float32)


def _reverb(x, rng, seg=3.2, mezcla=0.38):
    n = int(seg * SR)
    ir = rng.standard_normal(n).astype(np.float32) * np.exp(-np.arange(n) / (0.55 * SR))
    ir /= np.sqrt((ir ** 2).sum())
    N = 1 << int(np.ceil(np.log2(len(x) + n)))
    w = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[: len(x)].astype(np.float32)
    return x * (1 - mezcla) + w * mezcla


def generar_pista(franja, semilla, minutos=4.5):
    h = HUMORES[franja]
    rng = np.random.default_rng(semilla)
    escala = MAYOR if h['modo'] == 'mayor' else MENOR
    prog = PROG_MAYOR if h['modo'] == 'mayor' else PROG_MENOR
    raiz = 48 + NOTAS[h['tonica']] % 12
    def grado(g):
        return raiz + escala[g % 7] + 12 * (g // 7)
    total = minutos * 60
    comp = 4 * 60 / h['bpm'] * (2 if franja in ('calma', 'positivo') else 1)   # duración de un acorde
    n_acordes = int(total / comp)
    L = int(n_acordes * comp * SR)
    izq, der = np.zeros(L + 4 * SR, np.float32), np.zeros(L + 4 * SR, np.float32)
    for i in range(n_acordes):
        ac = prog[i % 4]
        pos = int(i * comp * SR)
        freqs = [_f(grado(g)) for g in ac] + [_f(grado(ac[0]) - 12)]
        p = _pad(freqs, comp + 2.0, h['brillo'], rng)
        izq[pos:pos + len(p)] += p * 0.9
        der[pos:pos + len(p)] += p * 0.9
        # notas sueltas sobre la pentatónica del acorde
        pent = [grado(g) + 12 for g in (ac[0], ac[1], ac[2], ac[0] + 1, ac[2] + 1)]
        paso = 60 / h['bpm'] / 2
        t = 0.0
        while t < comp - 0.5:
            if rng.random() < h['notas'] * 0.45:
                f = _f(int(rng.choice(pent)) + (12 if rng.random() < 0.25 else 0))
                y = _pluck(f) * rng.uniform(0.10, 0.2)
                s = pos + int(t * SR); lado = rng.uniform(0.25, 0.75)
                m = min(len(y), len(izq) - s)
                izq[s:s + m] += y[:m] * (1 - lado) * 1.6
                der[s:s + m] += y[:m] * lado * 1.6
            t += paso
    izq, der = _reverb(izq[:L], rng), _reverb(der[:L], rng)
    # entrada y salida suaves para que se pueda encadenar sin clics
    f = min(int(2.5 * SR), L // 4)
    rampa = np.linspace(0, 1, f, dtype=np.float32)
    for c in (izq, der):
        c[:f] *= rampa; c[-f:] *= rampa[::-1]
    est = np.stack([izq, der], 1)
    est /= (np.abs(est).max() + 1e-9)
    return (est * 0.8).astype(np.float32), h['nombres'][semilla % len(h['nombres'])]


def guardar_wav(est, ruta):
    with wave.open(ruta, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(est, -1, 1) * 32767).astype(np.int16).tobytes())


def pistas(franja, carpeta, cantidad=3, semilla_base=0, minutos=4.5):
    """Genera (o reutiliza de la caché) pistas de la franja. Devuelve [{'titulo','ruta'}]."""
    os.makedirs(carpeta, exist_ok=True)
    out = []
    for k in range(cantidad):
        sem = semilla_base + k
        ruta = os.path.join(carpeta, '%s_%d_%d.wav' % (franja, sem, int(minutos * 10)))
        titulo = HUMORES[franja]['nombres'][sem % 5]
        if not os.path.exists(ruta):
            est, titulo = generar_pista(franja, sem, minutos)
            guardar_wav(est, ruta)
        out.append({'titulo': titulo, 'ruta': ruta})
    return out
