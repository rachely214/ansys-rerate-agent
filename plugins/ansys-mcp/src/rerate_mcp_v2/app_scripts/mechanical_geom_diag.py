# Runs INSIDE Ansys Mechanical. Geometry diagnostics for the imported single blade (no mesh, no solve).
# Reports per-face area/type, every edge length and the dihedral angle between the two faces at sample points,
# and flags short edges, small faces and near-tangent (sliver) or knife-edge face pairs. Fixed file; only a JSON
# argument block is substituted by the server.
import json, math
ARGS = json.loads(r'''__ARGS_JSON__''')
STEP = ARGS["step"]; SHORT = float(ARGS["short_edge_m"]); SMALL = float(ARGS["small_face_m2"])
for a in list(Model.Analyses): a.Delete()
try:
    ExtAPI.DataModel.Project.New() if hasattr(ExtAPI.DataModel.Project, "New") else None
except Exception:
    pass
gi = Model.GeometryImportGroup.AddGeometryImport()
gi.Import(STEP, Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic,
          Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences())
bodies = list(Model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
gb = bodies[0].GetGeoBody()
# GeoData (GetGeoBody) works in millimetres on this setup, independent of the display unit system (verified: geo
# volume in mm^3 equals the tree volume converted from its display unit). Convert to metres explicitly.
s = 1.0e-3
faces = [{"id": f.Id, "type": str(f.SurfaceType).replace("GeoSurface", ""), "area_m2": f.Area * s * s,
          "n_edges": len(list(f.Edges))} for f in gb.Faces]

def normal(face, p):
    try:
        uv = face.ParamAtPoint(p)
        n = face.NormalAtParam(uv[0], uv[1])
        return [n[0], n[1], n[2]]
    except Exception:
        return None

edges = []
for e in gb.Edges:
    fs = list(e.Faces)
    rec = {"id": e.Id, "len_m": e.Length * s, "faces": [f.Id for f in fs], "angle_deg": None}
    if len(fs) == 2:
        angs = []
        for t in (0.25, 0.5, 0.75):
            try:
                pt = e.PointAtParam(e.ParamAtPoint(e.Centroid) if t == 0.5 else
                                    e.StartParameter + t * (e.EndParameter - e.StartParameter))
            except Exception:
                pt = e.Centroid
            n1, n2 = normal(fs[0], pt), normal(fs[1], pt)
            if n1 and n2:
                d = max(-1.0, min(1.0, sum(a * b for a, b in zip(n1, n2))))
                angs.append(math.degrees(math.acos(d)))
        if angs:
            rec["angle_deg"] = [round(x, 2) for x in angs]
    edges.append(rec)
flags = {"short_edges": [x for x in edges if x["len_m"] < SHORT],
         "small_faces": [x for x in faces if x["area_m2"] < SMALL],
         "near_tangent_edges": [x for x in edges if x["angle_deg"] and min(x["angle_deg"]) < 5.0],
         "knife_edges": [x for x in edges if x["angle_deg"] and max(x["angle_deg"]) > 170.0]}
json.dumps({"n_faces": len(faces), "n_edges": len(edges), "volume_m3": gb.Volume * s ** 3, "length_scale_to_m": s,
            "faces": faces,
            "edges": edges, "flags": flags})
