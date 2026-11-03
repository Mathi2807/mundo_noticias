"""Marcadores y próximos partidos de fútbol para la barra inferior (ESPN, API pública sin clave).
Si una liga o el servicio falla, simplemente no aparece: la barra sigue con las demás secciones."""
import json
from datetime import datetime, timedelta, timezone

from .util import descargar, numero_a_letras

URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s'
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


def _hora(dt_cr):
    h = dt_cr.hour % 12 or 12
    return '%d:%02d %s' % (h, dt_cr.minute, 'am' if dt_cr.hour < 12 else 'pm')


def _cuando(dt_cr, hoy_cr):
    d = (dt_cr.date() - hoy_cr.date()).days
    if d == 0:
        return 'Hoy ' + _hora(dt_cr)
    if d == 1:
        return 'Mañana ' + _hora(dt_cr)
    return '%s %d %s' % (DIAS[dt_cr.weekday()].capitalize()[:3], dt_cr.day, _hora(dt_cr))


def _hora_hablada(dt):
    h12 = dt.hour % 12 or 12
    parte = 'de la madrugada' if dt.hour < 6 else ('de la mañana' if dt.hour < 12 else ('de la tarde' if dt.hour < 19 else 'de la noche'))
    if dt.hour == 12:
        parte = 'del mediodía'
    hh = ('la una' if h12 == 1 else 'las ' + numero_a_letras(h12))
    mm = '' if dt.minute == 0 else (' y media' if dt.minute == 30 else ' y ' + numero_a_letras(dt.minute))
    return '%s%s %s' % (hh, mm, parte)


def _cuando_hablado(dt_cr, hoy_cr):
    d = (dt_cr.date() - hoy_cr.date()).days
    dia = 'hoy' if d == 0 else ('mañana' if d == 1 else DIAS[dt_cr.weekday()])
    return '%s a %s' % (dia, _hora_hablada(dt_cr))


def hablado(datos, liga, ahora_utc):
    """Frases para decir en voz alta: (resultados finales, próximos partidos), cada uno [(fecha, frase)]."""
    hoy_cr = ahora_utc + timedelta(hours=-6)
    res, prox = [], []
    for ev in datos.get('events', []):
        try:
            comp = ev['competitions'][0]
            eq = {c['homeAway']: c for c in comp['competitors']}
            loc, vis = eq['home'], eq['away']
            nl = loc['team'].get('shortDisplayName') or loc['team']['displayName']
            nv = vis['team'].get('shortDisplayName') or vis['team']['displayName']
            estado = ev['status']['type']['state']
            fecha = datetime.fromisoformat(ev['date'].replace('Z', '+00:00')) + timedelta(hours=-6)
            if estado == 'post':
                gl, gv = int(float(loc.get('score'))), int(float(vis.get('score')))
                if gl == gv:
                    f = '%s y %s empataron %s a %s' % (nl, nv, numero_a_letras(gl), numero_a_letras(gv))
                elif gl > gv:
                    f = '%s le ganó %s a %s a %s' % (nl, numero_a_letras(gl), numero_a_letras(gv), nv)
                else:
                    f = '%s venció %s a %s a %s' % (nv, numero_a_letras(gv), numero_a_letras(gl), nl)
                res.append((fecha, f))
            elif estado == 'pre' and fecha > hoy_cr:
                prox.append((fecha, '%s contra %s, %s' % (nl, nv, _cuando_hablado(fecha, hoy_cr))))
        except Exception:
            continue
    return res, prox


def guion_deportivo(ligas, ahora_utc=None, descargar_fn=descargar, max_res=5, max_prox=5):
    """Ítem de noticiero 'Deportes' hablado por Josué con marcadores finales y próximos partidos, o None."""
    ahora = ahora_utc or datetime.now(timezone.utc)
    hoy = ahora + timedelta(hours=-6)
    fechas = [(hoy + timedelta(days=d)).strftime('%Y%m%d') for d in (-1, 0, 1, 2)]
    partes_r, partes_p = [], []
    for nombre, cod in ligas:
        rs, ps = [], []
        for f in fechas:
            try:
                datos = json.loads(descargar_fn(URL % (cod, f), respetar_robots=False, timeout=15))
                r, p = hablado(datos, nombre, ahora)
                rs += r; ps += p
            except Exception:
                continue
        rs = sorted(set(rs), key=lambda x: x[0], reverse=True)[:2]
        ps = sorted(set(ps), key=lambda x: x[0])[:2]
        if rs:
            partes_r.append('En %s: %s.' % (nombre, '; '.join(x for _, x in rs)))
        if ps:
            partes_p.append('En %s: %s.' % (nombre, '; '.join(x for _, x in ps)))
    if not partes_r and not partes_p:
        return None
    g = 'Es hora de los deportes. '
    if partes_r:
        g += 'Resultados recientes. ' + ' '.join(partes_r[:max_res]) + ' '
    if partes_p:
        g += 'Y los próximos partidos. ' + ' '.join(partes_p[:max_prox]) + ' '
    g += 'Datos de ESPN.'
    return {'id': 'deportes_hoy', 'seccion': 'Deportes', 'set': 'deportes', 'titular': 'Marcadores y próximos partidos',
            'sub': 'Datos: ESPN · horarios de Costa Rica', 'fuente': 'ESPN', 'url': 'https://www.espn.com/futbol/', 'guion': g, 'tipo': 'interes'}


def interpretar(datos, liga, ahora_utc):
    """Convierte la respuesta de ESPN en dos listas: marcadores (final o en juego) y próximos."""
    hoy_cr = ahora_utc + timedelta(hours=-6)
    marcadores, proximos = [], []
    for ev in datos.get('events', []):
        try:
            comp = ev['competitions'][0]
            eq = {c['homeAway']: c for c in comp['competitors']}
            loc, vis = eq['home'], eq['away']
            nl = loc['team'].get('shortDisplayName') or loc['team']['displayName']
            nv = vis['team'].get('shortDisplayName') or vis['team']['displayName']
            estado = ev['status']['type']['state']
            fecha = datetime.fromisoformat(ev['date'].replace('Z', '+00:00')) + timedelta(hours=-6)
            if estado == 'post':
                marcadores.append((fecha, '%s: %s %s-%s %s (final)' % (liga, nl, loc.get('score', '?'), vis.get('score', '?'), nv)))
            elif estado == 'in':
                minuto = ev['status'].get('displayClock', '')
                marcadores.append((fecha, '%s: %s %s-%s %s (en juego %s)' % (liga, nl, loc.get('score', '?'), vis.get('score', '?'), nv, minuto)))
            elif estado == 'pre':
                proximos.append((fecha, '%s: %s vs %s · %s' % (liga, nl, nv, _cuando(fecha, hoy_cr))))
        except Exception:
            continue
    return marcadores, proximos


def obtener(ligas, ahora_utc=None, descargar_fn=descargar, maximo=16):
    """ligas: [[nombre, código_espn], ...]. Devuelve lista de textos para la barra (marcadores primero, luego próximos)."""
    ahora = ahora_utc or datetime.now(timezone.utc)
    hoy = ahora + timedelta(hours=-6)
    fechas = [(hoy + timedelta(days=d)).strftime('%Y%m%d') for d in (-1, 0, 1)]
    todos_m, todos_p, orden = [], [], {l[1]: i for i, l in enumerate(ligas)}
    for nombre, cod in ligas:
        for f in fechas:
            try:
                datos = json.loads(descargar_fn(URL % (cod, f), respetar_robots=False, timeout=15))
                m, p = interpretar(datos, nombre, ahora)
                todos_m += [(orden[cod], t, x) for t, x in m]
                todos_p += [(orden[cod], t, x) for t, x in p]
            except Exception:
                continue
    # las ligas de arriba en la lista (Costa Rica primero) van antes; dentro de cada liga, lo más reciente / más próximo
    todos_m.sort(key=lambda z: (z[0], -z[1].timestamp()))
    todos_p.sort(key=lambda z: (z[0], z[1].timestamp()))
    vistos, out = set(), []
    for _, _, x in todos_m[: maximo // 2 + 2] + todos_p[: maximo // 2 + 2]:
        if x not in vistos:
            vistos.add(x); out.append(x)
    return out[:maximo]
