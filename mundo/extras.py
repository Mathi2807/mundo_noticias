"""Segmentos propios de Mundo Noticias que no dependen de noticias: ¿Sabías que?, Hoy en la historia y promoción de las redes."""
import json, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SABIAS = [
    'Costa Rica abolió su ejército el primero de diciembre de mil novecientos cuarenta y ocho.',
    'El volcán Irazú, con más de tres mil cuatrocientos metros, es el volcán más alto del país.',
    'El cerro Chirripó, de unos tres mil ochocientos metros, es la montaña más alta de Costa Rica.',
    'Costa Rica guarda cerca del cinco por ciento de la biodiversidad del planeta en un territorio muy pequeño.',
    'El colón es la moneda del país desde mil ochocientos noventa y seis, y su nombre recuerda a Cristóbal Colón.',
    'El Teatro Nacional de Costa Rica fue inaugurado en mil ochocientos noventa y siete.',
    'La Isla del Coco fue declarada Patrimonio de la Humanidad por la Unesco en mil novecientos noventa y siete.',
    'El lago Arenal es el lago más grande de Costa Rica y es también un gran generador de energía.',
    'En los últimos años, Costa Rica ha producido más del noventa por ciento de su electricidad con fuentes renovables.',
    'La Universidad de Costa Rica fue fundada en mil novecientos cuarenta.',
    'En Costa Rica las mujeres votaron por primera vez en mil novecientos cuarenta y nueve.',
    'Cartago fue la capital del país hasta mil ochocientos veintitrés.',
    'Los pulpos tienen tres corazones y su sangre es de color azul.',
    'Un día en Venus dura más que un año en Venus, porque gira sobre sí mismo muy despacio.',
    'La miel bien guardada casi no se echa a perder: se han encontrado frascos comestibles de miles de años.',
    'El Parque Nacional Tortuguero es uno de los lugares donde anida la tortuga verde en el Caribe costarricense.',
    'Las estrellas que ves de noche pueden haberse apagado ya: su luz tarda años en llegar hasta nosotros.',
    'Los colibríes pueden batir sus alas decenas de veces por segundo y son habituales en los jardines ticos.',
]

EFEMERIDES = {
    (1, 1): 'Hoy es primero de enero, Año Nuevo.',
    (3, 8): 'Hoy se conmemora el Día Internacional de la Mujer.',
    (4, 11): 'Un once de abril de mil ochocientos cincuenta y seis, Juan Santamaría se convirtió en héroe nacional en la batalla de Rivas.',
    (4, 22): 'Hoy se celebra el Día de la Tierra.',
    (5, 1): 'Hoy se conmemora el Día Internacional del Trabajo.',
    (6, 5): 'Hoy se celebra el Día Mundial del Ambiente.',
    (7, 25): 'Un veinticinco de julio de mil ochocientos veinticuatro, el Partido de Nicoya, hoy Guanacaste, se anexó a Costa Rica.',
    (8, 2): 'Hoy es el Día de la Virgen de los Ángeles, patrona de Costa Rica.',
    (9, 15): 'Un quince de septiembre de mil ochocientos veintiuno, Centroamérica proclamó su independencia.',
    (10, 31): 'Hoy se celebra el Día Nacional de la Mascarada Tradicional Costarricense.',
    (11, 20): 'Hoy se celebra el Día Universal del Niño.',
    (12, 1): 'Un primero de diciembre de mil novecientos cuarenta y ocho, Costa Rica abolió su ejército.',
    (12, 25): 'Hoy es Navidad.',
}


def cargar_redes():
    return json.load(open(os.path.join(RAIZ, 'config', 'redes.json'), encoding='utf-8'))


def sabias_que(k):
    return {'id': 'sabias%d' % (k % len(SABIAS)), 'seccion': '¿Sabías que?', 'set': 'noticias', 'titular': '¿Sabías que…?',
            'sub': 'Dato curioso · Mundo Noticias', 'guion': '¿Sabías que? ' + SABIAS[k % len(SABIAS)], 'extra': True}


def efemeride(loc):
    t = EFEMERIDES.get((loc.month, loc.day))
    if not t:
        return None
    return {'id': 'efemeride', 'seccion': 'Hoy en la historia', 'set': 'noticias', 'titular': 'Hoy en la historia',
            'sub': 'Mundo Noticias', 'guion': 'Hoy en la historia. ' + t, 'extra': True}


def promo(k, redes=None):
    r = redes or cargar_redes()
    o = k % 3
    if o == 0:
        g = 'Si te gusta Mundo Noticias, síguenos en YouTube como Mundo Noticias T V, y activa la campanita para no perderte nada.'
        sub, t = 'YouTube: ' + r['youtube']['corto'], 'Síguenos en YouTube'
    elif o == 1:
        g = 'También estamos en Twitch como mundonoticiastv. Entra, sigue el canal y acompáñanos en directo.'
        sub, t = 'Twitch: ' + r['twitch']['corto'], 'Acompáñanos en Twitch'
    else:
        g = 'Únete a nuestra comunidad en Discord, donde puedes comentar las noticias y proponer temas. El enlace está en la barra de abajo y en la descripción del directo.'
        sub, t = 'Discord: ' + r['discord']['corto'], 'Únete en Discord'
    return {'id': 'promo%d' % o, 'seccion': 'Comunidad', 'set': 'noticias', 'titular': t, 'sub': sub, 'guion': g, 'extra': True}


def linea_barra(redes=None):
    r = redes or cargar_redes()
    return [('COMUNIDAD', 'YouTube: %s  ·  Twitch: %s  ·  Discord: %s' % (r['youtube']['corto'], r['twitch']['corto'], r['discord']['corto']))]
