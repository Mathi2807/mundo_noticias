"""Ingesta: RSS/Atom y páginas HTML (OpenGraph/párrafos). Respeta robots.txt. Cada fuente se aísla: si una falla, las demás siguen."""
import hashlib, json, os, re, time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .util import descargar, decodificar, limpiar_html

NS_ATOM = '{http://www.w3.org/2005/Atom}'


def _fecha(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _hijo(el, *nombres):
    for n in nombres:
        x = el.find(n)
        if x is not None and (x.text or len(x)):
            return x
    return None


def parsear_feed(xml_bytes, fuente):
    """RSS 2.0, RSS 1.0 (RDF) y Atom -> lista de dicts."""
    texto = decodificar(xml_bytes)
    texto = re.sub(r'^\s*<\?xml[^>]*\?>', '', texto)
    raiz = ET.fromstring(texto)
    items = []
    entradas = [e for e in raiz.iter() if e.tag.split('}')[-1] in ('item', 'entry')]
    for e in entradas:
        def g(*tags):
            for t in tags:
                for c in e:
                    if c.tag.split('}')[-1] == t and (c.text or '').strip():
                        return c.text.strip()
            return ''
        titulo = limpiar_html(g('title'))
        enlace = g('link')
        if not enlace:
            for c in e:
                if c.tag.split('}')[-1] == 'link' and c.get('href'):
                    enlace = c.get('href'); break
        resumen = limpiar_html(g('description', 'summary'))
        cuerpo = limpiar_html(g('encoded', 'content'))
        fecha = _fecha(g('pubDate', 'published', 'updated', 'date'))
        if titulo and enlace:
            items.append({'titulo': titulo, 'url': enlace.strip(), 'resumen': resumen, 'texto': cuerpo or resumen,
                          'fecha': fecha.isoformat() if fecha else None})
    return items


class _Pagina(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.enlaces, self.parrafos, self.titulo = {}, [], [], ''
        self._p = None; self._t = False; self._a = None; self._buf = ''

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == 'meta':
            k = (a.get('property') or a.get('name') or '').lower()
            if k and a.get('content'):
                self.meta.setdefault(k, a['content'])
        elif tag == 'title':
            self._t = True
        elif tag == 'p':
            self._p = ''
        elif tag == 'a' and a.get('href'):
            self._a = [a['href'], '']

    def handle_endtag(self, tag):
        if tag == 'title':
            self._t = False
        elif tag == 'p' and self._p is not None:
            t = re.sub(r'\s+', ' ', self._p).strip()
            if len(t) > 60:
                self.parrafos.append(t)
            self._p = None
        elif tag == 'a' and self._a:
            self.enlaces.append((self._a[0], re.sub(r'\s+', ' ', self._a[1]).strip())); self._a = None

    def handle_data(self, d):
        if self._t:
            self.titulo += d
        if self._p is not None:
            self._p += d
        if self._a:
            self._a[1] += d


def parsear_articulo(html_bytes, url):
    p = _Pagina()
    p.feed(decodificar(html_bytes))
    m = p.meta
    titulo = m.get('og:title') or p.titulo
    resumen = m.get('og:description') or m.get('description') or ''
    cuerpo = ' '.join(p.parrafos[:12])
    fecha = _fecha(m.get('article:published_time') or m.get('date') or m.get('og:updated_time'))
    return {'titulo': limpiar_html(titulo), 'url': url, 'resumen': limpiar_html(resumen),
            'texto': limpiar_html(cuerpo) or limpiar_html(resumen), 'fecha': fecha.isoformat() if fecha else None}


def enlaces_de_listado(html_bytes, base, patron, maximo=8):
    p = _Pagina()
    p.feed(decodificar(html_bytes))
    rx = re.compile(patron)
    vistos, out = set(), []
    for href, txt in p.enlaces:
        u = urljoin(base, href).split('#')[0]
        if urlparse(u).netloc.replace('www.', '') != urlparse(base).netloc.replace('www.', ''):
            continue
        if rx.search(urlparse(u).path) and u not in vistos and u.rstrip('/') != base.rstrip('/'):
            vistos.add(u); out.append(u)
    return out[:maximo]


def _id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]


class Ingesta:
    def __init__(self, config, descargar_fn=descargar, max_por_fuente=8, pausa=0.8):
        self.fuentes = [f for f in config['fuentes'] if f.get('activa', True)]
        self.dl = descargar_fn
        self.max = max_por_fuente
        self.pausa = pausa
        self.salud = {}

    def _una(self, f):
        if f['tipo'] in ('rss', 'atom'):
            items = parsear_feed(self.dl(f['url']), f)[: self.max]
        else:
            lst = self.dl(f['url'])
            urls = enlaces_de_listado(lst, f['url'], f['patron_enlace'], self.max)
            items = []
            for u in urls:
                try:
                    items.append(parsear_articulo(self.dl(u), u))
                except Exception:
                    continue
                time.sleep(self.pausa)
        # artículos sin texto suficiente: intenta traer la página (OpenGraph + párrafos)
        for it in items:
            if len(it['texto']) < 200 and f['tipo'] in ('rss', 'atom'):
                try:
                    a = parsear_articulo(self.dl(it['url']), it['url'])
                    if len(a['texto']) > len(it['texto']):
                        it['texto'] = a['texto']
                    it['fecha'] = it['fecha'] or a['fecha']
                    time.sleep(self.pausa)
                except Exception:
                    pass
        for it in items:
            it.update({'id': _id(it['url']), 'fuente_id': f['id'], 'fuente': f['nombre'], 'hint': f.get('hint', ''),
                       'pais': f.get('pais', '')})
        return items

    def correr(self):
        todo = []
        for f in self.fuentes:
            t0 = time.time()
            try:
                items = self._una(f)
                self.salud[f['id']] = {'ok': True, 'items': len(items), 'seg': round(time.time() - t0, 1)}
                todo += items
            except Exception as e:
                self.salud[f['id']] = {'ok': False, 'error': (type(e).__name__ + ': ' + str(e))[:160]}
        return todo
