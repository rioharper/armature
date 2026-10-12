"""The Milestone 0 review artifact: the frames table lists every element of
fixtures 1 and 2 in the base frame at home, checked against MuJoCo's own
world-frame quantities at qpos0 (which reach the base frame through the
compiler's body-local frames, not through the table); and the renders of
fixture 2 are PNGs with a skeleton in them."""

import numpy as np
import mujoco
import pytest
from PIL import Image
from scipy.spatial.transform import Rotation

import armature
from test_fixture_2r_arm import PARAMS as ARM_PARAMS
from test_fixture_2r_arm import RIGID_ELBOW, arm
from test_fixture_cable_platform import HOME, LEVEL, params, platform
from test_fixture_five_bar import PARAMS as FIVE_BAR_PARAMS
from test_fixture_five_bar import five_bar

SEED = 20261011
PLATFORM_PARAMS = params(HOME, 2.0)


def _home(m):
    """MuJoCo's own world-frame kinematics at qpos0, the home posture."""
    data = mujoco.MjData(m.model)
    mujoco.mj_forward(m.model, data)
    return data


def _names(table, section):
    return [r["name"] for r in table.sections[section]]


def _assert_bodies_and_sites(table, m, data):
    model = m.model
    for b in m.description.bodies:
        row, i = table.row("Bodies", b.name), model.body(b.name).id
        assert row["mass"] == pytest.approx(model.body_mass[i], rel=1e-12)
        assert row["COM"] == pytest.approx(data.xipos[i], abs=1e-12)
        turn = data.ximat[i].reshape(3, 3)
        tensor = turn @ np.diag(model.body_inertia[i]) @ turn.T
        assert row["inertia (xx, yy, zz, xy, xz, yz)"] == pytest.approx(
            [tensor[0, 0], tensor[1, 1], tensor[2, 2], tensor[0, 1],
             tensor[0, 2], tensor[1, 2]], abs=1e-12)
    for s in m.description.sites:
        assert table.row("Sites", s.name)["position"] == pytest.approx(
            data.site(s.name).xpos, abs=1e-12)


def test_frames_list_every_element_of_fixture_1_in_the_base_frame():
    m = armature.compile(arm, ARM_PARAMS)
    table, data = armature.frames(arm, ARM_PARAMS), _home(m)
    assert _names(table, "Bodies") == ["upper", "fore"]
    assert _names(table, "Joints") == ["shoulder", "elbow"]
    assert _names(table, "Sites") == ["tip"]
    assert _names(table, "Actuators") == ["shoulder_motor", "elbow_motor"]
    assert _names(table, "Parameters") == list(ARM_PARAMS)
    assert table.row("Gravity", "gravity")["vector"] == (0, -9.81, 0)
    _assert_bodies_and_sites(table, m, data)
    for name in ("shoulder", "elbow"):
        row, j = table.row("Joints", name), m.model.joint(name).id
        assert row["axis"] == pytest.approx(data.xaxis[j], abs=1e-12)
        assert row["point"] == pytest.approx(data.xanchor[j], abs=1e-12)
    for name in ("shoulder_motor", "elbow_motor"):
        row = table.row("Actuators", name)
        dof = m.model.jnt_dofadr[m.model.joint(row["joint"]).id]
        assert row["gear"] == m.model.actuator(name).gear[0]
        assert row["reflected N²J"] == pytest.approx(m.model.dof_armature[dof],
                                                     rel=1e-12)


def test_frames_list_every_element_of_fixture_2_in_the_base_frame():
    m = armature.compile(platform, PLATFORM_PARAMS)
    table, data = armature.frames(platform, PLATFORM_PARAMS), _home(m)
    assert _names(table, "Bodies") == ["platform"]
    assert _names(table, "Joints") == ["hang"]
    assert _names(table, "Sites") == ["centre"]
    assert _names(table, "Cables") == ["c1", "c2", "c3", "c4"]
    hang = table.row("Joints", "hang")
    assert hang["kind"] == "free" and hang["axis"] is None
    assert hang["point"] == pytest.approx(HOME)
    _assert_bodies_and_sites(table, m, data)
    for i, name in enumerate(_names(table, "Cables")):
        row = table.row("Cables", name)
        assert row["start body"] == "world" and row["end body"] == "platform"
        assert row["start"] == pytest.approx(data.site(f"{name}:start").xpos,
                                             abs=1e-12)
        assert row["end"] == pytest.approx(data.site(f"{name}:end").xpos,
                                           abs=1e-12)
        assert row["length at home"] == pytest.approx(data.ten_length[i],
                                                      rel=1e-12)
        assert row["rest length"] == PLATFORM_PARAMS[f"l0_{i + 1}"]


def tilted_block(p):
    """A box on turned axes, so every product of inertia is nonzero in base
    axes, on a hinge through one corner."""
    turn = Rotation.from_euler("zyx", [0.7, -0.4, 1.1]).as_matrix()
    return [armature.box("block", center=(0.2, 0.1, -0.3),
                         size=(0.3, 0.2, 0.1), mass=p["m"], axes=turn),
            armature.joint("swing", "hinge", parent="world", child="block",
                           axis=(0, 1, 0), point=(0, 0, 0), range=(-1, 1))]


def test_frames_list_products_of_inertia_in_base_axes():
    m = armature.compile(tilted_block, {"m": 2.0})
    table = armature.frames(tilted_block, {"m": 2.0})
    products = table.row("Bodies", "block")["inertia (xx, yy, zz, xy, xz, yz)"][3:]
    assert min(abs(v) for v in products) > 1e-4
    _assert_bodies_and_sites(table, m, _home(m))


def test_a_variant_lists_its_reductions():
    table = armature.frames(LEVEL, PLATFORM_PARAMS)
    assert [r["assumption"] for r in table.sections["Reductions"]] == ["A5"] * 3
    assert "Reductions" not in armature.frames(platform,
                                               PLATFORM_PARAMS).sections
    elbow = armature.frames(RIGID_ELBOW, ARM_PARAMS).sections["Reductions"]
    assert "lock 'elbow'" in elbow[0]["name"]


def test_a_loop_lists_its_gap_at_home():
    table = armature.frames(five_bar, FIVE_BAR_PARAMS)
    for row in table.sections["Loops"]:
        assert row["gap at home"] <= 1e-12


def test_the_markdown_carries_every_element():
    text = armature.frames(platform, PLATFORM_PARAMS).markdown()
    for heading in ("## Bodies", "## Joints", "## Sites", "## Cables",
                    "## Gravity", "## Parameters"):
        assert heading in text
    for name in ("platform", "hang", "centre", "c1", "c4", "l0_3"):
        assert f"| {name} |" in text
    assert "| (2, 2, 1.2) |" in text  # the free joint's point, at 6 digits
    assert "| — |" in text            # and its axis, which it has none of


def test_frames_read_symbols_too():
    import sympy as sp
    symbols = {k: sp.Symbol(k, real=True) for k in ARM_PARAMS}
    row = armature.frames(arm, symbols).row("Joints", "elbow")
    assert row["point"] == (symbols["l1"], 0.0, 0.0)


# --- renders ---------------------------------------------------------------------
def _sampled(seed=SEED):
    rng = np.random.default_rng(seed)
    point = HOME + rng.uniform(-0.6, 0.6, 3)
    return point, Rotation.from_rotvec(rng.uniform(-0.4, 0.4, 3)).as_matrix()


def _pixels(path):
    return np.asarray(Image.open(path).convert("RGB"))


def _assert_not_blank(image):
    background = image[0, 0]
    drawn = np.any(np.abs(image.astype(int) - background) > 40, axis=2)
    assert drawn.mean() > 0.002, f"only {drawn.mean():.2%} of pixels drawn"
    assert len(np.unique(image.reshape(-1, 3), axis=0)) > 20


def test_renders_of_fixture_2_at_home_and_a_sampled_state(tmp_path):
    out = armature.review(platform, PLATFORM_PARAMS, tmp_path / "m0",
                          states={"sampled": {"hang": _sampled()}})
    assert list(out.renders) == ["home", "sampled"]
    assert out.frames.read_text(encoding="utf-8").startswith("# Frames")
    images = {}
    for label, path in out.renders.items():
        assert path.suffix == ".png" and path.exists()
        with Image.open(path) as png:
            assert png.format == "PNG"
        images[label] = _pixels(path)
        assert images[label].shape == (600, 800, 3)
        _assert_not_blank(images[label])
    moved = np.any(images["home"] != images["sampled"], axis=2).mean()
    assert moved > 0.001


def test_a_render_leaves_the_compiled_model_as_it_was(tmp_path):
    m = armature.compile(platform, PLATFORM_PARAMS)
    before = (m.model.vis.global_.offwidth, m.model.stat.meansize,
              m.model.site_size.copy(), m.model.tendon_width.copy())
    armature.render(m.at(), tmp_path / "home.png", size=(1024, 768))
    assert _pixels(tmp_path / "home.png").shape == (768, 1024, 3)
    after = (m.model.vis.global_.offwidth, m.model.stat.meansize,
             m.model.site_size, m.model.tendon_width)
    assert before[:2] == after[:2]
    assert np.array_equal(before[2], after[2])
    assert np.array_equal(before[3], after[3])


def _share(image, test):
    r, g, b = (image[..., k].astype(int) for k in range(3))
    return test(r, g, b).mean()


def test_a_render_draws_inertia_boxes_coms_and_joint_axes(tmp_path):
    """The five-bar's links have isotropic inertia, so their equivalent boxes
    are cubes that fill the view in translucent red; each body's COM is the
    only yellow in a render."""
    m = armature.compile(five_bar, FIVE_BAR_PARAMS)
    image = _pixels(armature.render(m.at(), tmp_path / "home.png"))
    assert _share(image, lambda r, g, b: (r > 40) & (r > 2 * g)
                  & (r > 2 * b)) > 0.2
    arm_image = _pixels(armature.render(armature.compile(arm, ARM_PARAMS).at(),
                                        tmp_path / "arm.png"))
    for img in (image, arm_image):
        assert _share(img, lambda r, g, b: (r > 150) & (g > 110)
                      & (b < 0.4 * g)) > 1e-4
    # the joint arrows are MuJoCo's teal, unlike the base frame's pure blue
    assert _share(arm_image, lambda r, g, b: (b > 80) & (g > 0.5 * b)
                  & (r < 0.5 * b)) > 1e-4


def test_a_closed_chain_renders_at_its_closed_posture(tmp_path):
    m = armature.compile(five_bar, FIVE_BAR_PARAMS)
    q = {name: 0.2 for name in m.independent}
    home = _pixels(armature.render(m.at(), tmp_path / "home.png"))
    moved = _pixels(armature.render(m.at(q=q), tmp_path / "moved.png"))
    _assert_not_blank(moved)
    assert np.any(home != moved)


def test_frames_list_each_contact_against_mujocos_geoms():
    """Each contact's shape and the shape it is against, in the base frame
    at home, read back from MuJoCo's own geoms at qpos0."""
    from test_fixture_wheel_leg import PARAMS as LEG_PARAMS
    from test_fixture_wheel_leg import wheel_leg
    table = armature.frames(wheel_leg, LEG_PARAMS)
    data = _home(m := armature.compile(wheel_leg, LEG_PARAMS))
    row = table.row("Contacts", "tyre")
    assert (row["body"], row["shape"], row["against"]) == (
        "wheel", "cylinder", "plane")
    assert row["size"] == (LEG_PARAMS["r"], LEG_PARAMS["w"])
    assert row["mu"] == LEG_PARAMS["mu"] and row["stiffness"] is None
    for at, axis, geom in (("at", "axis", "tyre"),
                           ("against at", "against axis", "tyre:against")):
        g = m.model.geom(geom).id
        assert row[at] == pytest.approx(data.geom_xpos[g], abs=1e-12)
        assert row[axis] == pytest.approx(
            data.geom_xmat[g].reshape(3, 3)[:, 2], abs=1e-12)
    assert "## Contacts" in table.markdown()
