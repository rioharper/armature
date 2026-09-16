"""
report_truth.py — what a note or a reviewer needs printed about the truth model.

    python analysis/model/report_truth.py

The MJCF is the truth model in full: a reviewer reading a truth check reads
this to see what it was checked *against*, without running anything. The
sampled configurations are the ones the checks actually visited, printed so a
surprising result can be reproduced at the posture that produced it.
"""

import numpy as np

# The chain builder's model. A floating mechanism keeps the other builder, so
# this reads `from truth.floating import mjcf, spec_from_params` and prints
# `mjcf(spec_from_params())`.
from truth.chain import mjcf
from truth.envelope import DEFAULT_SEED, DEFAULT_SAMPLES, sample

print("The truth model (MJCF)\n")
print(mjcf())

print(f"\nThe envelope sample: n = {DEFAULT_SAMPLES}, seed = {DEFAULT_SEED}\n")
for row in sample():
    print("  ", np.round(row, 4))
