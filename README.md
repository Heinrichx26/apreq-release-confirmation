# Information deadlines and the value of release-time confirmations

Code, derived inputs and saved results for the study of departure release-time
confirmations under the Approval Request/Call for Release (APREQ/CFR) procedure.
The tower chooses which future two-minute intervals to confirm with the en route
center and how many aircraft push back in each interval, when answers are delayed,
can contain errors and are limited in number.

All optimization uses open-source software. The direct scenario mixed-integer
program is solved by HiGHS through `scipy.optimize.milp`.

## Data sources

- United States: departures at ATL, CLT and DFW, January-March 2025, derived from
  the MrAirspace ADS-B flight archive (ODbL-1.0). Attribution and source links are in
  `data/independent_adsb_q1/source_manifest.json`.
- Zurich (LSZH): off-block and runway-entry events, 7 October - 5 December 2024,
  from the EUROCONTROL Open Performance Data Initiative (https://www.opdi.aero/).
  `src/opdi_trb/build_events.py` pairs the events from the published flight list and
  flight-event files; the derived pairs are in `data/opdi_trb/processed/`.

## Layout

- `src/trb_error_20261030/`: exact request recursion with delayed answers and a shared error allowance.
- `src/trb_external_error_20261030/`: finite-calendar comparisons with lookahead policies at ATL, CLT and DFW.
- `src/trb_transfer_20261030/`: date-separated calibration of service ranges.
- `src/trb_information_transfer_20261030/`: confirmations on later dates.
- `src/trb_calibrated_20261030/scenario_mip.py`: direct scenario MIP (HiGHS).
- `src/opdi_trb/`: Zurich event pairing, Zurich experiments, travel-time sensitivity and the MIP comparison.
- `src/trb_theory_20261126/`: information-deadline check, value of confirmations (exact recursion, two-step lookahead, range index rule), exhaustive checks of the interval-range results, inexact answers, returns to request number and the adaptive-value instance, and the answer-time and request-number chart.
- `src/figures/`: figures drawn from saved results only.
- `data/`: derived inputs; `results/`: saved outputs.

## Reproduction

Run from the repository root with Python 3.11 and `pip install -r requirements.txt`.

```
python src/opdi_trb/zurich_experiment.py chrono smoke
python src/opdi_trb/zurich_experiment.py chrono full
python src/opdi_trb/zurich_experiment.py finite full
python src/opdi_trb/mip_public.py full
cd src/opdi_trb && python us_travel.py full
python src/trb_theory_20261126/deadline_check.py
python src/trb_theory_20261126/verify_interval_theorem.py
python src/trb_theory_20261126/check_structure.py
python src/trb_theory_20261126/interval_schedule.py smoke
python src/trb_theory_20261126/interval_schedule.py full
python src/trb_theory_20261126/summarize_value_capture.py
python src/trb_theory_20261126/design_chart.py smoke
python src/trb_theory_20261126/design_chart.py full
python src/trb_theory_20261126/summarize_design_chart.py
python src/figures/plot_apreq_evidence.py
python src/figures/plot_value_theory.py
python src/figures/plot_design_chart.py
```

Each experiment has a short test stage on a small subset before the full stage.
Plotting scripts read saved results and do not rerun experiments.
