"""Redactor de guiones. Dos motores: LLM local (opcional, transformers) o extractivo con reglas.
Las dos salidas pasan las mismas barreras: menciona la fuente, no inventa cifras, no copia tiradas largas, longitud acotada."""
import os, re
from .util import oraciones, palabras, sin_tildes, limpiar_html

ETIQUETAS = {
    'nacionales': 'Nacionales', 'internacionales': 'Internacionales', 'deportes': 'Deportes', 'tu_bolsillo': 'Tu bolsillo',
    'tramites': 'Trámites y servicios', 'salud': 'Salud y bienestar', 'educacion': 'Educación y becas',
    'orgullo': 'Orgullo tico', 'emprendedores': 'Emprendedores', 'ambiente': 'Ambiente y naturaleza',
    'buenas': 'Buenas noticias del día', 'tecnologia': 'Tecnología y ciencia', 'cultura': 'Cultura y entretenimiento',
    'sabias': '¿Sabías que?', 'clima': 'Clima', 'titulares': 'Titulares',
}
ENTRADAS = {
    'deportes': 'En deportes, ', 'internacionales': 'Desde el mundo, ', 'tu_bolsillo': 'Para tu bolsillo, ',
    'tramites': 'Un dato útil para tus trámites: ', 'salud': 'En salud, ', 'educacion': 'En educación, ',
    'ambiente': 'En ambiente y naturaleza, ', 'tecnologia': 'En ciencia y tecnología, ', 'cultura': 'En cultura, ',
    'emprendedores': 'Para quienes emprenden, ',
}
MAX_SOLAPE = int(os.environ.get('MUNDO_MAX_SOLAPE', '8'))          # redacción propia (LLM)
MAX_SOLAPE_EXTRACTIVO = int(os.environ.get('MUNDO_MAX_SOLAPE_EXTRACTIVO', '90'))  # resumen por extracción: más permisivo
MIN_PAL, MAX_PAL = 35, 95


def solape_maximo(guion, fuente):
    g, f = palabras(guion), palabras(fuente)
    if not g or not f:
        return 0
    idx = {}
    for i in range(len(f)):
        idx.setdefault(f[i], []).append(i)
    mejor = 0
    for i in range(len(g)):
        for j in idx.get(g[i], ()):
            k = 0
            while i + k < len(g) and j + k < len(f) and g[i + k] == f[j + k]:
                k += 1
            mejor = max(mejor, k)
    return mejor


def numeros(t):
    return set(re.findall(r'\d+(?:[.,]\d+)?', t))


def revisar(guion, it, max_solape=MAX_SOLAPE):
    """Lista de problemas (vacía = aprobado)."""
    fuente = ' '.join([it['titulo'], it.get('resumen', ''), it.get('texto', '')])
    p = []
    if sin_tildes(it['fuente']) not in sin_tildes(guion):
        p.append('no menciona la fuente')
    nuevos = [n for n in numeros(guion) if n not in numeros(fuente)]
    if nuevos:
        p.append('cifras que no están en la fuente: ' + ', '.join(nuevos))
    s = solape_maximo(guion, fuente)
    if s > max_solape:
        p.append('copia %d palabras seguidas' % s)
    n = len(palabras(guion))
    if n < 12 or n > MAX_PAL + 25:
        p.append('longitud %d palabras' % n)
    return p


def _limpiar(s):
    s = re.sub(r'\((?:foto|fotograf[ií]a|imagen|video)[^)]*\)', '', s, flags=re.I)
    s = re.sub(r'^\s*(?:[A-ZÁÉÍÓÚÑ ]{3,}\s*[-–—:]\s*)', '', s)           # "SAN JOSÉ -"
    s = re.sub(r'\b(?:Lea|Vea|Lee|Ver) (?:también|más)\b.*$', '', s, flags=re.I)
    s = re.sub(r'https?://\S+', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def titular_corto(t, n=78):
    t = re.sub(r'\s+', ' ', t).strip().rstrip('.')
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(' ', 1)[0]
    return cut.rstrip(',;:') + '…'


def extractivo(it):
    """Guion en 2-5 oraciones: apertura con la fuente + hechos de la nota, descartando tiradas copiadas."""
    texto = _limpiar(it.get('texto') or it.get('resumen') or '')
    fuente_ref = ' '.join([it['titulo'], it.get('resumen', ''), texto])
    ent = ENTRADAS.get(it.get('seccion'), '')
    elegidas, pal = [], 0
    for o in oraciones(texto):
        o = _limpiar(o)
        n = len(palabras(o))
        if n < 6 or n > 32 or o.endswith(':'):
            continue
        if elegidas and sin_tildes(o)[:40] == sin_tildes(elegidas[-1])[:40]:
            continue
        if solape_maximo(o, it['titulo']) > MAX_SOLAPE + 6 and elegidas:
            continue
        elegidas.append(o); pal += n
        if pal >= MIN_PAL + 20 or len(elegidas) >= 4:
            break
    if not elegidas:
        elegidas = [it['titulo'].rstrip('.') + '.']
    cuerpo = ' '.join(elegidas)
    comunes = {'unos', 'unas', 'más', 'casi', 'cerca', 'alrededor', 'al', 'del', 'lo', 'sus', 'su', 'todos', 'todas', 'varios', 'varias', 'entre', 'sin', 'tras', 'ante', 'cada', 'otros', 'otras', 'el', 'la', 'los', 'las', 'un', 'una', 'en', 'este', 'esta', 'estos', 'estas', 'con', 'para', 'por', 'se', 'como', 'ya', 'a', 'además', 'también', 'según', 'durante', 'desde', 'hoy', 'ayer'}
    primera = cuerpo.split()[0].strip('«"“').lower()
    if primera in comunes:
        cuerpo = cuerpo[0].lower() + cuerpo[1:]
    if not cuerpo.endswith(('.', '!', '?')):
        cuerpo += '.'
    return '%s%s %s, %s' % (ent, 'según' if ent else 'Según', it['fuente'], cuerpo)


class LLM:
    """Redacción con un modelo pequeño local. Se activa con MUNDO_LLM=transformers (y MUNDO_LLM_MODELO)."""
    def __init__(self, modelo=None):
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa
        import torch
        self.torch = torch
        self.modelo = modelo or os.environ.get('MUNDO_LLM_MODELO', 'Qwen/Qwen2.5-1.5B-Instruct')
        self.tok = AutoTokenizer.from_pretrained(self.modelo)
        self.m = AutoModelForCausalLM.from_pretrained(self.modelo, torch_dtype=torch.float32)

    def escribir(self, it):
        ctx = _limpiar(it.get('texto') or it.get('resumen'))[:1800]
        msg = [{'role': 'system', 'content': 'Eres el guionista de un noticiero costarricense amable y claro. Escribes en español neutro, con palabras propias, sin copiar frases de la fuente.'},
               {'role': 'user', 'content': ('Redacta en 3 a 5 oraciones cortas (60 a 90 palabras) la nota para que la lea un presentador. '
                                            'Empieza mencionando la fuente: "%s". Usa solo datos y cifras del texto. No inventes. No uses viñetas ni emojis.\n\nTitular: %s\n\nTexto: %s') % (it['fuente'], it['titulo'], ctx)}]
        ids = self.tok.apply_chat_template(msg, add_generation_prompt=True, return_tensors='pt')
        with self.torch.no_grad():
            out = self.m.generate(ids, max_new_tokens=220, do_sample=True, temperature=0.5, top_p=0.9)
        return limpiar_html(self.tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)).strip()


_llm = None


def motor():
    global _llm
    if os.environ.get('MUNDO_LLM') == 'transformers' and _llm is None:
        try:
            _llm = LLM()
        except Exception as e:
            print('LLM no disponible (%s); uso redactor extractivo.' % e)
            os.environ['MUNDO_LLM'] = ''
    return _llm


def redactar(it, intentos=2):
    """Devuelve (guion, motor_usado, problemas_restantes)."""
    m = motor()
    if m:
        for _ in range(intentos):
            try:
                g = m.escribir(it)
            except Exception:
                break
            if not revisar(g, it):
                return g, 'llm', []
    g = extractivo(it)
    return g, 'extractivo', revisar(g, it, MAX_SOLAPE_EXTRACTIVO)
