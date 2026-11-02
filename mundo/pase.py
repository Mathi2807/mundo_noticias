"""Pase televisivo entre segmentos: barrido diagonal con banda azul de marca y su sonido 'swoosh'."""
import numpy as np

W, H = 1672, 941
SR = 44100
SEG_PASE = 0.56                       # duración del barrido en segundos
_G = np.add.outer(np.arange(H, dtype=np.float32) * 0.35, np.arange(W, dtype=np.float32))   # x + 0.35·y
AZUL = np.array([91, 147, 245], np.float32)


def barrido(a, b, p):
    """Mezcla el cuadro anterior `a` con el nuevo `b` (uint8 HxWx3). p: avance de 0 a 1."""
    e = p * p * (3 - 2 * p)
    borde = -90 + e * (W + 0.35 * H + 180)
    d = borde - _G                                  # >0: ya se ve el cuadro nuevo
    rev = np.clip(d / 8.0, 0, 1)[..., None]
    out = a.astype(np.float32) * (1 - rev) + b.astype(np.float32) * rev
    banda = np.clip(1 - np.abs(d - 40) / 46, 0, 1)[..., None] * 0.9
    out = out * (1 - banda) + AZUL * banda
    linea = np.clip(1 - np.abs(d - 2) / 3.5, 0, 1)[..., None]
    out = out * (1 - linea) + 255.0 * linea
    return np.clip(out, 0, 255).astype(np.uint8)


def swoosh(dur=SEG_PASE, volumen=0.30, semilla=7):
    """Barrido de ruido filtrado que sube de tono, con un golpe grave suave al inicio. Devuelve (n,2) float32."""
    rng = np.random.default_rng(semilla)
    n = int(dur * SR)
    t = np.arange(n) / SR
    ruido = rng.standard_normal(n).astype(np.float32)
    # filtro pasa-banda móvil: se mezcla ruido con versiones suavizadas a distintas escalas
    def media(x, k):
        c = np.cumsum(np.insert(x, 0, 0)); return (c[k:] - c[:-k]) / k
    alto = ruido - np.pad(media(ruido, 24), (12, 11))[:n]
    medio = np.pad(media(ruido, 24), (12, 11))[:n] - np.pad(media(ruido, 160), (80, 79))[:n]
    mezcla = alto * np.clip(t / dur * 2 - 0.3, 0, 1) + medio * np.clip(1.2 - t / dur * 1.4, 0, 1)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    golpe = np.sin(2 * np.pi * (70 - 25 * t) * t) * np.exp(-t * 14) * 0.9
    y = (mezcla * env * 0.8 + golpe)
    y = y / (np.abs(y).max() + 1e-9) * volumen
    izq = y * np.linspace(1.0, 0.75, n); der = y * np.linspace(0.75, 1.0, n)   # recorre el panorama de izq. a der.
    return np.stack([izq, der], 1).astype(np.float32)
