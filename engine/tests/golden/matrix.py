"""The verb matrix (ADR 0008): every golden mechanism against every engine
verb, as data, so a cell cannot fall back to self-consistency unseen.

Each cell ends in one of three states:
- `Known`: a known answer, C (a closed form written in the test) or I (an
  independent computation: an mpmath model, a SciPy minimisation or Hessian,
  a dense grid, or MuJoCo's own world-frame quantities), with the node ids of
  the tests that check it;
- `Covered`: covered elsewhere, naming the known-answer cell that checks the
  same code path, where nothing in that path depends on this mechanism's
  shape;
- `NotApplicable`: the verb has no meaning on the mechanism, and why.

A cell checked only against the engine (S), or only partly (P), is none of
them. `TRAPS` names, for each trap, the tests that show it failing, beside
the verb that catches it, and `FOOTNOTE` the verbs outside the rows. Charted
in #105, ruled in #107, filled by #115 to #118; `test_verb_matrix.py` holds
it to the rule.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Known:
    """A known answer: `code` C or I, `tests` the node ids that check it,
    and `note` what a reader of the cell must know, such as a case that is
    a strict xfail."""
    code: str
    tests: tuple
    note: str = ""


@dataclass(frozen=True)
class Covered:
    """Covered elsewhere: `by` the (mechanism, verb) of the known-answer cell
    on the same code path, and `why` nothing in it depends on this shape.
    `judgement` is set where the ruling was a call, saying when to revisit."""
    by: tuple
    why: str
    judgement: str = ""


@dataclass(frozen=True)
class NotApplicable:
    why: str


@dataclass(frozen=True)
class Trap:
    """A mechanism's trap, and the tests that show it failing, every one of
    them in the cell of the verb that catches it."""
    mechanism: str
    verb: str
    trap: str
    tests: tuple


def _in(module, *names):
    """The node ids of tests `names` in `tests/<module>.py`."""
    return tuple(f"tests/{module}.py::{name}" for name in names)


MECHANISMS = ("arm_2r", "cable_platform", "wheel_leg", "parallelogram",
              "spring_cable", "turret", "five_bar")
"""The golden projects in `golden/`, and the bare five-bar of
`test_fixture_five_bar.py`: not a golden project, but a row since #105, as
the loop the wheel leg stands on, with its own minimal-coordinate model."""

VERBS = {
    "at": "`Compiled.at`: posture, loop closure, Jacobian",
    "inverse": "`State.inverse`",
    "settle": "`State.settle`",
    "wrench": "`State.wrench`",
    "linearise": "`State.linearise`: stiffness, mass and modes",
    "release": "`State.release` and the variants: `reduce` with `lock`, "
               "`couple`, `planar`, `lump` or `rigid`",
    "symbolic": "`symbolic`",
    "equations": "`equations`: M, C q̇ and g, `numeric` and `christoffel`",
    "coarse": "the coarse bodies, `point`, `rod`, `box`, `cylinder`, "
              "`sphere` and `compose`",
    "sample": "`sample` and `sample_states`",
    "search": "`search` over a `Margin`, with `Coordinates`",
    "trace": "`drive.trace` of a mission's moves, holds and follows",
    "event": "`drive.event`, forward-simulated",
    "charge": "`drive.charge`, the bus integrated over a trace",
    "margins": "`drive.margins`, searched",
    "capacitance_needed": "`drive.capacitance_needed`",
    "frames": "`frames`, `render` and `review`",
    "clearance": "`clearance` of a contact",
}

_NO_CONTACT = NotApplicable("it has no contact to clear")
_NO_DRIVE = NotApplicable("it has no actuator and no bus")


def _coarse(shape):
    return Covered(("arm_2r", "coarse"),
                   "a coarse body compiles to a mass and an inertia before "
                   f"any joint reads it, whatever the {shape}")


# --- the 2R arm ----------------------------------------------------------------
_ARM = "test_fixture_2r_arm"

ARM_2R = {
    "at": Known("C", _in(_ARM, "test_pose_and_jacobian_are_the_closed_forms")),
    "inverse": Known("C", _in(
        _ARM, "test_static_torques_are_the_closed_form",
        "test_inverse_is_the_closed_form_at_sampled_states")),
    "settle": Known("C", _in(
        _ARM, "test_settle_holds_the_analytic_static_torque",
        "test_settle_does_not_hold_a_20_percent_wrong_torque",
        "test_settle_holds_a_site_load")),
    "wrench": Known("C", _in(_ARM, "test_elbow_wrench_is_the_closed_form")),
    "linearise": Known("C", _in(
        _ARM, "test_mass_matrix_carries_the_reflected_rotors",
        "test_stiffness_is_the_gravity_torques_derivative",
        "test_hanging_modes_are_the_closed_form")),
    "release": Known("C", _in(
        _ARM, "test_the_variant_inverse_is_the_one_body_arm",
        "test_release_names_the_elbow_and_its_displacement",
        "test_a_true_lock_releases_to_nothing",
        "test_the_locked_elbow_trap_fails_its_release")),
    "symbolic": Known("C", _in(
        _ARM, "test_symbolic_fk_is_the_closed_form",
        "test_symbolic_kinetic_energy_gives_the_closed_form_mass_matrix",
        "test_symbolic_variant_drops_the_locked_coordinate")),
    "equations": Known("C", _in(
        _ARM, "test_equations_are_the_closed_form",
        "test_christoffel_is_the_closed_form",
        "test_numeric_takes_a_band_and_refuses_an_unknown_one")),
    "coarse": Known("C", _in(
        "test_coarse", "test_a_coarse_description_compiles_and_reads_"
                       "symbolically"),
        note="an inline cylinder 2R arm, its mass and COM in closed form"),
    # Re-coded S → C (#107): on an open chain of hinges the answer is the
    # request, the ranges, the seed and the rate limits.
    "sample": Known("C", _in(
        "test_sampler", "test_every_state_lies_inside_its_ranges_and_fills_"
                        "them",
        "test_within_narrows_the_draw",
        "test_the_same_seed_gives_the_same_states",
        "test_sample_states_rates_lie_within_their_limits_in_both_signs")),
    "search": Known("C", _in("test_search", "test_golden_arm_holding_margin")),
    "trace": Known("C", _in(
        "test_drive_mission", "test_a_hold_under_a_tip_load_is_inverse_at_"
                              "rest",
        "test_a_move_by_direction_and_distance_reaches_the_end_it_names",
        "test_a_move_keeps_within_its_limits_at_every_sample")),
    "event": Known("C", _in(
        "test_drive_event", "test_an_estop_stops_the_2r_arm_by_its_closed_"
                            "form_energy")),
    "charge": Covered(("parallelogram", "charge"),
                      "the bus reads only the trace's bus powers, as the "
                      "parallelogram's stop gives them; the 2R e-stop "
                      "checks this arm's own trace"),
    "margins": Known("I", _in(
        "test_drive_margins", "test_the_searched_move_finds_a_direction_a_"
                              "named_move_misses",
        "test_the_worst_case_agrees_with_its_truth_at_1_kHz"),
        note="a brute-force sweep of 72 directions × 5 distances, run "
             "through trace and electrical, never through margins"),
    "capacitance_needed": Covered(("parallelogram", "capacitance_needed"),
                                  "it bisects the bus's peak V over a trace, "
                                  "whatever the trace's mechanism"),
    "frames": Known("I", _in(
        "test_review", "test_frames_list_every_element_of_fixture_1_in_the_"
                       "base_frame"),
        note="against MuJoCo's world frame at qpos0"),
    "clearance": _NO_CONTACT,
}

# --- the cable platform ----------------------------------------------------------
_PLATFORM = "test_fixture_cable_platform"
_ELSEWHERE_ON_A_BUS = (
    "the bus reads only the trace's bus powers; tilt enters only through "
    "the states trace passes, which settle and release check (#107)")

CABLE_PLATFORM = {
    "at": Known("C", _in(
        _PLATFORM, "test_floating_dofs_are_the_point_and_base_axes",
        "test_level_platform_compiles_to_three_slides",
        "test_partial_lock_turns_first_then_the_free_ones")),
    "inverse": Known("I", _in(
        _PLATFORM, "test_floating_need_is_the_potentials_gradient"),
        note="+∇V of the test's own potential, the force that holds the "
             "platform; the force acting on it is −∇V (#115)"),
    "settle": Known("I", _in(
        _PLATFORM, "test_settle_reproduces_the_table",
        "test_settle_is_the_potential_minimum",
        "test_settle_tilts_to_the_answer_at_the_stated_pose",
        "test_braking_along_x_slackens_the_worst_sign_to_the_answer")),
    "wrench": Known("C", _in(
        _PLATFORM, "test_lock_carries_the_residual_moment",
        "test_free_joint_carries_nothing_at_rest")),
    "linearise": Known("I", _in(
        _PLATFORM, "test_hanging_platform_stiffness_and_modes")),
    "release": Known("I", _in(
        _PLATFORM, "test_release_names_the_turns_at_the_edge_midpoint",
        "test_release_splits_the_low_corner_tilt",
        "test_level_platform_assumption_holds")),
    "symbolic": Known("C", _in(
        _PLATFORM, "test_symbolic_level_platform_is_three_slides")),
    "equations": Known("I", _in(
        _PLATFORM, "test_the_level_platform_hangs_on_its_cables_in_the_"
                   "equations"),
        note="on the level variant, three slides: the full free joint's "
             "rates are the angular velocity, the view's the turns' (#163)"),
    "coarse": _coarse("joint above it, floating or hinged"),
    "sample": Known("I", _in(
        "test_sampler", "test_floating_samples_respect_the_envelope",
        "test_floating_orientations_are_unit_quaternions") + _in(
        "test_sampler_map", "test_floating_poses_lie_inside_the_envelope_as_"
                            "unit_quaternions"),
        note="against a swing-twist split written in SciPy"),
    "search": Known("I", _in("test_search", "test_golden_platform_tension_"
                                            "floor"),
                    note="the slackest cable at the test's potential's "
                         "minimum, no longer a pinned number (#115)"),
    "trace": Covered(("cable_platform", "event"),
                     "the winch e-stop traces the move across the room "
                     "before it stops; tilt enters only through the states "
                     "trace passes, which settle and release check (#107)"),
    "event": Known("I", _in(
        "test_drive_event", "test_an_estop_stops_a_cable_robot_on_its_"
                            "shorted_winches",
        "test_a_shorted_cable_goes_slack_and_never_pushes"),
        note="on the level variant, its cables carried by winches through "
             "a seam, against independently computed cable geometry"),
    "charge": Covered(("parallelogram", "charge"), _ELSEWHERE_ON_A_BUS),
    "margins": Covered(("parallelogram", "margins"), _ELSEWHERE_ON_A_BUS),
    "capacitance_needed": Covered(("parallelogram", "capacitance_needed"),
                                  _ELSEWHERE_ON_A_BUS),
    "frames": Known("I", _in(
        "test_review", "test_frames_list_every_element_of_fixture_2_in_the_"
                       "base_frame",
        "test_renders_of_fixture_2_at_home_and_a_sampled_state")),
    "clearance": _NO_CONTACT,
}

# --- the five-bar leg on a wheel -------------------------------------------------
_LEG = "test_fixture_wheel_leg"

WHEEL_LEG = {
    "at": Known("I", _in(_LEG, "test_the_leg_stands_on_its_wheel")),
    "inverse": Known("I", _in(
        _LEG, "test_static_torques_match_virtual_work",
        "test_the_wheel_carries_the_weight",
        "test_the_cone_margin_is_positive_where_the_closed_form_holds",
        "test_the_tyres_traction_at_its_bands_low_corner_is_the_answer",
        "test_without_the_floor_the_torso_has_nothing_to_stand_on")),
    "settle": Known("I", _in(_LEG, "test_settle_under_the_static_torques_"
                                   "stays"),
                    note="held at the mpmath virtual-work torques, not "
                         "inverse's"),
    "wrench": Known("I", _in(_LEG, "test_wrench_across_the_hub_is_the_hub_"
                                   "torque")),
    "linearise": Covered(
        ("five_bar", "linearise"),
        "the loop's modes are checked on the bare five-bar, and contact's "
        "discarded solver roots on the incline wheel "
        "(test_contact.py::test_linearise_keeps_the_rocking_mode_and_lists_"
        "the_solver_roots); an answer for both together needs a "
        "minimal-coordinate rolling-contact model nobody has",
        judgement="revisit if Ibex needs modes"),
    "release": Covered(("five_bar", "release"),
                       "a lock in a loop is the bare five-bar's, and "
                       "`planar` is checked on test_planar.py's floating "
                       "biped"),
    "symbolic": Covered(("five_bar", "symbolic"),
                        "the symbolic view has no contact; the loop's "
                        "closure is the bare five-bar's"),
    "equations": Known("I", _in(
        _LEG, "test_the_equations_carry_the_pin_loop_and_the_tyre_with_tau",
        "test_the_equations_are_mujocos_on_the_loop",
        "test_the_christoffel_matrix_gives_mujocos_velocity_products"),
        note="the tyre is rigid, so its force sits with τ and the loop's; a "
             "compliant contact is refused "
             "(test_contact.py::test_equations_refuse_a_compliant_contact_"
             "and_carry_a_rigid_one)"),
    "coarse": _coarse("loop or contact"),
    "sample": Known("I", _in(
        _LEG, "test_resting_on_the_tyre_matches_the_closed_form_lift",
        "test_sampling_finds_the_skid_away_from_alpha_zero")),
    "search": Known("I", _in(
        _LEG, "test_searching_the_hips_finds_the_skid_away_from_alpha_zero",
        "test_the_same_margin_at_alpha_zero_alone_passes"),
        note="Coordinates with rest_on; the answer is skid_clearance's "
             "least over a dense mpmath grid, refined once"),
    "trace": Known("I", _in(
        _LEG, "test_the_holds_energy_is_its_copper_loss_through_the_driver"),
        note="the hold's torques are the mpmath static_torque, read back "
             "as R·i²·t"),
    "event": Known("C", _in(
        "test_drive_event", "test_an_event_with_a_resting_contact_reports_"
                            "it"),
        note="the tyre's normal against the carried weight; the holding "
             "torques are inverse's, which this row's inverse checks"),
    "charge": Known("I", _in(
        _LEG, "test_the_holds_energy_is_its_copper_loss_through_the_driver"),
        note="the source's energy, R·i²·t/η, i the mpmath static torque "
             "over Kt"),
    "margins": Known("I", _in(
        _LEG, "test_the_holds_peak_current_is_the_largest_static_torque"),
        note="each hip motor matches the grid's largest static torque "
             "over Kt, on the A = 1 face (#126)"),
    "capacitance_needed": Covered(("parallelogram", "capacitance_needed"),
                                  "a hold never regenerates, so the bus "
                                  "never rises for it to size"),
    "frames": Known("I", _in(
        "test_review", "test_frames_list_each_contact_against_mujocos_"
                       "geoms"),
        note="against MuJoCo's own geoms at qpos0"),
    "clearance": Known("C", _in(
        _LEG, "test_the_skid_is_missed_at_alpha_zero_alone",
        "test_the_skids_worst_clearance_is_the_answer")),
}

# --- the balanced parallelogram --------------------------------------------------
_PARALLELOGRAM = "test_fixture_parallelogram"

PARALLELOGRAM = {
    "at": Known("C", _in(
        _PARALLELOGRAM, "test_the_parallelogram_closes",
        "test_the_parallelogram_holds_its_branch_up_to_the_singularity")),
    "inverse": Known("C", _in(
        _PARALLELOGRAM, "test_gravity_torque_is_zero_over_the_envelope",
        "test_a_wrong_counterweight_reads_its_closed_form",
        "test_a_wrong_counterweight_fails_the_balance")),
    "settle": Known("C", _in(
        _PARALLELOGRAM, "test_released_with_the_motors_off_it_stays",
        "test_released_with_a_wrong_counterweight_it_falls")),
    "wrench": Known("C", _in(_PARALLELOGRAM, "test_the_pin_load_is_its_"
                                             "closed_form")),
    "linearise": Known("C", _in(
        _PARALLELOGRAM, "test_balanced_it_has_no_gravity_stiffness_anywhere",
        "test_a_wrong_counterweight_stiffens_j1_by_its_closed_form")),
    "release": Covered(("five_bar", "release"),
                       "a lock in a loop of hinges is the bare five-bar's, "
                       "and a lock on an open chain the 2R arm's"),
    "symbolic": Covered(("five_bar", "symbolic"),
                        "a loop of hinges closes symbolically as the bare "
                        "five-bar's does"),
    "equations": Known("I", _in(_PARALLELOGRAM,
                                "test_the_equations_are_mujocos")),
    "coarse": _coarse("chain or loop"),
    "sample": Covered(("five_bar", "sample"),
                      "a loop of hinges is sampled as the bare five-bar's "
                      "is, its dependent angles closed by the same solve"),
    "search": Known("C", _in(
        _PARALLELOGRAM,
        "test_the_searched_pin_margin_is_worst_nearest_the_singularity",
        "test_the_pin_margin_checked_at_home_passes"),
        note="the pin's wrench margin over J1 ∈ [−0.3, 0.3] and the crank "
             "φ ∈ [1.0, 2.0], read as J2 = φ − π/2 (#117)"),
    "trace": Known("C", _in(_PARALLELOGRAM, "test_the_stops_torques_are_the_"
                                            "closed_form")),
    "event": Known("C", _in(
        _PARALLELOGRAM, "test_the_stop_forward_simulated_holds_phi_and_"
                        "lifts_the_bus")),
    "charge": Known("C", _in(
        _PARALLELOGRAM, "test_the_stop_lifts_the_bus_by_the_energy_"
                        "relation"),
        note="V = √(V₀² + 2E/C), E from golden.answers' mpmath stop"),
    "margins": Known("C", _in(
        _PARALLELOGRAM, "test_the_stop_trips_a_source_that_cannot_sink_and_"
                        "not_one_that_can")),
    "capacitance_needed": Known("C", _in(
        _PARALLELOGRAM, "test_the_capacitance_the_stop_needs_is_the_closed_"
                        "form"),
        note="C = 2E/(V_trip² − V₀²)"),
    "frames": Covered(("arm_2r", "frames"),
                      "the frames table and the renders read bodies, "
                      "joints and sites at home, whatever closes them"),
    "clearance": _NO_CONTACT,
}

# --- the mass on a spring and on a cable -----------------------------------------
_SPRING = "test_fixture_spring_cable"

SPRING_CABLE = {
    "at": Known("C", _in("test_rigid", "test_at_holds_it_at_its_rest_"
                                       "length")),
    "inverse": Known("C", _in(_SPRING, "test_inverse_needs_the_weight_less_"
                                       "the_cables_pull"),
                     note="on the elastic cable: m·g − k·stretch"),
    "settle": Known("C", _in(
        _SPRING, "test_at_rest_the_cable_carries_the_weight_and_the_slide_"
                 "nothing") + _in(
        "test_rigid", "test_rigid_cable_releases_with_the_sag_the_elastic_"
                      "one_shows")),
    "wrench": Known("C", _in(
        _SPRING, "test_at_rest_the_spring_carries_the_weight_in_its_slide",
        "test_at_rest_the_cable_carries_the_weight_and_the_slide_nothing"),
        note="m·g at rest is read on the test-side spring control, whose "
             "slide carries it; on the golden cable the slide carries 0 "
             "and the cable's tension is m·g (#115)"),
    "linearise": Known("C", _in(
        _SPRING, "test_spring_reads_its_stiffness",
        "test_taut_cable_reads_its_stiffness", "test_slack_cable_reads_zero",
        "test_a_bias_only_linearisation_reads_zero",
        "test_the_bias_only_trap_reads_the_cables_stiffness",
        "test_the_linearised_swing_read_as_specific_force_is_the_imu_peak")),
    "release": Known("C", _in(
        "test_rigid", "test_rigid_cable_releases_with_the_sag_the_elastic_"
                      "one_shows")),
    "symbolic": Known("C", _in(
        "test_rigid", "test_the_symbolic_closure_is_the_length_less_the_"
                      "rest")),
    "equations": Known("C", _in(
        _SPRING, "test_the_equations_hang_the_bob_on_the_taut_cable",
        "test_the_equations_carry_a_slides_spring"),
        note="the cable taut: its slack deadband is not symbolic"),
    "coarse": _coarse("slide"),
    "sample": Covered(("arm_2r", "sample"),
                      "on one free slide the answer is the request, as on "
                      "the 2R arm's open chain"),
    "search": Known("C", _in("test_search", "test_golden_cable_frequency_"
                                            "margin"),
                    note="worst at k_low, f = √(k_low/m)/2π"),
    "trace": _NO_DRIVE,
    "event": _NO_DRIVE,
    "charge": _NO_DRIVE,
    "margins": _NO_DRIVE,
    "capacitance_needed": _NO_DRIVE,
    "frames": Covered(("cable_platform", "frames"),
                      "a cable's ends are listed in the base frame as the "
                      "platform's four are"),
    "clearance": _NO_CONTACT,
}

# --- the geared turret -----------------------------------------------------------
_TURRET = "test_fixture_turret"
_ONE_HINGE = ("on one hinge off the world, as the 2R arm's shoulder is, "
              "nothing in it depends on the payload's offset")

TURRET = {
    "at": Known("C", _in(_TURRET, "test_the_muzzles_pose_and_jacobian_are_"
                                  "the_closed_forms")),
    "inverse": Known("C", _in(_TURRET, "test_the_pans_torque_is_its_inertia_"
                                       "and_its_rotors"),
                     note="(J_load/N + N·J_m)·q̈ at the motor; the vertical "
                          "axis carries no gravity torque"),
    "settle": Known("C", _in(_TURRET, "test_released_with_the_motor_off_it_"
                                      "stays")),
    "wrench": Known("C", _in(
        _TURRET, "test_the_bearings_wrench_is_the_closed_form",
        "test_the_bearings_peak_moment_in_the_slew_is_the_answer",
        "test_the_bearing_checked_on_its_weight_alone_passes_a_slew_it_fails",
        "test_the_weight_only_trap_holds_the_bearings_moment"),
        note="the weight and its moment m·g·d at rest, the COM's "
             "acceleration moving, the slew's peak over the bearing's "
             "rating; the last is a strict xfail: the trap's own check, "
             "which must fail"),
    "linearise": Known("C", _in(_TURRET, "test_the_pans_mass_is_the_load_and_"
                                         "the_reflected_rotor")),
    "release": Covered(("arm_2r", "release"),
                       "a lock or a reduction " + _ONE_HINGE),
    "symbolic": Covered(("arm_2r", "symbolic"), "the symbolic view " +
                        _ONE_HINGE),
    "equations": Known("I", _in(_TURRET, "test_the_equations_are_mujocos"),
                       note="the reflected rotor is the derivation's to add"),
    "coarse": _coarse("hinge"),
    "sample": Covered(("arm_2r", "sample"),
                      "on one hinge the answer is the request, as on the 2R "
                      "arm's open chain"),
    "search": Covered(("arm_2r", "search"),
                      "a margin over Coordinates reads states, whatever the "
                      "chain; the slew's own answer is read off its "
                      "trace"),
    "trace": Known("C", _in(
        _TURRET, "test_the_slews_peak_torque_is_the_closed_form",
        "test_the_trace_keeps_the_rotors_share_apart"),
        note="(J_load/N + N·J_m)·a at the slew's acceleration limit"),
    "event": Covered(("arm_2r", "event"),
                     "an e-stop " + _ONE_HINGE),
    "charge": Covered(("parallelogram", "charge"),
                      "the bus reads only the trace's bus powers, and the "
                      "turret has no drive of its own"),
    "margins": Covered(("parallelogram", "margins"),
                       "a margin searches what trace and charge give, and "
                       "the trace's torque is checked here"),
    "capacitance_needed": Covered(("parallelogram", "capacitance_needed"),
                                  "it bisects the bus's peak V over a "
                                  "trace, whatever the trace's mechanism"),
    "frames": Covered(("arm_2r", "frames"),
                      "the frames table and the renders read bodies, "
                      "joints and sites at home, whatever the chain"),
    "clearance": _NO_CONTACT,
}

# --- the bare five-bar -----------------------------------------------------------
_FIVE_BAR = "test_fixture_five_bar"

FIVE_BAR = {
    "at": Known("I", _in(
        _FIVE_BAR, "test_at_closes_the_loop_on_home_branch",
        "test_dependent_rates_keep_the_loop_closed")),
    "inverse": Known("I", _in(
        _FIVE_BAR, "test_static_torques_match_virtual_work",
        "test_dynamic_torques_match_lagrange",
        "test_mj_inverse_answers_for_the_solver_not_the_mechanism")),
    "settle": Known("I", _in(_FIVE_BAR, "test_settle_under_the_static_"
                                        "torques_stays"),
                    note="held at the mpmath virtual-work torques, not "
                         "inverse's (#116)"),
    "wrench": Known("I", _in(_FIVE_BAR, "test_wrench_counts_the_loop_"
                                        "force")),
    "linearise": Known("I", _in(
        _FIVE_BAR, "test_modes_are_on_the_manifold_and_match_minimal_"
                   "coordinates")),
    "release": Known("I", _in(
        _FIVE_BAR, "test_the_locked_variant_inverse_is_the_four_bar",
        "test_release_settles_where_the_five_bar_balances"),
        note="motor B read as E, the second motor's joint: locking E "
             "leaves a four-bar on motor A, its answer the five-bar's "
             "mpmath model with E held (#116)"),
    "symbolic": Known("I", _in(
        _FIVE_BAR, "test_symbolic_closure_vanishes_on_the_reference_loop")),
    "equations": Known("I", _in(_FIVE_BAR, "test_the_equations_are_mujocos")),
    "coarse": _coarse("loop"),
    "sample": Known("I", _in(
        "test_sampler", "test_loop_closed_states_close_and_match_the_"
                        "closed_form",
        "test_closed_chain_rates_keep_the_loop_closed")),
    "search": Known("C", _in(
        "test_search", "test_five_bar_pin_clearance_is_the_feasible_worst_"
                       "over_pi")),
    "trace": Known("I", _in(
        "test_drive_mission", "test_a_five_bar_moves_by_its_lagrange_"
                              "torques")),
    "event": Known("I", _in(
        "test_drive_event", "test_an_estop_stops_the_five_bar_by_its_"
                            "mpmath_energy")),
    "charge": Covered(("parallelogram", "charge"),
                      "the bus reads only the trace's bus powers; the "
                      "five-bar's e-stop checks its own trace"),
    "margins": Covered(("parallelogram", "margins"),
                       "a margin searches what trace and charge give, and "
                       "the parallelogram's runs through a loop"),
    "capacitance_needed": Covered(("parallelogram", "capacitance_needed"),
                                  "it bisects the bus's peak V over a "
                                  "trace, whatever the trace's mechanism"),
    "frames": Covered(("arm_2r", "frames"),
                      "the frames table and the renders read bodies, "
                      "joints and sites at home; a loop adds only its gap "
                      "there, which the at cell closes"),
    "clearance": _NO_CONTACT,
}

MATRIX = {"arm_2r": ARM_2R, "cable_platform": CABLE_PLATFORM,
          "wheel_leg": WHEEL_LEG, "parallelogram": PARALLELOGRAM,
          "spring_cable": SPRING_CABLE, "turret": TURRET,
          "five_bar": FIVE_BAR}

TRAPS = (
    Trap("arm_2r", "release", "a locked elbow",
         _in(_ARM, "test_the_locked_elbow_trap_fails_its_release")),
    Trap("cable_platform", "release",
         "the platform stays level (the level variant's locked turns)",
         _in(_PLATFORM, "test_level_platform_assumption_holds")),
    Trap("cable_platform", "settle",
         "the braking load checked at one sign only, not the sign that "
         "slackens the cables",
         _in(_PLATFORM, "test_braking_along_x_slackens_the_worst_sign_to_the_"
                        "answer")),
    Trap("wheel_leg", "search", "first contact checked at α = 0 only",
         _in(_LEG, "test_the_same_margin_at_alpha_zero_alone_passes")),
    Trap("wheel_leg", "inverse",
         "the five-bar's statics without the contact row",
         _in(_LEG, "test_without_the_floor_the_torso_has_nothing_to_stand_"
                   "on")),
    Trap("wheel_leg", "inverse",
         "the tyre's traction read at its nominal μ, not its band's low "
         "corner",
         _in(_LEG, "test_the_tyres_traction_at_its_bands_low_corner_is_the_"
                   "answer")),
    Trap("parallelogram", "margins",
         "regeneration into a PSU that cannot sink current",
         _in(_PARALLELOGRAM, "test_the_stop_trips_a_source_that_cannot_sink_"
                             "and_not_one_that_can")),
    Trap("parallelogram", "search",
         "the coupler pin's load checked at home, far from θ1 = φ",
         _in(_PARALLELOGRAM, "test_the_pin_margin_checked_at_home_passes")),
    Trap("parallelogram", "inverse", "a wrong counterweight",
         _in(_PARALLELOGRAM, "test_a_wrong_counterweight_fails_the_balance")),
    Trap("spring_cable", "linearise",
         "the stiffness read from qfrc_bias alone, about 0 N/m",
         _in(_SPRING, "test_a_bias_only_linearisation_reads_zero",
             "test_the_bias_only_trap_reads_the_cables_stiffness")),
    Trap("spring_cable", "linearise",
         "the accelerometer read as the bob's acceleration, not its specific "
         "force",
         _in(_SPRING, "test_the_linearised_swing_read_as_specific_force_is_"
                      "the_imu_peak")),
    Trap("spring_cable", "release",
         "the cable is inextensible (the rigid reduction)",
         _in("test_rigid", "test_rigid_cable_releases_with_the_sag_the_"
                           "elastic_one_shows")),
    Trap("turret", "wrench",
         "the bearing checked on its axial load alone, the weight's moment "
         "and the slew's left out",
         _in(_TURRET, "test_the_bearing_checked_on_its_weight_alone_passes_"
                      "a_slew_it_fails",
             "test_the_weight_only_trap_holds_the_bearings_moment")),
    Trap("five_bar", "inverse",
         "mj_inverse, which answers for the solver's soft constraint",
         _in(_FIVE_BAR,
             "test_mj_inverse_answers_for_the_solver_not_the_mechanism")),
)

FOOTNOTE = {
    **{f"drive.{verb}": "takes drive data alone, never a mechanism; checked "
                        "in test_drive_electrical.py and test_drive_thermal.py"
       for verb in ("check", "electrical", "envelope", "heat", "repeat",
                    "rms_torque", "kt_from_kv")},
    **{verb: "takes a trace or names, never the mechanism's shape (#107)"
       for verb in ("account", "drive.energy", "drive.review")},
}
"""The engine verbs outside the rows, and why."""
