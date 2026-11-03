#!/usr/bin/env python3
"""Mundo Noticias: produce un bucle de programación (video + créditos + lista) de forma autónoma.

Uso:  python3 main.py producir [--franja auto|calma|despierta|marcha|positivo] [--salida salida] [--offline]
"""
import argparse, json, math, os, random, sys, time, wave
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from mundo import datos, deportes, extras as ext, filtro, ingesta, musica as mus, programa as prog, util
from mundo.ticker import ETIQUETA_DE

ANTICIPO_MIN = 100   # minutos que pasan, en promedio, entre producir un bucle y que salga al aire


def descargar_offline(carpeta, config):
    mapa = {}
    for f in config['fuentes']:
        arch = {'onu': 'onu.xml', 'unafut': 'unafut.xml', 'bbc': 'bbc.xml'}
        for k, v in arch.items():
            if f['id'].startswith(k) or (k == 'bbc' and f['id'] == 'bbc_mundo'):
                mapa[f['url']] = v
    mapa['api.met.no'] = 'met.json'; mapa['hacienda'] = 'hacienda.json'

    def dl(url, **kw):
        for k, v in mapa.items():
            if k in url:
                return open(os.path.join(carpeta, v), 'rb').read()
        raise IOError('sin fixture para ' + url)
    return dl


def dur_wav(ruta):
    with wave.open(ruta) as w:
        return w.getnframes() / w.getframerate()


def producir(a):
    t0 = time.time()
    cfg = json.load(open(os.path.join(RAIZ, 'config', 'fuentes.json'), encoding='utf-8'))
    parrilla = prog.cargar_parrilla()
    if a.interludio is not None:
        parrilla['musica_interludio_minutos'] = a.interludio
    ahora = datetime.now(timezone.utc)
    # la franja, el saludo y la fecha se deciden para la HORA EN QUE SALDRÁ AL AIRE, no para la de producción
    destino = ahora + timedelta(minutes=a.anticipo)
    franja, min_restantes, loc = prog.franja_actual(destino, parrilla)
    if a.franja != 'auto':
        franja = next(f for f in parrilla['franjas'] if f['id'] == a.franja)
        min_restantes = 120
    objetivo = a.minutos or max(30, min(parrilla['bucle_minutos'][1], min_restantes))
    rng = random.Random(int(ahora.timestamp()) // 600)
    salida = os.path.abspath(a.salida); os.makedirs(salida, exist_ok=True)
    estado_dir = os.path.abspath(a.estado); os.makedirs(estado_dir, exist_ok=True)
    print('Franja: %s · bucle objetivo: %.0f min' % (franja['nombre'], objetivo), flush=True)

    dl = util.descargar
    if a.offline:
        sys.path.insert(0, os.path.join(RAIZ, 'tests', 'fixtures'))
        import generar
        fx = os.path.join(estado_dir, 'fixtures'); generar.generar(fx)
        dl = descargar_offline(fx, cfg)

    notas, extras, descartadas, ticker_items = [], {'inicio': [], 'fin': []}, [], []
    sel = filtro.Seleccion(os.path.join(estado_dir, 'estado.json'))
    if franja['tipo'] == 'noticias':
        ing = ingesta.Ingesta(cfg, dl, pausa=0 if a.offline else 0.8)
        crudas = ing.correr()
        json.dump(ing.salud, open(os.path.join(estado_dir, 'salud_fuentes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('Fuentes: %d respondieron, %d fallaron; %d notas crudas' % (
            sum(1 for v in ing.salud.values() if v['ok']), sum(1 for v in ing.salud.values() if not v['ok']), len(crudas)), flush=True)
        cand, descartadas = sel.candidatas(crudas, ahora)
        n_pedidas = max(3, int(math.ceil(objetivo / 6.0)))
        elegidas = sel.elegir(cand, n_pedidas, semilla=int(ahora.timestamp()) // 600, ahora=ahora)
        minimo = max(3, int(objetivo / 10))
        if len(elegidas) < minimo:       # faltan notas nuevas: se repasan SOLO las de hoy, las menos recientes primero
            rep = sel.repaso(cand, minimo - len(elegidas), destino, excluir={c['id'] for c in elegidas})
            for c in rep:
                c['repaso'] = True
            elegidas += rep
        print('Candidatas: %d · descartadas: %d · elegidas: %d (%d de repaso)' % (
            len(cand), len(descartadas), len(elegidas), sum(1 for c in elegidas if c.get('repaso'))), flush=True)
        for c in elegidas:
            it = prog.item_noticia(c)
            if it:
                notas.append(it)
            else:
                descartadas.append((c, 'guion no superó las revisiones'))
        c = datos.clima(cfg['datos']['clima']['ciudades'], dl)
        if c: extras['inicio'].append(c)
        tc = datos.tipo_cambio(cfg['datos']['tipo_cambio']['url'], dl)
        if tc: extras['inicio'].append(tc)
        n_reales = len(notas)
        # deportes dichos en voz: notas deportivas garantizadas (si las hay) y resumen de marcadores/próximos de ESPN
        if not any(n['seccion'] == 'Deportes' for n in notas):
            for c_ in [c_ for c_ in cand if c_['seccion'] == 'deportes' and c_['id'] not in {n['id'] for n in notas}][:2]:
                it = prog.item_noticia(c_)
                if it:
                    notas.insert(min(len(notas), max(2, len(notas) // 2)), it)
        try:
            dep_item = deportes.guion_deportivo(cfg['datos']['deportes']['ligas'], destino, dl)
        except Exception:
            dep_item = None
        k_h = int(destino.timestamp() // 3600)
        mezcla = []
        e0 = ext.efemeride(loc)
        if e0: extras['inicio'].append(e0)
        if dep_item: mezcla.append((0.45, dep_item))
        mezcla += [(0.30, ext.sabias_que(k_h)), (0.65, ext.promo(k_h)), (0.80, ext.sabias_que(k_h + 7))]
        for pos, it in sorted(mezcla, key=lambda x: -x[0]):
            notas.insert(min(len(notas), max(2, int(len(notas) * pos))), it)
        # barra inferior: titulares de todas las candidatas (no solo las leídas) + clima, dólar y fútbol
        usados = {n['id'] for n in notas}
        for n in [n for n in notas if not n.get('extra') and n['id'] != 'deportes_hoy']:
            ticker_items.append((ETIQUETA_DE.get(n['seccion'], 'ACONTECIMIENTOS'), prog.titular_corto(n['titular'], 95)))
        for c_ in cand:
            if c_['id'] not in usados and len(ticker_items) < 40 and c_['seccion'] != 'deportes':
                ticker_items.append((ETIQUETA_DE.get(prog.ETIQUETAS.get(c_['seccion'], ''), 'ACONTECIMIENTOS'), prog.titular_corto(c_['titulo'], 95)))
        for e in extras['inicio']:
            ticker_items += e.get('ticker', [])
        ticker_items += ext.linea_barra()
        try:
            lig = cfg['datos']['deportes']['ligas']
            dep = deportes.obtener(lig, ahora, dl)
            ticker_items += [('DEPORTES', x) for x in dep]
            print('Deportes en la barra: %d' % len(dep), flush=True)
        except Exception as ex:
            print('Deportes no disponibles:', ex, flush=True)
        if not n_reales and not [e for e in extras['inicio'] if not e.get('extra')]:
            print('Sin noticias válidas: este bucle será de música.'); franja = dict(franja, tipo='musica')

    try:
        sal = json.load(open(os.path.join(estado_dir, 'salud_fuentes.json'), encoding='utf-8')) if franja['tipo'] == 'noticias' else {}
        md = ['# Estado de Mundo Noticias', '', 'Último bucle preparado: %s (UTC)' % ahora.strftime('%Y-%m-%d %H:%M'),
              'Sale al aire hacia las %s hora de Costa Rica · franja: %s · duración objetivo: %.0f min' % ((destino + timedelta(hours=-6)).strftime('%H:%M'), franja['nombre'], objetivo),
              'Notas leídas: %d (de repaso: %d)' % (len([n for n in notas if not n.get('extra')]), len([n for n in notas if n.get('repaso')])), '',
              '## Fuentes', ''] + ['- %s %s' % ('✅' if v.get('ok') else '❌', k) for k, v in sorted(sal.items())]
        open(os.path.join(estado_dir, 'ESTADO.md'), 'w', encoding='utf-8').write('\n'.join(md) + '\n')
    except Exception:
        pass
    sel.marcar([n['id'] for n in notas if not n.get('extra') and n['id'] != 'deportes_hoy'], destino); sel.guardar()
    if a.tras_seleccion:
        os.system(a.tras_seleccion)     # sube el estado ya, para que la corrida siguiente no repita estas notas
    cant = a.canciones
    pistas = mus.pistas(franja['humor'], os.path.join(estado_dir, 'musica'), cantidad=cant, semilla_base=(int(ahora.timestamp()) // 600) * 37, minutos=a.pista_min)
    for p in pistas:
        p['dur'] = dur_wav(p['ruta'])
    segs = prog.armar_bucle(franja, loc, notas, extras, pistas, objetivo, parrilla, rng)
    prog.preparar_voces(segs, os.path.join(salida, 'voces'))
    total = sum(s['dur'] for s in segs)
    print('Segmentos: %d · duración %.1f min' % (len(segs), total / 60), flush=True)
    audio = os.path.join(salida, 'audio_mezcla.wav')
    prog.escribir_audio(segs, pistas, audio)
    video = os.path.join(salida, 'bucle.mp4')
    prog.escribir_video(segs, audio, video, franja['nombre'], loc, res=a.resolucion, ticker_items=ticker_items)
    open(os.path.join(salida, 'creditos.txt'), 'w', encoding='utf-8').write(prog.creditos(segs, franja, loc, None))
    lista, t_ac = [], 0.0
    for s in segs:
        it = s.get('item') or {}
        d_real = int(round(s['dur'] * prog.FPS)) / prog.FPS          # lo que realmente dura en el video
        lista.append({'tipo': s['tipo'], 'dur_s': round(s['dur'], 1), 'inicio_s': round(t_ac, 3), 'dur_real': round(d_real, 3),
                      'id': it.get('id') or s['pista']['titulo'], 'seccion': it.get('seccion', 'Música'), 'titular': it.get('titular', ''),
                      'sub': it.get('sub', ''), 'extra': bool(it.get('extra')), 'repaso': bool(it.get('repaso')), 'set': it.get('set', ''),
                      'guion': it.get('guion', ''), 'fuente': it.get('fuente', ''), 'url': it.get('url', '')})
        t_ac += d_real
    json.dump({'franja': franja['nombre'], 'franja_id': franja['id'], 'calma': franja['tipo'] == 'musica', 'generado_utc': ahora.isoformat(),
               'destino_utc': destino.isoformat(), 'fin_utc': (destino + timedelta(seconds=total)).isoformat(), 'destino_dia_cr': (destino + timedelta(minutes=objetivo / 2, hours=-6)).strftime('%Y-%m-%d'), 'segmentos': lista,
               'descartadas': [{'titulo': i['titulo'], 'fuente': i['fuente'], 'motivo': m} for i, m in descartadas[:60]]},
              open(os.path.join(salida, 'lista.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.remove(audio) if a.limpiar else None
    print('Listo: %s (%.1f min de video, %.0f s de proceso)' % (video, total / 60, time.time() - t0), flush=True)


def clips(a):
    from mundo import clips as cl
    n = cl.generar(a.video, a.lista, a.salida, ext.cargar_redes(), maximo=a.maximo)
    print('Clips generados: %d' % n)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('producir')
    p.add_argument('--franja', default='auto')
    p.add_argument('--salida', default='salida')
    p.add_argument('--estado', default='estado')
    p.add_argument('--minutos', type=float, default=None, help='duración objetivo del bucle (por defecto 90, limitada por la franja)')
    p.add_argument('--interludio', type=float, default=None, help='minutos de música entre bloques')
    p.add_argument('--anticipo', type=float, default=ANTICIPO_MIN, help='minutos hasta que el bucle salga al aire')
    p.add_argument('--tras-seleccion', default=None, help='comando de shell a ejecutar al elegir las notas (guardar estado)')
    p.add_argument('--canciones', type=int, default=14)
    p.add_argument('--pista-min', type=float, default=4.5)
    p.add_argument('--offline', action='store_true', help='usa datos de prueba en vez de internet')
    p.add_argument('--resolucion', default='1280x720')
    p.add_argument('--limpiar', action='store_true')
    c = sub.add_parser('clips')
    c.add_argument('--video', default='salida/bucle.mp4'); c.add_argument('--lista', default='salida/lista.json')
    c.add_argument('--salida', default='clips'); c.add_argument('--maximo', type=int, default=5)
    a = ap.parse_args()
    clips(a) if a.cmd == 'clips' else producir(a)


if __name__ == '__main__':
    main()
