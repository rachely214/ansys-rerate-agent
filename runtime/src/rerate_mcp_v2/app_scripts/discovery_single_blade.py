# Python Script, API Version = V261
# Runs INSIDE Ansys Discovery. One main blade on a hub slice, for the structural check.
# Slice = hub flowpath offset `depth` into the metal, swept over the blade's own theta range + `theta_margin_deg`
# each side (no cut passes through the blade). Bottom face of the slice = fixed support. Optional root fillet.
# Saves <out>.stp (and .dsco). All numbers come from argsDict; no defaults.
from SpaceClaim.Api.V261 import *
from SpaceClaim.Api.V261.Geometry import *
from SpaceClaim.Api.V261.Modeler import *
from SpaceClaim.Api.V261.Scripting.Commands import *
from SpaceClaim.Api.V261.Scripting.Commands.CommandOptions import *
from SpaceClaim.Api.V261.Scripting.Selection import *
from SpaceClaim.Api.V261.Scripting.Helpers import ViewHelper
import math, os
from System.Collections.Generic import List

import traceback as _tb
log = []
try:
    def A(k):
        if not argsDict.ContainsKey(k):
            raise Exception("missing script argument: " + k)
        return argsDict[k]
    GEO = A("geo"); OUT = A("out"); TO_M = float(A("to_m")); DEPTH = float(A("depth"))
    FIL = float(A("fillet")); R_TE = float(A("r_te")); MARG = math.radians(float(A("theta_margin_deg")))
    STRIDE = int(A("stride")); RMIN_PAD = float(A("le_pad"))
    TE_INSET = float(A("te_inset")); FIT_TOL = float(A("fit_tol_m"))
    log = []
    def P(x, y, z): return Point.Create(x * TO_M, y * TO_M, z * TO_M)
    def rd(p): return [tuple(float(v) for v in l.split()) for l in open(p) if len(l.split()) == 3]
    def sections(p):
        bl = []
        for l in open(p):
            if l.startswith("##"): bl.append([]); continue
            if l.startswith("#"): bl[-1].append([]); continue
            v = l.split()
            if len(v) == 3: bl[-1][-1].append(tuple(float(a) for a in v))
        return bl
    def nm(b, n):
        try: b.SetName(n)
        except Exception: b.Name = n

    ClearAll()
    part = GetRootPart()
    secs = sections(os.path.join(GEO, "profile.crv"))[0]
    th = [math.atan2(y, x) for s in secs for (x, y, z) in s]
    t0 = min(th) - MARG; t1 = max(th) + MARG
    hub = [(r, z) for (r, _, z) in rd(os.path.join(GEO, "hub.crv"))]
    rmin = min(math.hypot(x, y) for (x, y, z) in secs[0]) - RMIN_PAD
    # The slice rim must not coincide with the blade trailing edge: a rim exactly at the TE leaves a sliver face
    # that Mechanical cannot mesh, and adding an interpolated rim point AT the cut radius makes Discovery absorb
    # the blade faces during the merge (seen live: 6 faces instead of 9). So the cut radius only FILTERS existing
    # hub points (the rim ends at the last hub point inside it). Inset comes from the config (geometry_tolerances).
    R_RIM = R_TE * (1.0 - TE_INSET)  # config geometry_tolerances.hub_cut_te_inset_fraction
    top = [(r, z) for (r, z) in hub if rmin <= r <= R_RIM]
    bot = []
    for i, (r, z) in enumerate(top):
        a = top[max(0, i - 1)]; b = top[min(len(top) - 1, i + 1)]
        tr, tz = b[0] - a[0], b[1] - a[1]; L = math.hypot(tr, tz)
        nr, nz = tz / L, -tr / L
        if nz < 0: nr, nz = -nr, -nz
        bot.append((r + DEPTH * nr, z + DEPTH * nz))
    pt = List[Point](); pb = List[Point]()
    for r, z in top[::2] + [top[-1]]: pt.Add(P(r, 0, z))
    for r, z in bot[::2] + [bot[-1]]: pb.Add(P(r, 0, z))
    cv = List[ITrimmedCurve]()
    cv.Add(CurveSegment.Create(NurbsCurve.CreateThroughPoints(False, pt, FIT_TOL)))
    cv.Add(CurveSegment.Create(pt[pt.Count - 1], pb[pb.Count - 1]))
    cv.Add(CurveSegment.Create(NurbsCurve.CreateThroughPoints(False, pb, FIT_TOL)))
    cv.Add(CurveSegment.Create(pb[0], pt[0]))
    xz = Plane.Create(Frame.Create(Point.Origin, Direction.DirX, Direction.DirZ))
    arc = Circle.Create(Frame.Create(P(0, 0, top[0][1]), Direction.DirX, Direction.DirY), top[0][0] * TO_M)
    path = List[ITrimmedCurve](); path.Add(CurveSegment.Create(arc, Interval.Create(0.0, t1 - t0)))
    slab = Body.SweepProfile(Profile(xz, cv), path)
    slab.Transform(Matrix.CreateRotation(Line.Create(Point.Origin, Direction.DirZ), t0))
    hub_db = DesignBody.Create(part, "hub_slice", slab)
    log.append("hub slice closed=%s" % slab.IsClosed)

    def resample(s, n=201):
        d = [0.0]
        for i in range(1, len(s)):
            d.append(d[-1] + math.sqrt(sum((s[i][k] - s[i - 1][k]) ** 2 for k in range(3))))
        L = d[-1]; out = []; j = 0
        for i in range(n):
            t = L * i / (n - 1)
            while j < len(d) - 2 and d[j + 1] < t: j += 1
            f = (t - d[j]) / max(d[j + 1] - d[j], 1e-12)
            out.append(tuple(s[j][k] + f * (s[j + 1][k] - s[j][k]) for k in range(3)))
        return out
    n0 = part.Bodies.Count; crvs = []
    for s in [resample(s) for s in secs]:
        s2 = s[::STRIDE]
        if s2[-1] != s[-1]: s2.append(s[-1])
        pl = List[Point]()
        for p in s2: pl.Add(P(*p))
        pl.Add(pl[0])
        crvs.append(DesignCurve.Create(part, CurveSegment.Create(NurbsCurve.CreateThroughPoints(False, pl, FIT_TOL))))
    Loft.Create(Selection.Create(crvs), Selection.Empty(), LoftOptions(), None)
    for c in crvs: c.Delete()
    bd = list(part.Bodies)[n0]
    for e in [e for e in bd.Edges if e.Shape.Faces.Count == 1]:
        Fill.Execute(Selection.Create([e]), Selection.Empty(), FillOptions(), FillMode.ThreeD, None)
    bd = list(part.Bodies)[n0]; nm(bd, "blade")
    v_blade = 0.0
    try:
        v_blade = bd.Shape.Volume
        log.append("blade closed=%s vol_m3=%.6g" % (bd.Shape.IsClosed, v_blade))
    except Exception as e:
        log.append("blade volume n/a (%s)" % str(e)[:60])
    n_before = part.Bodies.Count
    try:
        Combine.Merge(BodySelection.Create([hub_db, bd]), None)
    except Exception as e:
        log.append("merge retry: " + str(e)[:60])
        s = hub_db.Shape.Copy(); s.Unite(List[Body]([bd.Shape.Copy()]))
        hub_db.Delete(); bd.Delete(); DesignBody.Create(part, "merged", s)
    def _vol(b):
        try:
            return b.Shape.Volume if b.Shape.IsClosed else 0.0
        except Exception:
            return 0.0
    log.append("bodies before/after merge %d/%d, volumes %s" % (n_before, part.Bodies.Count,
               ["%.4g" % _vol(b) for b in part.Bodies]))
    if part.Bodies.Count != 1:
        raise Exception("blade and hub slice did not merge into one body (blade likely not touching the slice)")
    imp = max(list(part.Bodies), key=_vol); nm(imp, "single_blade")
    log.append("after merge faces=%d vol_m3=%.6g" % (imp.Shape.Faces.Count, _vol(imp)))
    if FIL > 0:
        # root fillet edges = edges between the hub-slice top face and blade faces. Hub top/bottom are the two
        # largest non-planar faces; the top one is the face that shares edges with the blade faces.
        cands = [f for f in imp.Faces if f.Shape.Geometry.GetType().Name != "Plane"]
        areas = sorted(cands, key=lambda f: -f.Shape.Area)
        fil = []
        if len(areas) >= 2:
            ht, hb = areas[0], areas[1]
            adj = lambda f: sum(1 for e in f.Edges for g in e.Faces if g != f and g not in (ht, hb))
            if adj(hb) > adj(ht): ht, hb = hb, ht
            for e in ht.Edges:
                o = [g for g in e.Faces if g != ht]
                if o and o[0].Shape.Geometry.GetType().Name != "Plane" and o[0] != hb: fil.append(e)
            # Only the long blade-root edges get the fillet. Short edges (LE/TE caps meeting the hub, cone rim)
            # produce tiny fillet patches Mechanical cannot mesh. Keep edges longer than 10x the fillet radius.
            fil = [e for e in fil if e.Shape.Length > 10.0 * FIL * TO_M]
            log.append("fillet edges kept %d" % len(fil))
        n_faces_before = imp.Shape.Faces.Count
        v_before = _vol(imp)
        try:
            ConstantRound.Execute(EdgeSelection.Create(fil), FIL * TO_M, ConstantRoundOptions(), None)
            imp = [b for b in part.Bodies if b.Name == "single_blade"][0]
            # A good root fillet ADDS faces and barely changes the volume. If faces drop or the volume falls by
            # more than the blade volume, the fillet consumed the blade: undo it and continue without a fillet.
            if imp.Shape.Faces.Count < n_faces_before or _vol(imp) < v_before - 0.5 * v_blade:
                log.append("root fillet REMOVED blade faces (%d -> %d); fillet undone" %
                           (n_faces_before, imp.Shape.Faces.Count))
                Undo.Execute() if "Undo" in globals() else None
                raise Exception("root fillet damaged the blade; rebuild with structural.root_fillet_radius 0 or a "
                                "smaller radius")
            log.append("root fillet on %d edges ok (faces %d -> %d)" % (len(fil), n_faces_before,
                                                                         imp.Shape.Faces.Count))
        except Exception as e:
            raise Exception("root fillet step failed: " + str(e)[:200])
    imp = [b for b in part.Bodies if b.Name == "single_blade"][0]
    # Sanity: the merged solid must contain the blade (merged volume >= hub slice + most of the blade volume).
    v_imp = _vol(imp)
    log.append("final faces=%d vol_m3=%.6g" % (imp.Shape.Faces.Count, v_imp))
    if imp.Shape.Faces.Count < 9:
        raise Exception("merged single blade has only %d faces; the blade was absorbed or lost in the merge "
                        "(expected hub slice faces + pressure/suction/LE/tip/TE faces)" % imp.Shape.Faces.Count)
    DocumentSave.Execute(OUT + ".stp", ExportOptions.Create())
    # The STEP length unit must be metres (Discovery's internal unit). Mechanical then reads the true size; a STEP
    # tagged with another unit while holding metre values imports 1000x too large and will not mesh.
    try:
        with open(OUT + ".stp") as _f:
            _head = _f.read(20000)
        if "LENGTH_UNIT" in _head and ".METRE." not in _head.split("LENGTH_UNIT")[1][:120] and \
                ".METRE." not in _head.split("LENGTH_UNIT")[0][-120:]:
            log.append("STEP length unit is not metre; check the file header")
    except Exception:
        pass
    DocumentSave.Execute(OUT + ".dsco")
    ViewHelper.SetViewMode(InteractionMode.Solid, None); ViewHelper.ZoomToEntity()
    result = {"log": " | ".join(log), "closed": str(imp.Shape.IsClosed), "volume_m3": "%.9g" % imp.Shape.Volume,
              "faces": str(imp.Shape.Faces.Count), "step": OUT + ".stp",
              "step_bytes": str(os.path.getsize(OUT + ".stp")) if os.path.exists(OUT + ".stp") else "0"}
except Exception as _e:
    result = {"error": str(_e)[:800], "trace": _tb.format_exc()[-1500:], "log": " | ".join(log)}
