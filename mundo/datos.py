"""Datos en tiempo real sin texto de terceros: clima (MET Norway) y tipo de cambio (Hacienda)."""
import json
from datetime import datetime, timezone, timedelta
from .util import descargar, numero_a_letras

SIMBOLOS = {'clearsky': 'cielo despejado', 'fair': 'mayormente despejado', 'partlycloudy': 'parcialmente nublado',
            'cloudy': 'nublado', 'fog': 'con neblina', 'lightrain': 'con lluvias ligeras', 'rain': 'con lluvias',
            'heavyrain': 'con lluvias fuertes', 'lightrainshowers': 'con aguaceros ligeros', 'rainshowers': 'con aguaceros',
            'heavyrainshowers': 'con aguaceros fuertes', 'rainandthunder': 'con lluvia y tormenta eléctrica',
            'heavyrainandthunder': 'con lluvia fuerte y tormenta eléctrica', 'lightrainandthunder': 'con lluvia ligera y tormenta eléctrica',
            'rainshowersandthunder': 'con aguaceros y tormenta eléctrica', 'heavyrainshowersandthunder': 'con aguaceros fuertes y tormenta eléctrica',
            'lightrainshowersandthunder': 'con aguaceros ligeros y tormenta eléctrica'}


def _simbolo(code):
    base = (code or '').split('_')[0]
    return SIMBOLOS.get(base, 'variable')


def clima(ciudades, descargar_fn=descargar):
    """Devuelve un item de noticiero 'Clima' o None."""
    frases, ok, linea = [], 0, []
    ahora = datetime.now(timezone.utc)
    for nombre, lat, lon in ciudades:
        try:
            url = 'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=%.2f&lon=%.2f' % (lat, lon)
            d = json.loads(descargar_fn(url, respetar_robots=False))
            ts = [t for t in d['properties']['timeseries'] if ahora <= datetime.fromisoformat(t['time'].replace('Z', '+00:00')) <= ahora + timedelta(hours=12)]
            if not ts:
                continue
            temps = [t['data']['instant']['details']['air_temperature'] for t in ts]
            lluvia = sum(t['data'].get('next_1_hours', {}).get('details', {}).get('precipitation_amount', 0) for t in ts)
            sim = (ts[min(5, len(ts) - 1)]['data'].get('next_6_hours') or ts[0]['data'].get('next_1_hours') or {}).get('summary', {}).get('symbol_code', '')
            tmin, tmax = round(min(temps)), round(max(temps))
            llu = 'sin lluvia importante' if lluvia < 0.5 else ('con lluvia acumulada de %s milímetros' % numero_a_letras(round(lluvia)) if round(lluvia) > 0 else 'con lluvias ligeras')
            frases.append('En %s, entre %s y %s grados, %s y %s.' % (nombre, numero_a_letras(tmin), numero_a_letras(tmax), _simbolo(sim).replace('con ', 'con ') if sim else 'variable', llu))
            linea.append('%s %d°–%d°' % (nombre, tmin, tmax)); ok += 1
        except Exception:
            continue
    if not ok:
        return None
    guion = 'Así estará el tiempo en las próximas doce horas, según los datos de MET Norway. ' + ' '.join(frases)
    return {'id': 'clima', 'seccion': 'Clima', 'set': 'noticias', 'titular': 'El tiempo en las próximas horas',
            'sub': 'Datos: MET Norway (CC BY 4.0) · San José, Liberia, Limón y Puntarenas', 'fuente': 'MET Norway',
            'url': 'https://api.met.no/', 'guion': guion, 'tipo': 'interes',
            'ticker': [('CLIMA', ' · '.join(linea))]}


def tipo_cambio(url, descargar_fn=descargar):
    try:
        d = json.loads(descargar_fn(url, respetar_robots=False))
        compra = float(d['compra']['valor']); venta = float(d['venta']['valor'])
    except Exception:
        return None
    c, v = round(compra, 2), round(venta, 2)
    def letras(x):
        e, f = divmod(int(round(x * 100)), 100)
        return numero_a_letras(e) + (' con ' + numero_a_letras(f) if f else '')
    guion = ('Para tu bolsillo: según el Ministerio de Hacienda, el tipo de cambio de referencia del dólar está en %s colones para la compra y %s colones para la venta.') % (letras(c), letras(v))
    return {'id': 'tipo_cambio', 'seccion': 'Tu bolsillo', 'set': 'noticias', 'titular': 'Dólar: compra %.2f · venta %.2f' % (c, v),
            'sub': 'Fuente: Ministerio de Hacienda · tipo de cambio de referencia', 'fuente': 'Ministerio de Hacienda',
            'url': url, 'guion': guion, 'tipo': 'interes',
            'ticker': [('TU BOLSILLO', 'Dólar: compra ₡%.2f · venta ₡%.2f (Hacienda)' % (c, v))]}
