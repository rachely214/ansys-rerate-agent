# Re-rate Request (synthetic)

From: Plant Engineering, Customer Site
To: Aftermarket Engineering
Subject: Re-rate request, Unit C-101 compressor stage

Hi team,

Our site load is growing and we need more flow from Unit C-101 without replacing the casing, driver, or foundation. We also get occasional surge trips near our normal operating line and want more margin. The next planned outage is in 9 months.

Please tell us whether a re-rate is feasible inside the existing casing, and give us your recommended option with predicted performance.

Attached: original datasheet, casing limits, current performance curve, current impeller geometry.

Thanks,
Plant Engineering

---

## New duty (at 100% speed)

For this demo, the "existing" column uses NASA's measured values (taken at a suppressed 11 psia inlet) as the baseline, and targets are stated on the same basis.

| Requirement | Existing (measured) | Re-rate target |
|---|---|---|
| Inlet corrected mass flow | 10.85 lbm/s | 11.5 lbm/s (+6%) |
| Total pressure ratio | 4.68 | 4.60 minimum |
| Adiabatic efficiency (total-to-total) | 0.822 | 0.82 minimum (no worse than today) |
| Stability (surge) margin, NASA definition | 7.5% | 10% minimum |
| Shaft power | ~961 kW (calculated, see note) | No more than +6% over existing (driver limit) |
| Rotational speed | 21,789 rpm | Unchanged |

Power note: calculated from measured flow, pressure ratio, and efficiency at standard day inlet with ideal-gas air properties. At the target point (11.5 lbm/s, PR 4.60, efficiency 0.82) the calculation gives about +4.8%. If efficiency falls below about 0.81, the driver limit is exceeded. Efficiency is therefore a hard constraint, not a nice-to-have.

## Mechanical acceptance criteria (synthetic)

| Check | Criterion |
|---|---|
| Impeller stress at 105% speed (centrifugal plus aero pressure loads) | Peak stress below material allowable with safety factor of at least 1.5 |
| Running tip clearance at 100% speed | At least 0.008 in everywhere (cold clearance 0.012 in) |
| Blade vibration (Campbell diagram) | No impeller blade natural frequency within 10% of the 20-per-rev diffuser vane passing excitation (20E, about 7,263 Hz at 100% speed) across 90 to 105% speed |
| Material | Same as existing impeller |

## Deliverables requested

1. Baseline check first: simulate the existing machine and compare against the measured data, so we know how far the simulation is from reality before trusting any new design.
2. Feasibility verdict: can the target be met inside the existing casing?
3. Three distinct candidate designs with different tradeoffs (for example: conservative, balanced, aggressive), with predicted performance vs. targets, compared against the simulated baseline on identical settings. Pause here for our selection.
4. Full stress, clearance, and vibration results for the option we select.
5. Risks and what needs human review before release to manufacturing.
