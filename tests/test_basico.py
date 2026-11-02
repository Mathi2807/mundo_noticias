import os, sys, unittest, json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mundo import util, filtro, redactor, ingesta, musica, animacion
import numpy as np


class T(unittest.TestCase):
    def test_numeros(self):
        self.assertEqual(util.numero_a_letras(2027), 'dos mil veintisiete')
        self.assertEqual(util.numero_a_letras(1_252_000), 'un millón doscientos cincuenta y dos mil')
        self.assertIn('por ciento', util.normalizar_tts('el 12% sube'))
        self.assertIn('veintiún', util.normalizar_tts('21 casos'))

    def test_filtro_excluye(self):
        it = {'titulo': 'Ataque con misiles deja muertos', 'resumen': 'x' * 100, 'texto': 'y' * 200, 'fecha': None, 'hint': '', 'pais': 'int'}
        self.assertFalse(filtro.evaluar(it)[0])

    def test_filtro_acepta_util(self):
        it = {'titulo': 'MEP presenta el calendario escolar 2027', 'resumen': 'Las clases inician en marzo para estudiantes de escuelas y colegios.',
              'texto': 'El Ministerio de Educación publicó el calendario escolar. ' * 4, 'fecha': None, 'hint': 'educacion', 'pais': 'cr'}
        ok, _, info = filtro.evaluar(it)
        self.assertTrue(ok); self.assertEqual(info['seccion'], 'educacion')

    def test_barreras_redactor(self):
        it = {'titulo': 'Titular', 'resumen': '', 'texto': 'Se vacunó a 300 niños en la escuela del pueblo durante la semana pasada.', 'fuente': 'MEP'}
        self.assertIn('no menciona la fuente', redactor.revisar('Se vacunó a 300 niños.', it))
        self.assertTrue(any('cifras' in p for p in redactor.revisar('Según el MEP vacunaron a 999 niños en total hoy mismo en la zona.', it)))

    def test_rss(self):
        x = b'<rss><channel><item><title>A</title><link>http://a/1</link><description>d</description></item></channel></rss>'
        self.assertEqual(ingesta.parsear_feed(x, {})[0]['url'], 'http://a/1')

    def test_musica_determinista(self):
        a, _ = musica.generar_pista('calma', 1, 0.3); b, _ = musica.generar_pista('calma', 1, 0.3)
        self.assertTrue(np.allclose(a, b)); self.assertLessEqual(abs(a).max(), 0.81)

    def test_boca(self):
        x = np.concatenate([np.zeros(22050), 0.3 * np.sin(np.arange(22050) * 0.1), np.zeros(22050)]).astype(np.float32)
        e = animacion.envolvente_boca(x, 44100, 25)
        self.assertLess(e[:10].max(), 0.05); self.assertGreater(e[18:30].max(), 0.5)


if __name__ == '__main__':
    unittest.main()
