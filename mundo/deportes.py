"""Marcadores y próximos partidos de fútbol para la barra inferior (ESPN, API pública sin clave).
Si una liga o el servicio falla, simplemente no aparece: la barra sigue con las demás secciones."""
import json
from datetime import datetime, timedelta, timezone

from .util import descargar

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
