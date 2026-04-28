# Round 6p1 Lateral Slice Axis Crosscheck

Status: `consistent`
Recommended next action: `coefficient_debug_generalizes_across_slice_axes`

## mild_shape_medium_tilt
Small deformation with medium tilt. This is where bridge and asymptotic should start to separate.

### axis = x

| Family | field_relative_l2 | intensity_relative_l2 | peakline_x_delta_um_vs_bridge |
|---|---:|---:|---:|
| R0 | 0.172288 | 0.60337 | 2 |
| R0_plus_R2 | 0.00146966 | 0.00248865 | 4 |
| R0_plus_R1_plus_R2 | 0.000236691 | 0.000727276 | 0 |

axis requires odd basis: `True`; odd basis resolves axis: `True`; `R0+R1+R2` beats `R0+R2`: `True`; coefficient focus: `D1_dominant`.

### axis = y

| Family | field_relative_l2 | intensity_relative_l2 | peakline_x_delta_um_vs_bridge |
|---|---:|---:|---:|
| R0 | 0.200851 | 0.302617 | 0 |
| R0_plus_R2 | 0.00367493 | 0.00312404 | 0 |
| R0_plus_R1_plus_R2 | 0.00367493 | 0.00312404 | 0 |

axis requires odd basis: `False`; odd basis resolves axis: `False`; `R0+R1+R2` beats `R0+R2`: `False`; coefficient focus: `D1_dominant`.
