"""Filtro y selección: excluye lo morboso/negativo/farándula, puntúa utilidad pública y positividad,
evita repetidos y equilibra 55 % interés público / 45 % buenas noticias."""
import json, os, random, re
from datetime import datetime, timedelta, timezone

from .util import palabras, sin_tildes

EXCLUIR = r"""asesin\w* homicid\w* crimen\w* cadaver\w* balacer\w* sicari\w* violaci\w* abus\w* secuestr\w* femicid\w* narco\w*
 muert\w* fallec\w* masacre\w* tiroteo\w* apuñal\w* decapit\w* atentado\w* terroris\w* suicid\w* accidente\w* choque\w* colision\w*
 incendio\w* tragedia\w* guerra\w* bombardeo\w* misil\w* ataque\w* herid\w* detenid\w* arrest\w* capturad\w* estafa\w* robo\w* asalto\w*
 famos\w* farandula\w* escandalo\w* polemic\w* infidelidad\w* divorcio\w* chisme\w* influencer\w* reality\w* corrupci\w* acusad\w*
 imputad\w* condena\w* prision\w* carcel\w* cadena\ perpetua"""
EXCLUIR_RX = re.compile(r'\b(?:' + '|'.join(w.replace('\\w*', r'\w*') for w in EXCLUIR.split()) + r')\b')

POSITIVAS = r"""logra\w* exito\w* celebr\w* premi\w* gan\w* record inaugur\w* innov\w* descubr\w* avanc\w* mejora\w* recuper\w* restaur\w*
 beca\w* reconoc\w* orgullo\w* solidar\w* voluntari\w* reforest\w* conserv\w* creci\w* inclusi\w* feria\w* festival\w* apertura\w*
 nuevo\ nueva\ lanz\w* campe\w* medalla\w* aprendiz\w* talento\w* emprend\w* rescat\w* adopci\w* donaci\w* esperanza\w* histori\w* inedit\w*"""
UTIL = r"""beca\w* tramite\w* salud vacun\w* cita\w* empleo\w* trabajo\w* precio\w* tarifa\w* impuesto\w* hacienda subsidio\w* bono\w*
 matricula\w* calendario\w* lluvia\w* pronostico\w* alerta\w* servicio\w* licencia\w* pension\w* ccss educacion colegio\w* escuela\w*
 universidad\w* curso\w* credito\w* ahorro\w* agua electricidad transporte\w* carretera\w* ruta\w* horario\w* inscripci\w* ministerio\w*"""

SECCIONES = {
    'deportes': r'futbol|gol|liga|partido|campeonato|mundial|portero|seleccion|atleta|torneo|deport\w*',
    'tu_bolsillo': r'precio\w*|tarifa\w*|impuesto\w*|ahorro|credito|salario\w*|inflacion|tipo de cambio|economi\w*|bono|subsidio',
    'tramites': r'tramite\w*|requisito\w*|inscripci\w*|licencia\w*|cita\w*|pasaporte|cedula|marchamo|formulario\w*',
    'salud': r'salud|vacun\w*|hospital\w*|enfermedad\w*|nutricion|ccss|medic\w*|bienestar',
    'educacion': r'beca\w*|educacion|colegio\w*|escuela\w*|universidad\w*|matricula|estudiante\w*|curso\w*|mep|docente\w*',
    'ambiente': r'ambient\w*|naturaleza|biodiversidad|reforest\w*|conserv\w*|clima|parque nacional|sinac|fauna|flora|ecolog\w*|restaur\w* de',
    'tecnologia': r'tecnolog\w*|ciencia|cientific\w*|inteligencia artificial|satelite\w*|robot\w*|investigaci\w*|nasa|espacio',
    'cultura': r'cultura\w*|arte|musica|teatro|cine|festival\w*|mascarada|tradici\w*|museo\w*|libro\w*',
    'emprendedores': r'emprend\w*|pyme\w*|negocio\w*|startup\w*|innovaci\w*',
}


def _rx(lista):
    return re.compile(r'\b(?:' + '|'.join(lista.split()) + r')', re.I)


POS_RX, UTIL_RX = _rx(POSITIVAS.replace('\\ ', '_')), _rx(UTIL)


def evaluar(it, ahora=None, max_horas=96):
    """Devuelve (aceptada, motivo, info). info incluye seccion, tipo ('interes'|'positiva'), puntajes."""
    ahora = ahora or datetime.now(timezone.utc)
    base = sin_tildes((it['titulo'] + ' ' + it.get('resumen', '')))
    cuerpo = sin_tildes(it.get('texto', '')[:1500])
    if len(it.get('texto', '')) < 120 and len(it.get('resumen', '')) < 80:
        return False, 'texto insuficiente', {}
    if it.get('fecha'):
        f = datetime.fromisoformat(it['fecha'])
        if ahora - f > timedelta(hours=max_horas):
            return False, 'antigua', {}
    m = EXCLUIR_RX.search(base) or EXCLUIR_RX.search(cuerpo[:400])
    if m:
        return False, 'excluida (%s)' % m.group(0), {}
    pos = len(POS_RX.findall(base)) * 2 + len(POS_RX.findall(cuerpo))
    util = len(UTIL_RX.findall(base)) * 2 + len(UTIL_RX.findall(cuerpo))
    seccion = it.get('hint') or 'nacionales'
    if seccion == 'internacionales' or it.get('pais') == 'int':
        seccion = it.get('hint') if it.get('hint') not in ('internacionales', '') else 'internacionales'
    mejor, nm = None, 0
    for s, rx in SECCIONES.items():
        n = len(re.findall(r'\b(?:' + rx + r')', base))
        if n > nm:
            mejor, nm = s, n
    if mejor and (nm >= 1 and (seccion in ('nacionales', 'internacionales', '') or it.get('pais') == 'cr')):
        if seccion == 'internacionales' and it.get('pais') == 'int' and mejor not in ('deportes',):
            pass  # la nota de agencia internacional se queda en Internacionales salvo deportes
        else:
            seccion = mejor
    tipo = 'positiva' if pos >= 3 else 'interes'
    if pos < 1 and util < 1 and it.get('pais') != 'int':
        return False, 'sin interés claro', {}
    return True, 'ok', {'seccion': seccion, 'tipo': tipo, 'pos': pos, 'util': util}


def _tokens(t):
    return set(w for w in palabras(t) if len(w) > 3)


def parecido(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


class Seleccion:
    def __init__(self, estado_path, reuso_horas=20):
        self.path = estado_path
        self.estado = {'usadas': {}}
        if os.path.exists(estado_path):
            try:
                self.estado = json.load(open(estado_path, encoding='utf-8'))
            except Exception:
                pass
        self.reuso = timedelta(hours=reuso_horas)

    def guardar(self):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        # limpia usadas con más de 10 días
        lim = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        self.estado['usadas'] = {k: v for k, v in self.estado['usadas'].items() if v > lim}
        json.dump(self.estado, open(self.path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    def disponible(self, it, ahora):
        u = self.estado['usadas'].get(it['id'])
        return not u or ahora - datetime.fromisoformat(u) > self.reuso

    def marcar(self, ids, ahora=None):
        ahora = ahora or datetime.now(timezone.utc)
        for i in ids:
            self.estado['usadas'][i] = ahora.isoformat()

    def candidatas(self, items, ahora=None):
        """Evalúa, quita duplicados (mismo enlace o título muy parecido) y devuelve (aceptadas, descartadas)."""
        ahora = ahora or datetime.now(timezone.utc)
        ok, no, vistos = [], [], []
        for it in items:
            acept, motivo, info = evaluar(it, ahora)
            if not acept:
                no.append((it, motivo)); continue
            if any(it['id'] == v['id'] or parecido(it['titulo'], v['titulo']) > 0.7 for v in vistos):
                no.append((it, 'repetida')); continue
            it.update(info); vistos.append(it); ok.append(it)
        return ok, no

    def elegir(self, candidatas, n, ratio_pos=0.45, por_seccion=2, ahora=None, semilla=None):
        """Elige n notas: ~45 % positivas, resto interés público, con variedad de secciones."""
        ahora = ahora or datetime.now(timezone.utc)
        rnd = random.Random(semilla)
        libres = [c for c in candidatas if self.disponible(c, ahora)]
        rnd.shuffle(libres)
        libres.sort(key=lambda c: -(c['util'] + c['pos'] * 0.6) + rnd.random())
        quiero_pos = round(n * ratio_pos)
        elegidas, cuenta = [], {}
        for tipo, cupo in (('positiva', quiero_pos), ('interes', n - quiero_pos)):
            for c in libres:
                if len([e for e in elegidas if e['tipo'] == tipo]) >= cupo:
                    break
                if c['tipo'] != tipo or c in elegidas or cuenta.get(c['seccion'], 0) >= por_seccion:
                    continue
                elegidas.append(c); cuenta[c['seccion']] = cuenta.get(c['seccion'], 0) + 1
        for c in libres:  # relleno si faltó de un tipo
            if len(elegidas) >= n:
                break
            if c not in elegidas and cuenta.get(c['seccion'], 0) < por_seccion + 1:
                elegidas.append(c); cuenta[c['seccion']] = cuenta.get(c['seccion'], 0) + 1
        return elegidas
