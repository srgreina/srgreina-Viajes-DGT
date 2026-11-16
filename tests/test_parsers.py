"""Tests con XML sintético basado en la estructura publicada de los feeds (no son datos reales)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))

from parsers import parse_incidencias, parse_located, parse_paneles  # noqa: E402
from realtime import diff  # noqa: E402

NS = (
    'xmlns:d2="http://levelC/schema/3/d2Payload" '
    'xmlns:sit="http://levelC/schema/3/situationPublication" '
    'xmlns:com="http://levelC/schema/3/common" '
    'xmlns:loc="http://levelC/schema/3/locationReferencing" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
)

INCIDENCIAS = f"""<?xml version="1.0" encoding="UTF-8"?>
<d2:payload {NS} xsi:type="sit:SituationPublication">
  <com:publicationTime>2026-11-15T20:22:23.656+01:00</com:publicationTime>
  <sit:situation id="2816645">
    <sit:situationRecord xsi:type="sit:RoadOrCarriagewayOrLaneManagement" id="18811074" version="2">
      <sit:situationRecordCreationTime>2025-12-12T08:11:34+01:00</sit:situationRecordCreationTime>
      <sit:validity>
        <com:validityStatus>active</com:validityStatus>
        <com:validityTimeSpecification>
          <com:overallStartTime>2025-12-12T08:05:19+01:00</com:overallStartTime>
        </com:validityTimeSpecification>
      </sit:validity>
      <sit:roadOrCarriagewayOrLaneManagementType>narrowLanes</sit:roadOrCarriagewayOrLaneManagementType>
      <sit:groupOfLocations>
        <loc:linearLocation>
          <loc:roadNumber>N-400</loc:roadNumber>
          <loc:from>
            <loc:pointCoordinates><loc:latitude>39.993732</loc:latitude><loc:longitude>-3.6074991</loc:longitude></loc:pointCoordinates>
            <loc:kilometrePoint>37.1</loc:kilometrePoint>
          </loc:from>
          <loc:to>
            <loc:pointCoordinates><loc:latitude>39.994446</loc:latitude><loc:longitude>-3.6054852</loc:longitude></loc:pointCoordinates>
            <loc:kilometrePoint>37.3</loc:kilometrePoint>
          </loc:to>
        </loc:linearLocation>
      </sit:groupOfLocations>
    </sit:situationRecord>
  </sit:situation>
  <sit:situation id="3343801">
    <sit:situationRecord xsi:type="sit:MaintenanceWorks" id="5684393" version="1">
      <sit:situationRecordCreationTime>2023-11-21T18:50:51+01:00</sit:situationRecordCreationTime>
      <sit:roadMaintenanceType>roadworks</sit:roadMaintenanceType>
    </sit:situationRecord>
  </sit:situation>
</d2:payload>
"""

PANELES = f"""<?xml version="1.0" encoding="UTF-8"?>
<d2:payload {NS}>
  <com:publicationTime>2026-11-15T20:20:00+01:00</com:publicationTime>
  <vmsUnit id="VMS-1">
    <vmsMessage><textLine>RETENCION KM 12</textLine><textLine>PRECAUCION</textLine></vmsMessage>
  </vmsUnit>
  <vmsUnit id="VMS-2"><timeLastSet>x</timeLastSet></vmsUnit>
</d2:payload>
"""

LOCATED = f"""<?xml version="1.0" encoding="UTF-8"?>
<d2:payload {NS}>
  <device id="RAD-1">
    <name><com:value>Radar A-7 km 230</com:value></name>
    <loc:roadNumber>A-7</loc:roadNumber>
    <loc:pointCoordinates><loc:latitude>36.7</loc:latitude><loc:longitude>-4.4</loc:longitude></loc:pointCoordinates>
    <loc:kilometrePoint>230</loc:kilometrePoint>
    <stillImageUrl>https://example.invalid/cam1.jpg</stillImageUrl>
  </device>
  <device id="SIN-COORD"><name><com:value>sin posicion</com:value></name></device>
</d2:payload>
"""


class TestParsers(unittest.TestCase):
    def test_incidencias(self):
        items, meta = parse_incidencias(INCIDENCIAS.encode())
        self.assertEqual(meta["published"], "2026-11-15T20:22:23.656+01:00")
        self.assertEqual([i["id"] for i in items], ["18811074", "5684393"])
        a = items[0]
        self.assertEqual(a["kind"], "RoadOrCarriagewayOrLaneManagement")
        self.assertEqual(a["road"], "N-400")
        self.assertEqual(a["pk"], [37.1, 37.3])
        self.assertEqual(a["a"], [39.993732, -3.607499])  # coordenadas a 6 decimales
        self.assertEqual(a["b"], [39.994446, -3.605485])
        self.assertEqual(a["status"], "active")
        self.assertEqual(a["start"], "2025-12-12T08:05:19+01:00")
        self.assertIn("narrowLanes", a["types"])
        self.assertEqual(items[1]["types"], ["roadworks"])

    def test_paneles(self):
        items, _ = parse_paneles(PANELES.encode())
        self.assertEqual([i["id"] for i in items], ["VMS-1"])
        self.assertEqual(items[0]["texts"], ["RETENCION KM 12", "PRECAUCION"])

    def test_located(self):
        items, _ = parse_located(LOCATED.encode())
        self.assertEqual(len(items), 1)
        r = items[0]
        self.assertEqual((r["id"], r["road"], r["pk"]), ("RAD-1", "A-7", [230.0]))
        self.assertEqual(r["urls"], ["https://example.invalid/cam1.jpg"])
        self.assertEqual((r["lat"], r["lon"]), (36.7, -4.4))

    def test_diff(self):
        prev = [{"id": "1", "v": 1}, {"id": "2", "v": 1}, {"id": "3", "v": 1}]
        cur = [{"id": "1", "v": 1}, {"id": "2", "v": 2}, {"id": "4", "v": 1}]
        ev = {(e["ev"], e["id"]) for e in diff(prev, cur, "T", bootstrap=False)}
        self.assertEqual(ev, {("change", "2"), ("close", "3"), ("open", "4")})
        boot = diff([], cur, "T", bootstrap=True)
        self.assertTrue(all(e.get("boot") for e in boot))


if __name__ == "__main__":
    unittest.main()
