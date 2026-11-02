#!/usr/bin/env python3
"""Mundo Noticias: produce un bucle de programación (video + créditos + lista) de forma autónoma.

Uso:  python3 main.py producir [--franja auto|calma|despierta|marcha|positivo] [--salida salida] [--offline]
"""
import argparse, json, math, os, random, sys, time, wave
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from mundo import datos, filtro, ingesta, musica as mus, programa as prog, util


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
    franja, min_restantes, loc = prog.franja_actual(ahora, parrilla)
    if a.franja != 'auto':
        franja = next(f for f in parrilla['franjas'] if f['id'] == a.franja)
        min_restantes = 120
    objetivo = a.minutos or min(random.Random(int(ahora.timestamp()) // 3600).randint(*parrilla['bucle_minutos']), min_restantes)
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

    notas, extras, descartadas = [], {'inicio': [], 'fin': []}, []
    sel = filtro.Seleccion(os.path.join(estado_dir, 'estado.json'))
    if franja['tipo'] == 'noticias':
        ing = ingesta.Ingesta(cfg, dl, pausa=0 if a.offline else 0.8)
        crudas = ing.correr()
        json.dump(ing.salud, open(os.path.join(estado_dir, 'salud_fuentes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('Fuentes: %d respondieron, %d fallaron; %d notas crudas' % (
            sum(1 for v in ing.salud.values() if v['ok']), sum(1 for v in ing.salud.values() if not v['ok']), len(crudas)), flush=True)
        cand, descartadas = sel.candidatas(crudas, ahora)
        n_pedidas = max(3, int(math.ceil(objetivo / 2.6)))
        elegidas = sel.elegir(cand, n_pedidas, semilla=int(ahora.timestamp()) // 600, ahora=ahora)
        print('Candidatas: %d · descartadas: %d · elegidas: %d' % (len(cand), len(descartadas), len(elegidas)), flush=True)
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
        if not notas and not extras['inicio']:
            print('Sin noticias válidas: este bucle será de música.'); franja = dict(franja, tipo='musica')

    cant = 3
    pistas = mus.pistas(franja['humor'], os.path.join(estado_dir, 'musica'), cantidad=cant, semilla_base=int(ahora.timestamp()) // 86400 * 3, minutos=a.pista_min)
    for p in pistas:
        p['dur'] = dur_wav(p['ruta'])
    segs = prog.armar_bucle(franja, loc, notas, extras, pistas, objetivo, parrilla, rng)
    prog.preparar_voces(segs, os.path.join(salida, 'voces'))
    total = sum(s['dur'] for s in segs)
    print('Segmentos: %d · duración %.1f min' % (len(segs), total / 60), flush=True)
    audio = os.path.join(salida, 'audio_mezcla.wav')
    prog.escribir_audio(segs, pistas, audio)
    video = os.path.join(salida, 'bucle.mp4')
    prog.escribir_video(segs, audio, video, franja['nombre'], loc, res=a.resolucion)
    open(os.path.join(salida, 'creditos.txt'), 'w', encoding='utf-8').write(prog.creditos(segs, franja, loc, None))
    lista = [{'tipo': s['tipo'], 'dur_s': round(s['dur'], 1), 'id': (s.get('item') or {}).get('id') or s['pista']['titulo'],
              'seccion': (s.get('item') or {}).get('seccion', 'Música'), 'guion': (s.get('item') or {}).get('guion', ''),
              'fuente': (s.get('item') or {}).get('fuente', ''), 'url': (s.get('item') or {}).get('url', '')} for s in segs]
    json.dump({'franja': franja['nombre'], 'generado_utc': ahora.isoformat(), 'segmentos': lista,
               'descartadas': [{'titulo': i['titulo'], 'fuente': i['fuente'], 'motivo': m} for i, m in descartadas[:60]]},
              open(os.path.join(salida, 'lista.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    sel.marcar([n['id'] for n in notas], ahora); sel.guardar()
    os.remove(audio) if a.limpiar else None
    print('Listo: %s (%.1f min de video, %.0f s de proceso)' % (video, total / 60, time.time() - t0), flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('producir')
    p.add_argument('--franja', default='auto')
    p.add_argument('--salida', default='salida')
    p.add_argument('--estado', default='estado')
    p.add_argument('--minutos', type=float, default=None, help='duración objetivo del bucle (por defecto 60-120, limitada por la franja)')
    p.add_argument('--interludio', type=float, default=None, help='minutos de música entre bloques')
    p.add_argument('--pista-min', type=float, default=4.5)
    p.add_argument('--offline', action='store_true', help='usa datos de prueba en vez de internet')
    p.add_argument('--resolucion', default='1280x720')
    p.add_argument('--limpiar', action='store_true')
    a = ap.parse_args()
    producir(a)


if __name__ == '__main__':
    main()
