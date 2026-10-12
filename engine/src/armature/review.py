"""The Milestone 0 review artifact: what the red team checks a description
against the spec's sketch with.

A description error is common-mode (ADR 0003): the derivation and the truth
model both read it, so no truth check can see it. The artifact puts it in
front of a reader instead:

- a frames table, every joint axis and point, COM, mass, inertia, site and
  cable end, in the base frame at home, exactly as the description wrote
  them (one section per element kind, so a new kind is one more row
  function in `SECTIONS`);
- skeleton renders at home and at given states: inertia boxes, joint axes,
  each body's COM, cables, and any contact the model has, as PNG.

Rendering is offscreen through MuJoCo's default GL backend; writing PNG
needs Pillow.
"""

import copy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import mujoco
import numpy as np

from .compiler import compile
from .description import describe

RENDER_SIZE = (800, 600)   # px, width × height
VIEW = (150.0, -25.0)      # azimuth and elevation, degrees: MuJoCo's camera
                           # convention; the base frame is drawn in each view
MARK = 0.06                # the decor's size, as a fraction of the model's extent
COM_RGBA = (1.0, 0.8, 0.0, 1.0)  # yellow: no other decor is


@dataclass(frozen=True)
class Frames:
    """The frames table: `sections` maps each section's title to its rows,
    each a mapping of column to value, in the order the description wrote
    them. Every position, axis and inertia is in the base frame at home, the
    numbers the description wrote; an inertia is about its COM, listed as
    (xx, yy, zz, xy, xz, yz)."""
    sections: MappingProxyType

    def row(self, section, name):
        """The row named `name` in `section`."""
        for r in self.sections[section]:
            if r["name"] == name:
                return r
        raise KeyError(f"no {name!r} in {section!r}")

    def markdown(self):
        """The table as Markdown, one table per section."""
        out = ["# Frames at home, in the base frame", ""]
        for title, rows in self.sections.items():
            columns = list(rows[0])
            out += [f"## {title}", "",
                    "| " + " | ".join(columns) + " |",
                    "|" + "---|" * len(columns)]
            out += ["| " + " | ".join(_fmt(r[c]) for c in columns) + " |"
                    for r in rows]
            out.append("")
        return "\n".join(out)


@dataclass(frozen=True)
class Review:
    """What `review` wrote: the frames table's path, and each render's path
    keyed by its state's label ("home" first)."""
    frames: Path
    renders: MappingProxyType


def frames(mechanism, params):
    """The frames table of `mechanism(params)` (or a variant, whose
    reductions get a section of their own), validated first."""
    d = describe(mechanism, params)
    sections = {}
    for title, attribute, row in SECTIONS:
        rows = tuple(row(e, d) for e in getattr(d, attribute, ()))
        if rows:
            sections[title] = rows
    sections["Gravity"] = ({"name": "gravity", "vector": _v(d.gravity)},)
    if params:
        sections["Parameters"] = tuple({"name": k, "value": _n(params[k])}
                                       for k in params)
    if d.reductions:
        sections["Reductions"] = tuple(
            {"name": str(r), "assumption": r.assumption} for r in d.reductions)
    return Frames(MappingProxyType({
        title: tuple(MappingProxyType(r) for r in rows)
        for title, rows in sections.items()}))


def render(state, path, *, size=RENDER_SIZE, view=VIEW):
    """Draw `state`'s skeleton offscreen and save it as a PNG at `path`.

    Shown: each body's equivalent inertia box (the uniform box with its mass
    and inertia) and its COM as a yellow ball, labelled by body; each joint's
    axis as an arrow; sites; cables; contact points and forces where the
    model has contacts; and the base frame's axes (x red, y green, z blue).
    `view` is (azimuth, elevation) in degrees. Returns the path."""
    try:
        from PIL import Image
    except ImportError:
        raise ImportError("writing a render as PNG needs Pillow: "
                          "`uv add pillow`") from None
    width, height = size
    model = copy.deepcopy(state.compiled.model)  # the compiled one stays as is
    model.vis.global_.offwidth = max(model.vis.global_.offwidth, width)
    model.vis.global_.offheight = max(model.vis.global_.offheight, height)
    mark = MARK * model.stat.extent
    model.stat.meansize = mark  # joint arrows and the base frame scale with it
    model.vis.scale.jointlength = model.vis.scale.framelength = 3.0
    model.vis.scale.jointwidth = model.vis.scale.framewidth = 0.15
    model.vis.rgba.inertia[3] = 0.3  # see the COMs and axes inside the boxes
    model.site_size[:, 0] = 0.15 * mark
    model.tendon_width[:] = 0.05 * mark
    data = state._data()  # its posture, with every loop closed

    option = mujoco.MjvOption()
    for flag in ("mjVIS_INERTIA", "mjVIS_JOINT", "mjVIS_TENDON",
                 "mjVIS_CONTACTPOINT", "mjVIS_CONTACTFORCE"):
        option.flags[getattr(mujoco.mjtVisFlag, flag)] = True
    option.flags[mujoco.mjtVisFlag.mjVIS_COM] = False  # the subtree's; ours below
    option.frame = mujoco.mjtFrame.mjFRAME_WORLD
    option.label = mujoco.mjtLabel.mjLABEL_BODY
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = model.stat.center
    camera.distance = 2.0 * model.stat.extent
    camera.azimuth, camera.elevation = view

    with mujoco.Renderer(model, height, width) as renderer:
        renderer.update_scene(data, camera=camera, scene_option=option)
        scene = renderer.scene
        for b in range(1, model.nbody):  # each body's own COM
            if scene.ngeom >= scene.maxgeom:
                break
            mujoco.mjv_initGeom(scene.geoms[scene.ngeom],
                                mujoco.mjtGeom.mjGEOM_SPHERE,
                                np.array([0.3 * mark, 0, 0]), data.xipos[b],
                                np.eye(3).ravel(), np.array(COM_RGBA))
            scene.geoms[scene.ngeom].emission = 0.6
            scene.ngeom += 1
        pixels = renderer.render()
    path = Path(path)
    Image.fromarray(pixels).save(path)
    return path


def review(mechanism, params, directory, states=None):
    """Write the Milestone 0 review artifact into `directory`: `frames.md`,
    and a render per state, `home.png` first, then `<label>.png` for each
    `states` entry, a label mapped to the independent coordinates `at()`
    takes. Returns a `Review`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    table = directory / "frames.md"
    table.write_text(frames(mechanism, params).markdown(), encoding="utf-8")
    m = compile(mechanism, params)
    renders = {"home": render(m.at(), directory / "home.png")}
    for label, q in (states or {}).items():
        renders[label] = render(m.at(q=q), directory / f"{label}.png")
    return Review(table, MappingProxyType(renders))


# --- the sections, one per element kind ------------------------------------------
def _body(b, d):
    i = b.inertia
    return {"name": b.name, "mass": _n(b.mass), "COM": _v(b.com),
            "inertia (xx, yy, zz, xy, xz, yz)": tuple(
                _n(i[r][c]) for r, c in ((0, 0), (1, 1), (2, 2), (0, 1),
                                         (0, 2), (1, 2)))}


def _joint(j, d):
    return {"name": j.name, "kind": j.kind, "parent": j.parent,
            "child": j.child, "axis": None if j.axis is None else _v(j.axis),
            "point": _v(j.point),
            "range": None if j.range is None else tuple(map(_n, j.range)),
            "home": None if j.kind == "free" else _n(j.home),
            "stiffness": None if j.stiffness is None else _n(j.stiffness),
            "rest": (None if j.stiffness is None
                     else _n(j.home if j.rest is None else j.rest))}


def _site(s, d):
    return {"name": s.name, "body": s.body, "position": _v(s.pos)}


def _cable(c, d):
    (on_a, a), (on_b, b) = c.start, c.end
    span = _length(a, b)
    return {"name": c.name, "start body": on_a, "start": _v(a),
            "end body": on_b, "end": _v(b), "EA": _n(c.ea),
            "rest length": _n(c.rest_length), "length at home": span}


def _loop(loop, d):
    at = {s.name: s.pos for s in d.sites}
    return {"name": loop.name, "a": loop.a, "b": loop.b,
            "gap at home": _length(at[loop.a], at[loop.b])}


def _actuator(a, d):
    reflected = (None if _n(a.gear) is None or _n(a.rotor_inertia) is None
                 else _n(a.gear) ** 2 * _n(a.rotor_inertia))
    return {"name": a.name, "joint": a.joint, "gear": _n(a.gear),
            "rotor inertia": _n(a.rotor_inertia), "reflected N²J": reflected,
            "torque limit": None if a.torque_limit is None
            else _n(a.torque_limit)}


def _contact(c, d):
    def described(s):
        sizes = {"sphere": (s.radius,), "cylinder": (s.radius, s.half_length),
                 "box": tuple(s.half_sizes or ()), "plane": ()}.get(s.kind, ())
        return {"kind": s.kind, "pos": _v(s.pos),
                "axis": None if s.axis is None else _v(s.axis),
                "size": tuple(_n(v) for v in sizes)}
    shape, against = described(c.shape), described(c.against)
    return {"name": c.name, "body": c.body, "shape": shape["kind"],
            "at": shape["pos"], "axis": shape["axis"], "size": shape["size"],
            "against": against["kind"], "against at": against["pos"],
            "against axis": against["axis"], "against size": against["size"],
            "mu": _n(c.mu),
            "stiffness": None if c.stiffness is None else _n(c.stiffness),
            "damping": None if c.damping is None else _n(c.damping)}


SECTIONS = (  # (title, the Description's attribute, its row from (element, d))
    ("Bodies", "bodies", _body),
    ("Joints", "joints", _joint),
    ("Sites", "sites", _site),
    ("Cables", "cables", _cable),
    ("Loops", "loops", _loop),
    ("Actuators", "actuators", _actuator),
    ("Contacts", "contacts", _contact),
)


def _n(value):
    """A number as a float; a symbol as itself."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _v(vector):
    return tuple(_n(x) for x in vector)


def _length(a, b):
    try:
        return float(np.linalg.norm(np.array(a, float) - np.array(b, float)))
    except TypeError:
        return None


def _fmt(value):
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)):
        return "(" + ", ".join(_fmt(v) for v in value) + ")"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
