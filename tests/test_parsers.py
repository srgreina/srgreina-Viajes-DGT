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
      <sit:causeType>roadMaintenance</sit:causeType>
      <sit:roadMaintenanceType>roadworks</sit:roadMaintenanceType>
      <sit:vehicleType>anyVehicle</sit:vehicleType>
      <sit:laneUsage>allLanesCompleteCarriageway</sit:laneUsage>
      <sit:roadOrCarriagewayOrLaneManagementType>narrowLanes</sit:roadOrCarriagewayOrLaneManagementType>
      <sit:groupOfLocations>
        <loc:linearLocation>
          <loc:roadName>N-400</loc:roadName>
          <loc:tpegDirectionRoad>both</loc:tpegDirectionRoad>
          <loc:tpegLinearLocationType>segment</loc:tpegLinearLocationType>
          <loc:to>
            <loc:pointCoordinates><loc:latitude>39.994446</loc:latitude><loc:longitude>-3.6054852</loc:longitude></loc:pointCoordinates>
            <loc:kilometrePoint>37.3</loc:kilometrePoint>
          </loc:to>
          <loc:from>
            <loc:pointCoordinates><loc:latitude>39.993732</loc:latitude><loc:longitude>-3.6074991</loc:longitude></loc:pointCoordinates>
            <loc:kilometrePoint>37.1</loc:kilometrePoint>
          </loc:from>
          
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
<d2:payload {NS} xmlns:vms="http://levelC/schema/3/vms">
  <com:publicationTime>2026-11-15T20:20:00+01:00</com:publicationTime>
  <vms:vmsControllerStatus>
    <vms:vmsControllerReference targetClass="vms:VmsController" id="167938"/>
    <vms:vmsStatus vmsIndex="1"><vms:vmsStatus/></vms:vmsStatus>
  </vms:vmsControllerStatus>
  <vms:vmsControllerStatus>
    <vms:vmsControllerReference targetClass="vms:VmsController" id="61441"/>
    <vms:vmsStatus vmsIndex="1">
      <vms:vmsStatus>
        <vms:vmsMessage messageIndex="1">
          <vms:vmsMessage>
            <vms:timeLastSet>2026-11-16T06:05:49.000+01:00</vms:timeLastSet>
            <vms:displayAreaSettings displayAreaIndex="1">
              <vms:displayAreaSettings xsi:type="vms:PictogramDisplay">
                <vms:pictogram xsi:type="vms:RegularPictogram">
                  <vms:customPictogramCode>R301100I</vms:customPictogramCode>
                </vms:pictogram>
              </vms:displayAreaSettings>
            </vms:displayAreaSettings>
            <vms:displayAreaSettings displayAreaIndex="2">
              <vms:displayAreaSettings xsi:type="vms:TextDisplay">
                <vms:textLine lineIndex="1">
                  <vms:textLine>
                    <vms:textLine> VELOCIDAD
CONTROLADA
POR RADAR</vms:textLine>
                    <vms:lineFlashing>false</vms:lineFlashing>
                  </vms:textLine>
                </vms:textLine>
              </vms:displayAreaSettings>
            </vms:displayAreaSettings>
          </vms:vmsMessage>
        </vms:vmsMessage>
      </vms:vmsStatus>
    </vms:vmsStatus>
  </vms:vmsControllerStatus>
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
  <device id="CAM-1">
    <roadName>A-62</roadName><roadDestination>BURGOS</roadDestination>
    <pointCoordinates><latitude>42.2624</latitude><longitude>-3.9403</longitude></pointCoordinates>
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
        self.assertEqual(a["types"], ["roadMaintenance", "roadworks", "narrowLanes"])
        self.assertEqual(a["dir"], "both")
        self.assertEqual(a["lanes"], "allLanesCompleteCarriageway")
        self.assertNotIn("veh", a)  # anyVehicle no se guarda
        self.assertEqual(items[1]["types"], ["roadworks"])

    def test_paneles(self):
        items, _ = parse_paneles(PANELES.encode())
        self.assertEqual([i["id"] for i in items], ["61441.1"])  # sin mensaje -> no aparece
        p = items[0]
        self.assertEqual(p["ctrl"], "61441")
        self.assertEqual(p["texts"], ["VELOCIDAD / CONTROLADA / POR RADAR"])
        self.assertEqual(p["picts"], ["R301100I"])
        self.assertEqual(p["time"], "2026-11-16T06:05:49.000+01:00")

    def test_located(self):
        items, _ = parse_located(LOCATED.encode())
        self.assertEqual(len(items), 2)
        c = items[1]
        self.assertEqual((c["id"], c["road"], c["dest"]), ("CAM-1", "A-62", "BURGOS"))
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
