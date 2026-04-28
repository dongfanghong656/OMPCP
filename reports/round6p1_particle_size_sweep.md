# Round 6p1 Particle Size Sweep

Status: `complete`
Recommended next action: `use_sweep_as_axial_spectral_smoke_not_lateral_truth`
Mode: `low_na_separable_baseline`
Diameter range (nm): `[200.0, 1000.0]`
Cases: `9` ok / `0` failed

Scope note:
For mode=low_na, this sweep is an axial spectral/Mie smoke harness: the lateral profile is still the Gaussian system surrogate, so it must not be used as evidence that particle scattering leaves lateral PSF shape unchanged.

| diameter_nm | status | fwhm_opd_um | peak_opd_um | centroid_opd_um | main_to_sidelobe_rejection_db | peakline_x_um |
| --- | --- | --- | --- | --- | --- | --- |
| 200.0 | ok | 5.71276255084965 | -0.14999999999999858 | -0.14807736657426496 | 26.569541749481267 | 0.0 |
| 300.0 | ok | 5.3484653696529865 | -1.9499999999999993 | -2.035519376178719 | 25.05121686894921 | 0.0 |
| 400.0 | ok | 5.744031098771046 | -0.7999999999999972 | -0.7534040868901684 | 25.574020595718963 | 0.0 |
| 500.0 | ok | 5.729953673168945 | -1.0500000000000007 | -1.0746370422139504 | 25.90216152923564 | 0.0 |
| 600.0 | ok | 5.834225834048289 | -2.1499999999999986 | -2.2176605444314137 | 23.774955098973724 | 0.0 |
| 700.0 | ok | 6.0293715093218 | -1.8499999999999979 | -1.9087614240220525 | 21.383952011382632 | 0.0 |
| 800.0 | ok | 5.097588381337543 | -1.8999999999999986 | -1.7616344801050279 | 22.863842123715308 | 0.0 |
| 900.0 | ok | 5.8876689170000525 | -2.099999999999998 | -2.184261043312596 | 23.110619565097743 | 0.0 |
| 1000.0 | ok | 6.102072655063177 | -3.1499999999999986 | -3.317398613423421 | 21.105100928383006 | 0.0 |
