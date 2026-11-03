"""Animación procedural de Josué: boca (labios sincronizados con la voz), parpadeo y movimiento natural."""
import json, math, os, random
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def envolvente_boca(muestras, sr, fps, ataque=0.04, soltar=0.09):
    """Del audio (float mono) saca la apertura de boca 0..1 por fotograma."""
    x = np.asarray(muestras, dtype=np.float32)
    n = int(len(x) / sr * fps) + 1
    paso = sr / fps
    rms = np.zeros(n, np.float32)
    cruces = np.zeros(n, np.float32)
    for i in range(n):
        seg = x[int(i * paso): int((i + 1) * paso)]
        if len(seg):
            rms[i] = math.sqrt(float(np.mean(seg * seg)))
            cruces[i] = float(np.mean(np.abs(np.diff(np.sign(seg))) > 0)) if len(seg) > 1 else 0
    ref = np.percentile(rms[rms > 1e-4], 92) if np.any(rms > 1e-4) else 1.0
    a = np.clip(rms / (ref + 1e-9), 0, 1) ** 0.7
    # consonantes sibilantes (muchos cruces por cero): boca poco abierta
    a *= (1 - 0.45 * np.clip((cruces - 0.25) / 0.25, 0, 1))
    a[rms < 0.004] = 0
    out = np.zeros_like(a)
    ka, kr = 1 - math.exp(-1 / (ataque * fps)), 1 - math.exp(-1 / (soltar * fps))
    v = 0.0
    for i, t in enumerate(a):
        v += (t - v) * (ka if t > v else kr)
        out[i] = v
    return np.clip(out, 0, 1)


def _suave(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


class Josue:
    def __init__(self, atuendo, plate_path=None, semilla=1):
        cfg = json.load(open(os.path.join(RAIZ, 'config', 'personaje.json')))
        c = cfg[atuendo]
        self.c = c
        self.pivote = tuple(cfg['pivote'])
        self.banda = cfg['banda_rotulo_y']
        pr = cv2.imread(os.path.join(RAIZ, c['imagen']), cv2.IMREAD_UNCHANGED)
        self.rgb = cv2.cvtColor(pr[:, :, :3], cv2.COLOR_BGR2RGB)
        self.alfa = pr[:, :, 3].astype(np.float32) / 255.0
        self.plate = cv2.cvtColor(cv2.imread(plate_path or os.path.join(RAIZ, 'assets', 'plate.png')), cv2.COLOR_BGR2RGB)
        from .render import limpiar_barra
        limpiar_barra(self.plate)
        # trabajo solo sobre el recorte donde está Josué (mucho más rápido); las coordenadas se desplazan al recorte
        ys, xs = np.where(self.alfa > 0.02)
        self.oy, self.ox = int(max(0, ys.min() - 24)), int(max(0, xs.min() - 24))
        ye, xe = int(min(self.alfa.shape[0], ys.max() + 25)), int(min(self.alfa.shape[1], xs.max() + 25))
        self.full_h, self.full_w = self.alfa.shape
        self.rgb, self.alfa = self.rgb[self.oy:ye, self.ox:xe].copy(), self.alfa[self.oy:ye, self.ox:xe].copy()
        self.plate_full = self.plate
        self.plate = self.plate_full[self.oy:ye, self.ox:xe].copy()
        self.H, self.W = self.rgb.shape[:2]
        c = json.loads(json.dumps(c))
        c['boca']['cx'] -= self.ox; c['boca']['y'] -= self.oy
        c['ojos'] = [[a - self.ox, b - self.oy] for a, b in c['ojos']]
        self.c = c
        self.pivote = (float(self.pivote[0] - self.ox), float(self.pivote[1] - self.oy))
        self.banda = max(0, self.banda - self.oy)
        self.roi = (self.oy, ye, self.ox, xe)
        self.rng = random.Random(semilla)
        self.proximo_parpadeo = 1.5
        self.inicio_parpadeo = -9
        self.fase = [self.rng.uniform(0, 6.28) for _ in range(4)]
        # recorte de la cara reutilizable
        b = c['boca']
        self.x0, self.x1 = int(b['cx'] - 90), int(b['cx'] + 90)
        self.y0, self.y1 = int(b['y'] - 30), int(b['y'] + 85)
        yy, xx = np.mgrid[self.y0:self.y1, self.x0:self.x1].astype(np.float32)
        self.yy, self.xx = yy, xx
        self.wx = np.exp(-0.5 * ((xx - b['cx']) / (b['ancho'] * 0.5)) ** 2)
        dy = yy - b['y']
        self.wy = np.where(dy < -2, 0.0, np.where(dy < 3, _suave((dy + 2) / 5), np.where(dy < 28, 1.0, 1 - _suave((dy - 28) / 50))))
        self.wy = self.wy.astype(np.float32)

    def parpadeo(self, t):
        if t >= self.proximo_parpadeo:
            self.inicio_parpadeo = t
            self.proximo_parpadeo = t + self.rng.uniform(2.5, 5.5)
            if self.rng.random() < 0.18:
                self.proximo_parpadeo = t + 0.35  # parpadeo doble ocasional
        u = (t - self.inicio_parpadeo) / 0.16
        return float(math.sin(math.pi * u)) if 0 <= u <= 1 else 0.0

    def _boca(self, img, ap):
        b = self.c['boca']
        o = ap * b['apertura_max']
        if o < 0.6:
            return
        sub = img[self.y0:self.y1, self.x0:self.x1].astype(np.float32)
        d = o * self.wx * self.wy
        mapy = (self.yy - d - self.y0).astype(np.float32)
        mapx = (self.xx - self.x0).astype(np.float32)
        mov = cv2.remap(sub, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # hueco entre el labio superior y el inferior desplazado
        hueco = ((self.yy >= b['y']) & (self.yy < b['y'] + d - 1.0)).astype(np.float32)
        hueco = cv2.GaussianBlur(hueco, (0, 0), 0.9)[..., None]
        prof = np.clip((self.yy - b['y']) / np.maximum(d, 1), 0, 1)[..., None]
        interior = np.array([52, 20, 26], np.float32) * (1 - 0.35 * prof) + np.array([95, 38, 44], np.float32) * (0.35 * prof)
        # dientes superiores: franja clara pegada al labio de arriba
        dient = ((self.yy >= b['y']) & (self.yy < b['y'] + np.minimum(d * 0.3, 3.5) - 1.0)).astype(np.float32)
        dient = cv2.GaussianBlur(dient, (0, 0), 0.8)[..., None] * min(1.0, max(0.0, (o - 4) / 5))
        interior = interior * (1 - dient * 0.9) + np.array([205, 192, 182], np.float32) * dient * 0.9
        res = mov * (1 - hueco) + interior * hueco
        img[self.y0:self.y1, self.x0:self.x1] = np.clip(res, 0, 255).astype(np.uint8)

    def _ojos(self, img, cierre):
        if cierre < 0.08:
            return
        for (ex, ey) in self.c['ojos']:
            rx, ry = 19, 7
            ys, xs = int(ey - 22), int(ex - rx - 8)
            ye, xe = int(ey + 18), int(ex + rx + 8)
            reg = img[ys:ye, xs:xe].astype(np.float32)
            piel = img[int(ey - 12): int(ey - 8), int(ex - 10): int(ex + 10)].reshape(-1, 3).mean(0) * 0.92
            lim = (ey - ry) + (2 * ry) * cierre - ys          # borde inferior del párpado que baja
            m = np.zeros(reg.shape[:2], np.float32)
            cv2.ellipse(m, (int(ex - xs), int(ey - ys)), (rx + 2, ry + 3), 0, 0, 360, 1, -1)
            mm = np.arange(reg.shape[0], dtype=np.float32)[:, None]
            m *= (mm <= lim).astype(np.float32)
            m = cv2.GaussianBlur(m, (0, 0), 1.0)[..., None]
            lin = np.zeros(reg.shape[:2], np.float32)
            cv2.ellipse(lin, (int(ex - xs), int(lim) - 2), (rx - 1, 3), 0, 10, 170, 1, 1)
            lin = cv2.GaussianBlur(lin, (0, 0), 0.8)[..., None] * 0.6 * min(1, cierre * 1.6)
            reg = reg * (1 - m) + piel * m
            reg = reg * (1 - lin) + np.array([38, 24, 20], np.float32) * lin
            img[ys:ye, xs:xe] = np.clip(reg, 0, 255).astype(np.uint8)

    def fotograma(self, t, apertura=0.0, hablando=True):
        """Devuelve el cuadro RGB (H,W,3) uint8 con plate + Josué animado."""
        cara = self.rgb.copy()
        self._boca(cara, apertura)
        self._ojos(cara, self.parpadeo(t))
        f = self.fase
        amp = 1.0 if hablando else 0.7
        dx = amp * (1.1 * math.sin(2 * math.pi * t / 6.1 + f[0]) + 0.4 * math.sin(2 * math.pi * t / 2.3 + f[1]))
        dy = 0.9 * math.sin(2 * math.pi * t / 4.2 + f[2]) + 0.8 * apertura  # respiración + asentir al hablar
        rot = 0.30 * math.sin(2 * math.pi * t / 7.3 + f[3]) * amp
        M = cv2.getRotationMatrix2D(self.pivote, rot, 1.0)
        M[0, 2] += dx
        M[1, 2] += dy
        flags = cv2.INTER_LINEAR
        rgb = cv2.warpAffine(cara, M, (self.W, self.H), flags=flags, borderMode=cv2.BORDER_REPLICATE)
        al = cv2.warpAffine(self.alfa, M, (self.W, self.H), flags=flags, borderValue=0)
        out = self.plate.astype(np.float32) * (1 - al[..., None]) + rgb.astype(np.float32) * al[..., None]
        roi = out.astype(np.uint8)
        roi[self.banda:] = self.plate[self.banda:]
        full = self.plate_full.copy()
        y0, y1, x0, x1 = self.roi
        full[y0:y1, x0:x1] = roi
        return full
