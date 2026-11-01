# Runs INSIDE Ansys Mechanical. Spin stress of one blade on a hub slice, at several mesh sizes (mesh study).
# Fixed file: the mechanical_v2 server substitutes only the JSON argument block below (values from the case and
# the config structural_meshing section). For each size: patch-independent tet mesh, solve, and report
#   peak equivalent stress (whole body), peak on blade faces, and the "body" stress = 99th percentile of nodal
#   stress on blade nodes farther than `exclude_m` from the root/hub-cut/support edges (away from sharp features).
import json, math
ARGS = json.loads(r'''__ARGS_JSON__''')
STEP = ARGS["step"]; MAT_FILE = ARGS["material_file"]; MAT = ARGS["material_name"]; OUT = ARGS["out_dir"]
RADS = float(ARGS["omega_rad_s"]); SIZES = [float(x) for x in ARGS["mesh_sizes_m"]]; MAXN = int(ARGS["max_nodes"])
MS = ARGS["meshing"]  # {method, min_size_ratio, refinement, growth, defeature_m, element_order}
EXCL = float(ARGS["exclude_m"])

for a in list(Model.Analyses): a.Delete()
try:
    ExtAPI.DataModel.Project.New() if hasattr(ExtAPI.DataModel.Project, "New") else None
except Exception:
    pass
gi = Model.GeometryImportGroup.AddGeometryImport()
gi.Import(STEP, Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.Format.Automatic,
          Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences())
ExtAPI.Application.ActiveUnitSystem = MechanicalUnitSystem.StandardMKS
if MAT not in [c.Name for c in Model.Materials.Children]:
    Model.Materials.Import(MAT_FILE)
bodies = list(Model.Geometry.GetChildren(DataModelObjectCategory.Body, True))
if len(bodies) != 1:
    raise Exception("expected exactly one body after import into a clean model, found %d" % len(bodies))
body = bodies[0]; body.Material = MAT
gb = body.GetGeoBody(); faces = list(gb.Faces)
planes = [f for f in faces if "Plane" in str(f.SurfaceType)]
def adj(f, g): return any(e in list(g.Edges) for e in f.Edges)
cands = [f for f in faces if "BSpline" in str(f.SurfaceType) and sum(1 for p in planes if adj(f, p)) >= 2]
cands = sorted(cands, key=lambda f: -f.Area)[:2]
cands.sort(key=lambda f: -f.Centroid[2])
bottom, hub_top = cands[0], cands[1]
# blade = every face that is not a cut plane, the support face or the hub top: pressure/suction/LE/TE/tip faces
# AND the root fillet faces (any surface type), so the fillet is part of the evaluated blade surface.
blade = [f for f in faces if f not in planes and f not in cands]
for n in (list(Model.NamedSelections.Children) if Model.NamedSelections else []):
    n.Delete()
def ns(name, ids):
    sm = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities); sm.Ids = ids
    n = Model.AddNamedSelection(); n.Location = sm; n.Name = name; return n
nb = ns("slice_bottom", [bottom.Id]); nbl = ns("blade_faces", [f.Id for f in blade])
# Singular features EXCLUDED from evaluation: only the planar cuts of the hub slice and the fixed-support face
# (modelling artefacts, not real geometry). The blade root / fillet is NOT excluded (DEC-15).
sharp_edges = []
for f in planes + [bottom]:
    sharp_edges += list(f.Edges)
# Root junction: hub-top edges shared with a blade face (fillet hub-side tangent line, or the sharp root line
# when there is no fillet). Nodes within ROOT_ZONE of it form the root/fillet zone, reported separately.
root_edges = [e for e in hub_top.Edges if any(g in blade for g in e.Faces)]
ROOT_ZONE = float(ARGS["root_zone_m"])
def edge_pts(e, n=40):
    # GeoEdge exposes start/end vertices and length but no parameter range; sample along the edge with
    # PointAtParam over [0, 1] when available, otherwise use the vertices and centroid.
    pts = []
    try:
        for i in range(n + 1):
            p = e.PointAtParam(i / float(n)); pts.append((p[0] * 1e-3, p[1] * 1e-3, p[2] * 1e-3))  # GeoData is mm
    except Exception:
        for v in list(e.Vertices):
            pts.append((v.X * 1e-3, v.Y * 1e-3, v.Z * 1e-3))
        c = e.Centroid; pts.append((c[0] * 1e-3, c[1] * 1e-3, c[2] * 1e-3))
    return pts
SHARP = [p for e in sharp_edges for p in edge_pts(e)]
ROOT = []
for e in root_edges:
    try:
        n_seg = max(40, int(e.Length * 1e-3 / (0.25 * ROOT_ZONE)) + 1)  # GeoData length in mm
    except Exception:
        n_seg = 400
    ROOT += edge_pts(e, n_seg)
if not ROOT:
    raise Exception("no blade-root edges found on the hub top face; cannot evaluate the root/fillet zone")
# blade root radius for the hand check: smallest radius on the blade faces (GeoData mm -> m)
R_ROOT = min(math.hypot(v.X, v.Y) for f in blade for e in f.Edges for v in e.Vertices) * 1e-3

mesh = Model.Mesh
mesh.ElementOrder = ElementOrder.Quadratic if MS["element_order"] == "quadratic" else ElementOrder.Linear
try:
    mesh.UseAdaptiveSizing = False
except Exception:
    pass
meth = None
if MS["method"] == "patch_independent_tet":
    meth = mesh.AddAutomaticMethod()
    sel = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities); sel.Ids = [gb.Id]
    meth.Location = sel
    meth.Method = MethodType.AllTriAllTet
    meth.Algorithm = MeshMethodAlgorithm.PatchIndependent
    meth.CurvatureNormalAngle = Quantity("0 [deg]")
    meth.Refinement = int(MS["refinement"]); meth.TetraGrowthRate = float(MS["growth"])
    meth.MeshBasedDefeaturing = True
    meth.DefeaturingTolerance = Quantity("%r [m]" % float(MS["defeature_m"]))

st = Model.AddStaticStructuralAnalysis()
fx = st.AddFixedSupport(); fx.Location = nb
rv = st.AddRotationalVelocity(); rv.DefineBy = LoadDefineBy.Components
rv.ZComponent.Output.DiscreteValues = [Quantity("%.6f [rad s^-1]" % RADS)]
s = st.Solution.AddEquivalentStress()
sb = st.Solution.AddEquivalentStress(); sb.Location = nbl; sb.Name = "Blade stress"
d = st.Solution.AddTotalDeformation()
study = []
for sz in SIZES:
    mesh.ElementSize = Quantity("%r [m]" % sz)
    if meth is not None:
        meth.MaximumElementSize = Quantity("%r [m]" % sz)
        meth.MinimumSizeLimit = Quantity("%r [m]" % (sz * float(MS["min_size_ratio"])))
    mesh.GenerateMesh()
    row = {"size_m": sz, "nodes": mesh.Nodes, "mesh_state": str(mesh.ObjectState)}
    if not (0 < mesh.Nodes <= MAXN and str(mesh.ObjectState) == "Solved"):
        row["skipped"] = "mesh failed or over node limit"; study.append(row); continue
    st.Solve(True)
    row["solve"] = str(st.Solution.Status)
    row["peak_Pa"] = s.Maximum.Value; row["blade_peak_Pa"] = sb.Maximum.Value
    row["max_def_m"] = d.Maximum.Value
    # bulk = blade nodes away from the cut/support edges AND outside the root zone; root/fillet zone = blade nodes
    # within ROOT_ZONE of the root junction (still away from the cut/support edges). Both mesh-studied.
    mdata = ExtAPI.DataModel.MeshDataByName(ExtAPI.DataModel.MeshDataNames[0])
    try:
        _u = str(mdata.Unit).lower()
    except Exception:
        _u = "mm"
    NODE_TO_M = {"m": 1.0, "mm": 1e-3, "cm": 1e-2, "in": 0.0254, "ft": 0.3048, "um": 1e-6}.get(_u, None)
    if NODE_TO_M is None:
        raise Exception("unknown mesh length unit %r" % _u)
    row["mesh_unit"] = _u
    vals, rvals = [], []
    n_cut, dr_min = 0, None
    try:
        ids = list(sb.PlotData["Node"]); sv = list(sb.PlotData["Values"])
        for nid, v in zip(ids, sv):
            nd = mdata.NodeById(nid)
            # Mesh node coordinates come back in the model's length unit (mm for the STEP import here), not
            # the active unit system; convert with the mesh unit so they match the m-based edge samples.
            px, py, pz = nd.X * NODE_TO_M, nd.Y * NODE_TO_M, nd.Z * NODE_TO_M
            droot = min(((px - a) ** 2 + (py - b) ** 2 + (pz - c) ** 2) for a, b, c in ROOT) ** 0.5
            dr_min = droot if dr_min is None else min(dr_min, droot)
            dcut = min(((px - a) ** 2 + (py - b) ** 2 + (pz - c) ** 2) for a, b, c in SHARP) ** 0.5
            if dcut <= EXCL:
                n_cut += 1
                continue
            (rvals if droot <= ROOT_ZONE else vals).append(v)
    except Exception as e:
        row["body_err"] = str(e)[:160]
    row["blade_nodes_total"] = len(ids) if "ids" in dir() else None
    row["excluded_cut_nodes"] = n_cut
    row["min_dist_to_root_m"] = dr_min
    row["root_pt_sample"] = ROOT[len(ROOT) // 2] if ROOT else None
    if vals:
        vals.sort(); row["body_p99_Pa"] = vals[int(0.99 * (len(vals) - 1))]; row["body_max_Pa"] = vals[-1]
        row["body_nodes"] = len(vals)
    if rvals:
        rvals.sort(); row["fillet_p99_Pa"] = rvals[int(0.99 * (len(rvals) - 1))]; row["fillet_max_Pa"] = rvals[-1]
        row["fillet_nodes"] = len(rvals)
    study.append(row)
ok = [r for r in study if r.get("solve") == "Done"]
img = OUT + "\\structural_stress_iso.png"
if ok:
    s.Activate(); Graphics.Camera.SetSpecificViewOrientation(ViewOrientationType.Iso); Graphics.Camera.SetFit()
    Graphics.ExportImage(img, GraphicsImageExportFormat.PNG)
msgs = [str(m.DisplayString)[:200] for m in ExtAPI.Application.Messages if "Error" in str(m.Severity)][-5:]
json.dumps({"study": study, "image": img if ok else None, "errors": msgs, "n_blade_faces": len(blade),
            "n_sharp_pts": len(SHARP), "n_root_pts": len(ROOT), "n_root_edges": len(root_edges),
            "exclude_m": EXCL, "root_zone_m": ROOT_ZONE, "volume_m3": gb.Volume * 1e-9, "r_root_m": R_ROOT})
