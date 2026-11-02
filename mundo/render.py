"""Rótulos del programa dibujados con Pillow (sin navegador): logo, etiqueta IA, chip de sección y tercio inferior."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1672, 941
_F = {}


def fuente(peso, tam):
    k = (peso, tam)
    if k not in _F:
        _F[k] = ImageFont.truetype(os.path.join(RAIZ, 'fuentes_tipograficas', 'Inter-%s.otf' % peso), tam)
    return _F[k]


class Capa:
    """Un recorte RGBA con su posición, listo para mezclar rápido sobre un fotograma."""
    def __init__(self, img, x, y):
        a = np.asarray(img.convert('RGBA'), dtype=np.float32)
        self.x, self.y = x, y
        self.h, self.w = a.shape[:2]
        self.rgb = a[..., :3]
        self.a = (a[..., 3:] / 255.0)
        self.rgba = self.rgb * self.a

    def sobre(self, frame):
        r = frame[self.y:self.y + self.h, self.x:self.x + self.w]
        r[:] = (r * (1 - self.a) + self.rgba).astype(np.uint8)


def _ajustar(draw, texto, peso, ancho, alto, max_tam=67, min_tam=34):
    """Devuelve (fuente, líneas) más grande que quepa en ancho x alto, hasta 2 líneas."""
    for tam in range(max_tam, min_tam - 1, -1):
        f = fuente(peso, tam)
        pal, lineas, cur = texto.split(), [], ''
        for p in pal:
            prueba = (cur + ' ' + p).strip()
            if draw.textlength(prueba, font=f) <= ancho:
                cur = prueba
            else:
                lineas.append(cur); cur = p
        lineas.append(cur)
        if len(lineas) * tam * 1.08 <= alto and all(draw.textlength(l, font=f) <= ancho for l in lineas):
            return f, lineas
    f = fuente(peso, min_tam)
    return f, [texto[:60] + '…']


def capas(item, franja):
    """Devuelve la lista de Capa para este ítem. item: seccion, titular, sub, set."""
    out = []
    # barra superior: logo + etiqueta IA
    barra = Image.new('RGBA', (1300, 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(barra)
    f1 = fuente('ExtraBold', 41)
    d.text((0, 35), 'MUNDO', font=f1, fill=(255, 255, 255, 255), anchor='lm')
    d.text((d.textlength('MUNDO', font=f1) + 14, 35), 'NOTICIAS', font=f1, fill=(141, 183, 255, 255), anchor='lm')
    f2 = fuente('SemiBold', 25)
    d.text((1246, 35), 'Presentador y voz generados con IA', font=f2, fill=(255, 255, 255, 210), anchor='rm')
    out.append(Capa(barra, 158, 13))
    # chip de sección + franja
    f3, f4 = fuente('ExtraBold', 33), fuente('SemiBold', 25)
    t1, t2 = item['seccion'].upper(), franja
    ancho = int(max(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t1, font=f3),
                    ImageDraw.Draw(Image.new('L', (1, 1))).textlength(t2, font=f4))) + 60
    chip = Image.new('RGBA', (ancho, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    d.rounded_rectangle((0, 0, ancho - 1, 95), radius=13, fill=(5, 18, 52, 189))
    d.rectangle((0, 0, 8, 95), fill=(91, 147, 245, 255))
    d.text((30, 30), t1, font=f3, fill=(255, 255, 255, 255), anchor='lm')
    d.text((30, 68), t2, font=f4, fill=(255, 255, 255, 225), anchor='lm')
    out.append(Capa(chip, 50, 127))
    # tercio inferior (la banda del set empieza en y=706)
    tercio = Image.new('RGBA', (1330, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(tercio)
    f, lineas = _ajustar(d, item['titular'], 'ExtraBold', 1304, 88)
    alto = len(lineas) * f.size * 1.08
    y = (88 - alto) / 2
    for l in lineas:
        d.text((0, y), l, font=f, fill=(7, 23, 63, 255)); y += f.size * 1.08
    fs = fuente('SemiBold', 27)
    sub = item['sub']
    while d.textlength(sub, font=fs) > 1304 and len(sub) > 10:
        sub = sub[:-2].rstrip() + '…'
    d.text((0, 91), sub, font=fs, fill=(43, 62, 112, 255))
    out.append(Capa(tercio, 145, 712))
    return out
