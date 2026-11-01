# Python Script, API Version = V261
# Runs INSIDE Ansys Discovery (SpaceClaim API). Builds an impeller solid from a BladeGen curve set:
#   hub band (hub flowpath revolved, offset `depth` into the metal) + blade rows (loft + fill caps),
#   rotate-copied `n_sets` times, merged, blades coloured orange (the changed part).
# Every number comes from argsDict (set by the geometry_v2 server from the approved case). No defaults.
from SpaceClaim.Api.V261 import *
from SpaceClaim.Api.V261.Geometry import *
from SpaceClaim.Api.V261.Modeler import *
from SpaceClaim.Api.V261.Scripting.Commands import *
from SpaceClaim.Api.V261.Scripting.Commands.CommandOptions import *
from SpaceClaim.Api.V261.Scripting.Selection import *
from SpaceClaim.Api.V261.Scripting.Helpers import ViewHelper
import math, os, time
from System.Collections.Generic import List

import traceback as _tb
log = []
try:
    def A(k):
        if not argsDict.ContainsKey(k):
            raise Exception("missing script argument: " + k)
        return argsDict[k]
    GEO = A("geo"); TO_M = float(A("to_m")); NB = int(A("n_sets")); DEPTH = float(A("depth"))
    R_TE = float(A("r_te")); STRIDE = int(A("stride"))
    TE_INSET = float(A("te_inset")); FIT_TOL = float(A("fit_tol_m"))
    log = []; T0 = time.time()
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
    # ---- hub disk: the hub flowpath (inlet to the trailing-edge radius) closed by a back face DEPTH behind the
    # exit hub point and a bore at the inlet hub radius, revolved 360 deg about z. The disk is a simplified solid
    # (customer disk geometry is not part of the case); it only carries the blades for display and volume checks.
    hub = [(r, z) for (r, _, z) in rd(os.path.join(GEO, "hub.crv"))]
    hp = [(r, z) for (r, z) in hub if r <= R_TE][::3]
    for i in range(len(hub) - 1):
        if hub[i][0] <= R_TE <= hub[i + 1][0]:
            f = (R_TE - hub[i][0]) / (hub[i + 1][0] - hub[i][0])
            hp.append((R_TE, hub[i][1] + f * (hub[i + 1][1] - hub[i][1])))
            break
    r_in, z_in = hp[0]
    r_te, z_te = hp[-1]
    z_back = z_te + DEPTH
    pts = List[Point]()
    for r, z in hp: pts.Add(P(r, 0, z))
    cv = List[ITrimmedCurve]()
    cv.Add(CurveSegment.Create(NurbsCurve.CreateThroughPoints(False, pts, FIT_TOL)))
    chain = [(r_te, z_te), (r_te, z_back), (r_in, z_back), (r_in, z_in)]
    for a, b in zip(chain[:-1], chain[1:]): cv.Add(CurveSegment.Create(P(a[0], 0, a[1]), P(b[0], 0, b[1])))
    xz = Plane.Create(Frame.Create(Point.Origin, Direction.DirX, Direction.DirZ))
    path = List[ITrimmedCurve]()
    path.Add(CurveSegment.Create(Circle.Create(Frame.Create(P(0, 0, z_in), Direction.DirX, Direction.DirY), TO_M)))
    hub_db = DesignBody.Create(part, "hub_disk", Body.SweepProfile(Profile(xz, cv), path))
    log.append("hub disk closed=%s" % hub_db.Shape.IsClosed)

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

    def make_blade(secs, name):
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
        b = list(part.Bodies)[n0]
        for e in [e for e in b.Edges if e.Shape.Faces.Count == 1]:
            Fill.Execute(Selection.Create([e]), Selection.Empty(), FillOptions(), FillMode.ThreeD, None)
        b = list(part.Bodies)[n0]; nm(b, name)
        log.append("%s closed=%s" % (name, b.Shape.IsClosed))
        return b

    rows = sections(os.path.join(GEO, "profile.crv"))
    blades = [make_blade(r, "blade_row_%d" % i) for i, r in enumerate(rows)]
    ax = Line.Create(Point.Origin, Direction.DirZ)
    for b in list(blades):
        for k in range(1, NB):
            c = b.Shape.Copy(); c.Transform(Matrix.CreateRotation(ax, 2 * math.pi * k / NB))
            blades.append(DesignBody.Create(part, "%s_%02d" % (b.Name, k), c))
    blade_names = set(b.Name for b in blades)
    try:
        Combine.Merge(BodySelection.Create([hub_db] + blades), None); log.append("merge ok")
    except Exception as e:
        log.append("merge FAIL " + str(e)[:200])
    bodies = list(part.Bodies)
    def _vol(b):
        try:
            return b.Shape.Volume if b.Shape.IsClosed else 0.0
        except Exception:
            return 0.0
    imp = max(bodies, key=_vol)
    log.append("bodies after merge %d, volumes %s" % (len(bodies), ["%.3g" % _vol(b) for b in bodies][:5]))
    def _flag(fn):
        try:
            return str(fn())
        except Exception as _x:
            return "n/a (" + str(_x)[:60] + ")"
    _closed = _flag(lambda: imp.Shape.IsClosed)
    _manifold = _flag(lambda: imp.Shape.IsManifold)
    _volume = _flag(lambda: "%.9g" % imp.Shape.Volume)
    _faces = _flag(lambda: imp.Shape.Faces.Count)
    log.append("closed=%s manifold=%s" % (_closed, _manifold))
    nm(imp, "impeller")
    try:
        import clr; clr.AddReference("System.Drawing"); from System.Drawing import Color
        from SpaceClaim.Api.V261.Scripting.Helpers import ColorHelper
        span_hub = 2 * R_TE * TO_M * 0.7
        bl = [f for f in imp.Faces if (f.Shape.GetBoundingBox(Matrix.Identity).MaxCorner -
                                       f.Shape.GetBoundingBox(Matrix.Identity).MinCorner).Magnitude < span_hub]
        ColorHelper.SetColor(FaceSelection.Create(bl), Color.FromArgb(255, 255, 120, 0))
        log.append("orange faces %d" % len(bl))
    except Exception as e:
        log.append("colour FAIL " + str(e)[:80])
    ViewHelper.SetViewMode(InteractionMode.Solid, None)
    ViewHelper.ZoomToEntity()
    result = {"log": " | ".join(log), "n_bodies": str(len(bodies)), "closed": _closed,
              "manifold": _manifold, "volume_m3": _volume, "faces": _faces, "sec": "%.1f" % (time.time() - T0)}
except Exception as _e:
    result = {"error": str(_e)[:800], "trace": _tb.format_exc()[-1500:], "log": " | ".join(log)}
