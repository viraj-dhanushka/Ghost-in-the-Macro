# Measured line-up

Written by `scripts/lineup.py` from real Faithful runs against the Referee. Do not edit by hand.

## discount (seed 20261204, LibreOffice 26.8.3.1 861effc5289d539f15c4c18d1ba8579ffd78728b)

| Suspect | Exit | Result |
|---|---|---|
| `dropped_branch.py` | 1 | difference found (targeted boundary case, not shrunk) at delivery_distance_km=12, quantity=50, unit_price=19.95: Referee 1077.3, suspect 1084.26 (seed 20261204). |
| `float_rounding.py` | 1 | difference found (shrunk) at delivery_distance_km=0, quantity=3565, unit_price=0.01: Referee 38.5, suspect 38.51 (seed 20261204). |
| `gt_slip.py` | 1 | difference found (targeted boundary case, not shrunk) at delivery_distance_km=12, quantity=50, unit_price=19.95: Referee 1077.3, suspect 1197.0 (seed 20261204). |
| `honest.py` | 0 | no difference found on 308 cases (seed 20261204). |

## haunted (seed 20261204, LibreOffice 26.8.3.1 861effc5289d539f15c4c18d1ba8579ffd78728b)

| Suspect | Exit | Result |
|---|---|---|
| `dropped_branch.py` | 1 | difference found (targeted boundary case, not shrunk) at delivery_distance_km=12, quantity=51, unit_price=19.95: Referee 1098.84, suspect 1105.8 (seed 20261204). |
| `float_rounding.py` | 1 | difference found (shrunk) at delivery_distance_km=0, quantity=3565, unit_price=0.01: Referee 38.5, suspect 38.51 (seed 20261204). |
| `honest.py` | 0 | no difference found on 311 cases (seed 20261204). |
| `tidied.py` | 1 | difference found (targeted boundary case, not shrunk) at delivery_distance_km=12, quantity=50, unit_price=19.95: Referee 1084.26, suspect 1077.3 (seed 20261204). |

