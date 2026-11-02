"""Genera datos de prueba (RSS/JSON) con fechas recientes, para correr todo sin red."""
import json, os, sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

AQUI = os.path.dirname(os.path.abspath(__file__))


def rss(items):
    x = ['<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>t</title>']
    for t, u, d, c, horas in items:
        f = format_datetime(datetime.now(timezone.utc) - timedelta(hours=horas))
        x.append('<item><title>%s</title><link>%s</link><pubDate>%s</pubDate><description>%s</description><content:encoded><![CDATA[<p>%s</p>]]></content:encoded></item>' % (t, u, f, d, c))
    return ''.join(x) + '</channel></rss>'


def generar(carpeta=AQUI):
    os.makedirs(carpeta, exist_ok=True)
    onu = [
        ('La naturaleza resurge, pero falta financiación para restaurarla', 'https://news.un.org/es/story/2026/10/1542123',
         'Un informe presentado en la COP17 de biodiversidad muestra avances en la restauración de ecosistemas.',
         'Unos 252 millones de hectáreas en 149 países ya están en proceso de restauración, según un informe presentado en la conferencia de biodiversidad COP17, en Ereván, Armenia. '
         'Se han creado más de un millón de empleos verdes. Sin embargo, la financiación anual tendría que pasar de 64.000 a 296.000 millones de dólares, más del cuádruple. '
         'El informe indica que esa inversión podría generar hasta 32 millones de empleos en el mundo para 2030. Es un avance importante para la recuperación de los ecosistemas.', 20),
        ('Ataque con misiles deja decenas de muertos en una ciudad', 'https://news.un.org/es/story/2026/10/9999001',
         'Un bombardeo causó la muerte de civiles.', 'Un bombardeo con misiles dejó decenas de muertos y heridos en una ciudad. ' * 4, 10),
        ('La OMS lanza una campaña de vacunación que llegará a millones de niños', 'https://news.un.org/es/story/2026/10/1542200',
         'La campaña busca proteger a los menores contra el sarampión.',
         'La Organización Mundial de la Salud lanzó una campaña de vacunación contra el sarampión que llegará a más de 20 millones de niños en 30 países. '
         'La iniciativa, que cuenta con apoyo de varios gobiernos, pretende recuperar la cobertura perdida en los últimos años. Los equipos de salud visitarán escuelas y comunidades rurales durante los próximos meses.', 30),
    ]
    unafut = [
        ('Vega, de San Carlos, logra una marca inédita entre porteros', 'https://www.unafut.com/2026/10/13/vega-logra-una-marca-inedita',
         'El portero logró tres juegos con valoración superior a nueve.',
         'El portero José David Vega, de San Carlos, es el primer jugador de la Liga Promerica en lograr tres partidos seguidos con una valoración de 9,0 o más según Sofascore. '
         'En esos tres juegos mantuvo su portería en cero y acumuló 20 atajadas. Además, su club comunicó la ampliación de su contrato hasta 2028.', 50),
        ('Escándalo y polémica por pelea entre famosos tras partido', 'https://www.unafut.com/2026/10/30/escandalo-pelea',
         'Chisme del día.', 'Un escándalo de farándula protagonizado por famosos. ' * 6, 5),
    ]
    bbc = [
        ('Científicos descubren un método para reciclar plásticos con luz solar', 'https://www.bbc.com/mundo/articles/c0test1',
         'Un equipo de investigadores logró un avance en reciclaje.',
         'Un equipo internacional de científicos presentó un método innovador que permite reciclar ciertos plásticos usando solo luz solar. '
         'Los investigadores explicaron que el proceso reduce el consumo de energía y podría aplicarse en plantas pequeñas. El avance se publicó esta semana en una revista científica y abre la puerta a nuevas soluciones para el ambiente.', 18),
    ]
    for nombre, items in (('onu', onu), ('unafut', unafut), ('bbc', bbc)):
        open(os.path.join(carpeta, nombre + '.xml'), 'w', encoding='utf-8').write(rss(items))
    ahora = datetime.now(timezone.utc)
    ts = []
    for h in range(0, 24):
        t = ahora + timedelta(hours=h)
        ts.append({'time': t.strftime('%Y-%m-%dT%H:00:00Z'), 'data': {'instant': {'details': {'air_temperature': 24 + (h % 12) * 0.5}},
                   'next_1_hours': {'summary': {'symbol_code': 'rain'}, 'details': {'precipitation_amount': 0.4 if h > 6 else 0}},
                   'next_6_hours': {'summary': {'symbol_code': 'partlycloudy_day'}}}})
    json.dump({'properties': {'timeseries': ts}}, open(os.path.join(carpeta, 'met.json'), 'w'))
    json.dump({'venta': {'fecha': '2026-10-30', 'valor': 512.34}, 'compra': {'fecha': '2026-10-30', 'valor': 500.12}}, open(os.path.join(carpeta, 'hacienda.json'), 'w'))


if __name__ == '__main__':
    generar(sys.argv[1] if len(sys.argv) > 1 else AQUI)
