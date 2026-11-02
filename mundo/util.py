"""Utilidades: red respetuosa (robots.txt), texto, números a letras en español."""
import html, os, re, time, unicodedata, urllib.request, urllib.robotparser, urllib.parse

UA = os.environ.get('MUNDO_UA', 'MundoNoticiasBot/1.0 (canal de noticias con IA; respeta robots.txt)')
_robots = {}


def permitido(url):
    p = urllib.parse.urlparse(url)
    base = '%s://%s' % (p.scheme, p.netloc)
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + '/robots.txt', headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                rp.parse(r.read().decode('utf-8', 'ignore').splitlines())
        except Exception:
            rp = None  # sin robots.txt accesible: se asume permitido
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def descargar(url, timeout=20, respetar_robots=True, cabeceras=None):
    """Devuelve bytes. Lanza excepción si falla o robots.txt lo prohíbe."""
    if respetar_robots and not permitido(url):
        raise PermissionError('robots.txt no permite ' + url)
    h = {'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'es'}
    h.update(cabeceras or {})
    ultimo = None
    for intento in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            ultimo = e
            time.sleep(1.5)
    raise ultimo


def decodificar(b):
    for enc in ('utf-8', 'latin-1'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode('utf-8', 'ignore')


def limpiar_html(s):
    s = re.sub(r'(?is)<(script|style).*?</\1>', ' ', s or '')
    s = re.sub(r'(?s)<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', html.unescape(s)).strip()


def sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def palabras(s):
    return re.findall(r'[a-z0-9ñ]+', sin_tildes(s))


def oraciones(texto):
    t = re.sub(r'\s+', ' ', texto).strip()
    partes = re.split(r'(?<=[.!?…])\s+(?=[A-ZÁÉÍÓÚÑ¿¡"“0-9])', t)
    return [p.strip() for p in partes if len(p.strip()) > 2]


# ---- números a letras (para que la voz lea bien cifras, años y porcentajes) ----
_U = ['cero', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve', 'diez', 'once', 'doce', 'trece',
      'catorce', 'quince', 'dieciséis', 'diecisiete', 'dieciocho', 'diecinueve', 'veinte', 'veintiuno', 'veintidós',
      'veintitrés', 'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve']
_D = ['', '', '', 'treinta', 'cuarenta', 'cincuenta', 'sesenta', 'setenta', 'ochenta', 'noventa']
_C = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos', 'quinientos', 'seiscientos', 'setecientos',
      'ochocientos', 'novecientos']


def _menor_mil(n):
    if n == 100:
        return 'cien'
    c, r = divmod(n, 100)
    out = [_C[c]] if c else []
    if r < 30:
        if r or not c:
            out.append(_U[r])
    else:
        d, u = divmod(r, 10)
        out.append(_D[d] + (' y ' + _U[u] if u else ''))
    return ' '.join(out)


def numero_a_letras(n, apocopar=False):
    if n < 0:
        return 'menos ' + numero_a_letras(-n)
    if n < 1000:
        t = _menor_mil(n)
    elif n < 1_000_000:
        m, r = divmod(n, 1000)
        t = ('mil' if m == 1 else numero_a_letras(m, True) + ' mil') + (' ' + _menor_mil(r) if r else '')
    elif n < 1_000_000_000_000:
        m, r = divmod(n, 1_000_000)
        t = ('un millón' if m == 1 else numero_a_letras(m, True) + ' millones') + (' ' + numero_a_letras(r) if r else '')
    else:
        return str(n)
    if apocopar:
        t = re.sub(r'\buno$', 'un', t)
        t = re.sub(r'\bveintiuno$', 'veintiún', t)
    return t


def normalizar_tts(texto):
    """Prepara el guion para la voz: cifras, porcentajes, unidades, decimales, símbolos."""
    t = texto
    t = re.sub(r'(\d+)\s*°\s*C\b', lambda m: m.group(1) + ' grados', t)
    t = t.replace('°', ' grados ')
    t = re.sub(r'¢\s*([\d.,]+)', lambda m: m.group(1) + ' colones', t)
    t = re.sub(r'\$\s*([\d.,]+)', lambda m: m.group(1) + ' dólares', t)
    t = re.sub(r'(\d)\s*%', r'\1 por ciento', t)
    t = re.sub(r'\bkm/h\b', 'kilómetros por hora', t)
    t = re.sub(r'\bmm\b', 'milímetros', t)
    t = re.sub(r'\bkm\b', 'kilómetros', t)

    def dec(m):
        ent, fr = m.group(1), m.group(2)
        return numero_a_letras(int(ent.replace('.', '').replace(' ', ''))) + ' coma ' + ' '.join(numero_a_letras(int(c)) for c in fr) if len(fr) <= 2 else m.group(0)
    t = re.sub(r'\b(\d{1,3}(?:[.\s]\d{3})*|\d+),(\d{1,2})\b(?!\d)', dec, t)

    def ent(m):
        s = m.group(0).replace('.', '').replace('\u00a0', '')
        s = re.sub(r'\s', '', s)
        if not s.isdigit():
            return m.group(0)
        n = int(s)
        if 1900 <= n <= 2100 and len(s) == 4 and '.' not in m.group(0):
            return numero_a_letras(n)
        return numero_a_letras(n, apocopar=True)
    t = re.sub(r'\d{1,3}(?:\.\d{3})+|\d+', ent, t)
    return re.sub(r'\s+', ' ', t).strip()
