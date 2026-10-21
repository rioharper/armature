"""
check — the checks a part definition's "Done when" section asks for,
run against build123d geometry instead of against a human's patience.

Pure library: one submodule per concern, each with its self-tests in a
sibling checks module (`python run_all.py check` runs them). Import the
public names from the package, as part.py does:

    from check import mass_properties, compare_to_target, interference

    mass.py          mass_properties, compare_to_target
    recipe.py        contained, rebuild_sweep — the recipe actually builds
    interference.py  interference, sweep_clearance
    views.py         write_views — the picture
    report.py        report — prints one part's result
    ledger.py        the ledger's numbers, read with the standard library,
                     and the export `set --from-part` writes back

THE UNIT CONTRACT — read this before touching anything in the package.

build123d is millimetre-native: every length you hand it and every number
it hands back is mm. The project's `ledger.toml` is SI: metres, kilograms.
Mixing them silently gives a 1000x length error and a 1e15x inertia error,
both of which look like plausible numbers. So:

  * geometry is built in mm            -> convert ledger values at the boundary
                                          with mm(), never anywhere else
  * everything this package RETURNS is SI (m, kg, kg m^2), because that is
    what the ledger and the derivation are in, and the comparison has to
    happen in the derivation's units — except `about`, which is echoed
    back in the MILLIMETRES it was given in. It is a build123d-side point,
    not a result, and a joint origin passed to it in metres gives a
    parallel-axis shift 1000x too small.

The conversions, derived once so nobody has to re-derive them at 3am:

  volume   mm^3 -> m^3           x 1e-9,  then x rho [kg/m^3] -> kg
  centre   mm   -> m             x 1e-3
  inertia  build123d reports the VOLUMETRIC second moment (density = 1),
           so its units are mm^5. mm^5 -> m^5 is 1e-15, and
           [kg/m^3] * [m^5] = [kg m^2]:      x rho x 1e-15 -> kg m^2

  sanity:  10x20x30 mm aluminium (2700 kg/m^3) -> m = 0.0162 kg,
           Ixx = m/12*(0.02^2+0.03^2) = 1.755e-6 kg m^2, and
           650000 mm^5 * 2700 * 1e-15 = 1.755e-6. Checked in mass_checks.py.
"""

MM_PER_M = 1000.0


def mm(metres: float) -> float:
    """SI length from the ledger -> mm for build123d. The only place a
    factor of 1000 is allowed to appear."""
    return metres * MM_PER_M


# Below mm(): nothing in the package imports it, so the order is free, and
# keeping it first keeps the contract and its one function together.
from check.interference import interference, sweep_clearance  # noqa: E402
from check.mass import compare_to_target, mass_properties  # noqa: E402
from check.recipe import contained, rebuild_sweep  # noqa: E402
from check.report import report  # noqa: E402
from check.views import VIEWS, write_views  # noqa: E402

__all__ = [
    "MM_PER_M", "VIEWS", "compare_to_target", "contained", "interference",
    "mass_properties", "mm", "rebuild_sweep", "report", "sweep_clearance",
    "write_views",
]
