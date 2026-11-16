"""Tests de aemet.py con CAP sintético (estructura publicada por AEMET, no son datos reales)."""
import io
import os
import sys
import tarfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from aemet import parse_poly, parse_tar  # noqa: E402

NOW = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)


def cap(ident, refs="", msg="Alert", status="Actual", nivel="naranja", expires="2026-09-09T23:59:59+02:00",
        poly="38.32,-0.99 38.33,-0.92 38.36,-0.83 38.32,-0.99", area="Litoral sur de Alicante"):
    refs_xml = f"<references>{refs}</references>" if refs else ""
    poly_xml = f"<polygon>{poly}</polygon>" if poly else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>{ident}</identifier><sent>2026-09-08T09:26:14-00:00</sent>
  <status>{status}</status><msgType>{msg}</msgType><scope>Public</scope>{refs_xml}
  <info><language>en-GB</language><event>Severe rain warning</event><severity>Severe</severity>
    <onset>2026-09-09T14:00:00+02:00</onset><expires>{expires}</expires>
    <description>One-hour accumulated precipitation: 40 mm.</description>
    <area><areaDesc>{area}</areaDesc>{poly_xml}</area></info>
  <info><language>es-ES</language><event>Aviso de lluvias de nivel {nivel}</event><severity>Severe</severity>
    <eventCode><valueName>AEMET-Meteoalerta fenomeno</valueName><value>PR;Lluvias</value></eventCode>
    <onset>2026-09-09T14:00:00+02:00</onset><expires>{expires}</expires>
    <description>Precipitación acumulada en una hora: 40 mm.</description>
    <parameter><valueName>AEMET-Meteoalerta nivel</valueName><value>{nivel}</value></parameter>
    <area><areaDesc>{area}</areaDesc>{poly_xml}
      <geocode><valueName>AEMET-Meteoalerta zona</valueName><value>770303</value></geocode></area></info>
</alert>"""


def tar_of(files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, xml in files.items():
            data = xml.encode("utf-8")
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


class AemetTests(unittest.TestCase):
    def test_aviso_basico(self):
        items = parse_tar(tar_of({"a.xml": cap("A1")}), NOW)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual((it["lvl"], it["ph"], it["area"], it["zone"]), ("naranja", "Lluvias", "Litoral sur de Alicante", "770303"))
        self.assertEqual(it["desc"], "Precipitación acumulada en una hora: 40 mm.")  # bloque es-ES
        self.assertEqual(it["from"], "2026-09-09T12:00:00Z")
        self.assertEqual(it["to"], "2026-09-09T21:59:59Z")
        self.assertEqual(it["poly"][0][0], [38.32, -0.99])

    def test_actualizacion_sustituye_y_se_descartan_cancel_caducado_sin_poligono(self):
        files = {
            "old.xml": cap("A1", nivel="amarillo"),
            "new.xml": cap("A2", refs="http://www.aemet.es,A1,2026-09-07T09:38:05-00:00", msg="Update"),
            "cancel.xml": cap("A3", msg="Cancel"),
            "expired.xml": cap("A4", expires="2026-09-09T10:00:00+02:00"),
            "nopoly.xml": cap("A5", poly=""),
            "junk.xml": "<no-xml",
            "readme.txt": "x",
        }
        items = parse_tar(tar_of(files), NOW)
        self.assertEqual([i["id"].split("#")[0] for i in items], ["A2"])
        self.assertEqual(items[0]["lvl"], "naranja")

    def test_poligono(self):
        self.assertIsNone(parse_poly("1,2 3,4"))
        self.assertEqual(parse_poly("1.00049,2 3,4.0006 5,6"), [[1.0, 2.0], [3.0, 4.001], [5.0, 6.0]])


if __name__ == "__main__":
    unittest.main()
