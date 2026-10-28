"""Write a minimal Ansys Engineering Data (MatML) XML from a plain material file with public properties.

Material files in this repository are small YAML files with cited public data (density, Young's modulus,
Poisson's ratio, tensile yield/ultimate). Mechanical imports Engineering Data XML, so the structural stage
generates the XML at run time with this module. The XML layout follows the public MatML 3.1 schema as used by
Ansys Engineering Data; no content is copied from Ansys libraries.
"""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import yaml

_PROPS = [  # (property id, property name, [(param id, param name, units xml, yaml key)])
    ("pr0", "Density", [("pa0", "Density",
                         '<Units name="Density"><Unit><Name>kg</Name></Unit><Unit power="-3"><Name>m</Name></Unit></Units>',
                         "density_kg_m3")]),
    ("pr1", "Elasticity", [("pa1", "Young's Modulus", '<Units name="Stress"><Unit><Name>Pa</Name></Unit></Units>',
                            "youngs_modulus_pa"),
                           ("pa2", "Poisson's Ratio", "<Unitless />", "poisson_ratio")]),
    ("pr2", "Tensile Yield Strength", [("pa3", "Tensile Yield Strength",
                                        '<Units name="Stress"><Unit><Name>Pa</Name></Unit></Units>',
                                        "tensile_yield_pa")]),
    ("pr3", "Tensile Ultimate Strength", [("pa4", "Tensile Ultimate Strength",
                                           '<Units name="Stress"><Unit><Name>Pa</Name></Unit></Units>',
                                           "tensile_ultimate_pa")]),
]
REQUIRED = ["name", "density_kg_m3", "youngs_modulus_pa", "poisson_ratio", "tensile_yield_pa"]


def load(path: Path) -> dict:
    d = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise ValueError(f"material file {path} is missing {missing}")
    # YAML 1.1 reads exponent forms like 113.8e9 as strings; convert every numeric property explicitly
    for k in ("density_kg_m3", "youngs_modulus_pa", "poisson_ratio", "tensile_yield_pa", "tensile_ultimate_pa"):
        if k in d:
            d[k] = float(d[k])
    return d


def to_matml(d: dict) -> str:
    body, meta = [], []
    for pid, pname, params in _PROPS:
        vals = [(a, n, u, d.get(k)) for a, n, u, k in params]
        if all(v is None for *_, v in vals):
            continue
        qual = '<Qualifier name="Behavior">Isotropic</Qualifier>' if pid == "pr1" else ""
        if pid == "pr1":
            qual += "<Qualifier name=\"Derive from\">Young's Modulus and Poisson's Ratio</Qualifier>"
        pv = "".join(f'<ParameterValue parameter="{a}" format="float"><Data>{float(v)!r}</Data>'
                     f'<Qualifier name="Variable Type">Dependent</Qualifier></ParameterValue>'
                     for a, _, _, v in vals if v is not None)
        body.append(f'<PropertyData property="{pid}"><Data format="string">-</Data>{qual}{pv}</PropertyData>')
        meta.append(f"<PropertyDetails id=\"{pid}\"><Unitless /><Name>{escape(pname)}</Name></PropertyDetails>")
        meta += [f'<ParameterDetails id="{a}"><Name>{escape(n)}</Name>{u}</ParameterDetails>' for a, n, u, _ in vals]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<EngineeringData version="19.4.0.79">\n<Notes>'
            + escape(str(d.get("description", ""))) + '</Notes>\n<Materials><MatML_Doc><Material><BulkDetails>'
            + f"<Name>{escape(str(d['name']))}</Name>" + "".join(body)
            + "</BulkDetails></Material><Metadata>" + "".join(meta)
            + "</Metadata></MatML_Doc></Materials>\n</EngineeringData>\n")


def props_from_xml(xml_path: Path) -> dict:
    """Read density (kg/m3) and tensile yield (Pa) from an Engineering Data XML (first material), by parameter
    name, using the file's own Metadata ids. Returns {} if not found."""
    import xml.etree.ElementTree as ET
    root = ET.parse(str(xml_path)).getroot()
    names = {pd.get("id"): (pd.findtext("Name") or "") for pd in root.iter("ParameterDetails")}
    out = {}
    for pv in root.iter("ParameterValue"):
        nm = names.get(pv.get("parameter"), "")
        data = pv.findtext("Data")
        try:
            v = float(data)
        except (TypeError, ValueError):
            continue
        if nm == "Density" and "density_kg_m3" not in out:
            out["density_kg_m3"] = v
        elif nm == "Tensile Yield Strength" and "tensile_yield_pa" not in out:
            out["tensile_yield_pa"] = v
    return out


def ensure_xml(material_file: Path, out_dir: Path) -> tuple[Path, dict]:
    """Return an Engineering Data XML for material_file. XML files are used as-is; YAML files are converted."""
    material_file = Path(material_file)
    if material_file.suffix.lower() == ".xml":
        return material_file, {}
    d = load(material_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (material_file.stem + ".xml")
    out.write_text(to_matml(d), encoding="utf-8")
    return out, d
