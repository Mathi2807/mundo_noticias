"""Barra inferior de noticias pasantes: etiquetas de color por sección y texto que se desplaza sin parar."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .render import fuente

COLORES = {
    'ACONTECIMIENTOS': (91, 147, 245), 'DEPORTES': (52, 199, 130), 'CLIMA': (84, 208, 232), 'TU BOLSILLO': (245, 184, 66),
    'INTERNACIONAL': (160, 132, 245), 'SALUD': (246, 112, 120), 'EDUCACIÓN': (110, 190, 255), 'AMBIENTE': (120, 210, 90),
    'CIENCIA': (96, 220, 200), 'CULTURA': (240, 140, 200), 'TRÁMITES': (240, 160, 90), 'EMPRENDEDORES': (230, 200, 90),
}
ETIQUETA_DE = {
    'Nacionales': 'ACONTECIMIENTOS', 'Internacionales': 'INTERNACIONAL', 'Deportes': 'DEPORTES', 'Tu bolsillo': 'TU BOLSILLO',
    'Trámites y servicios': 'TRÁMITES', 'Salud y bienestar': 'SALUD', 'Educación y becas': 'EDUCACIÓN',
    'Ambiente y naturaleza': 'AMBIENTE', 'Tecnología y ciencia': 'CIENCIA', 'Cultura y entretenimiento': 'CULTURA',
    'Orgullo tico': 'ACONTECIMIENTOS', 'Emprendedores': 'EMPRENDEDORES', 'Buenas noticias del día': 'ACONTECIMIENTOS',
    'Clima': 'CLIMA',
}
X0, X1 = 82, 1340          # ventana visible dentro de la barra del set
Y0, ALTO = 868, 48
VELOCIDAD = 130            # píxeles por segundo


class Ticker:
    def __init__(self, items, velocidad=VELOCIDAD, orden_por_seccion=True):
        """items: lista de (etiqueta, texto). Se agrupan por sección para que 'pasen' ordenadas."""
        items = [(e if e in COLORES else 'ACONTECIMIENTOS', t) for e, t in items if t]
        if not items:
            items = [('ACONTECIMIENTOS', 'Mundo Noticias · Presentador y voz generados con IA')]
        if orden_por_seccion:
            orden = list(dict.fromkeys(e for e, _ in items))
            items = [x for e in orden for x in items if x[0] == e]
        self.vel = velocidad
        self.ancho_vis = X1 - X0
        self.tira = self._dibujar(items)
        self.largo = self.tira.shape[1] // 2
        self.alfa = np.ones(self.ancho_vis, np.float32)
        r = np.linspace(0, 1, 46, dtype=np.float32)
        self.alfa[:46] = r; self.alfa[-46:] = r[::-1]

    def _dibujar(self, items):
        ft, fe = fuente('SemiBold', 25), fuente('ExtraBold', 17)
        tmp = ImageDraw.Draw(Image.new('L', (1, 1)))
        partes, x = [], 0
        for et, txt in items:
            wl = int(tmp.textlength(et, font=fe)) + 22
            wt = int(tmp.textlength(txt, font=ft))
            partes.append((et, txt, x, wl, wt)); x += wl + 12 + wt + 70
        total = max(x, self.ancho_vis + 200)
        # se repite la tira hasta llenar al menos dos ventanas, para el bucle continuo
        reps = 1
        while total * reps < self.ancho_vis * 2:
            reps += 1
        ancho = total * reps
        im = Image.new('RGBA', (ancho * 2, ALTO), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for r in range(reps * 2):
            for et, txt, x0, wl, wt in partes:
                x = x0 + r * total
                col = COLORES[et]
                d.rounded_rectangle((x, 9, x + wl, 9 + 30), radius=8, fill=col + (255,))
                d.text((x + wl / 2, 24), et, font=fe, fill=(6, 20, 52, 255), anchor='mm')
                d.text((x + wl + 12, 24), txt, font=ft, fill=(240, 246, 255, 255), anchor='lm')
        self._total = total * reps
        a = np.asarray(im, dtype=np.float32)
        return a

    def sobre(self, frame, t):
        off = int(t * self.vel) % self._total
        v = self.tira[:, off:off + self.ancho_vis]
        al = (v[..., 3] / 255.0) * self.alfa[None, :]
        reg = frame[Y0:Y0 + ALTO, X0:X1]
        reg[:] = (reg * (1 - al[..., None]) + v[..., :3] * al[..., None]).astype(np.uint8)
