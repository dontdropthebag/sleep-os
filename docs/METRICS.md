# Metric definitions

Every metric is labelled with a **measurement kind**:

| Kind | Meaning |
|---|---|
| `measured` | Directly measured by a sensor (e.g. record start/end times) |
| `device_estimated` | Derived by device firmware (sleep stages, snore minutes, "Hours") |
| `self_reported` | Entered by the user (ratings, habits, check-ins) |
| `system_derived` | Computed by this app from the above (efficiency, debt, regularity) |
| `experimental` | Predictions; lowest trust tier |

and a **confidence label**: high / moderate / low / insufficient data. Estimated metrics are
never presented as clinical measurements. Missing inputs yield missing outputs — never
imputed values.

## Duration

- **Total sleep time (TST):** device-estimated sleep minutes. For Sleep as Android this is
  the `Hours` field (tracked duration) **minus detected awake time**, because `Hours` alone
  does not subtract awakenings; capped at time in bed. Nights with no awake events show
  TST = tracked duration (efficiency 100% then means "no awakenings detected", not
  perfect sleep).
- **Time in bed (TIB):** final wake − in-bed time.
- **Rolling averages:** mean of last 7/14/28 non-null nights; requires ≥ half the window.
- **Workday vs free-day:** by profile workdays; each needs ≥ 3 nights.
- **Nap-adjusted daily sleep:** main TST + same-date nap TST.

## Sleep efficiency

`TST ÷ TIB × 100`, capped at 100 %. (Deep-sleep percentage is *never* called
"deep-sleep efficiency".)

## Architecture (stages)

From device-estimated stage intervals only: minutes and % of TST per stage, transition
count. Always labelled device-estimated; a single low deep-sleep night is explicitly not
treated as a problem (weekly trends are prioritised).

## Continuity

- Latency (only if the source records it — Sleep as Android does not),
- WASO = sum of awake intervals, awakenings count, average/longest awakening,
- Fragmentation index = awakenings per hour of sleep,
- Sleep-maintenance efficiency = TST ÷ (TST + WASO) × 100.

## Regularity

Circular statistics on local wall-clock minutes (so 23:50 vs 00:10 is a 20-minute spread):
SD of onset, wake, midpoint; mean times; workday-vs-free-day midpoint difference =
**social jetlag** (needs ≥ 3 nights of each). Needs ≥ 5 nights.
*Sleep Regularity Index (minute-level) is planned once minute-level sleep/wake data
is available.*

## Sleep need & debt

- **< 28 valid nights:** need = user preference clamped to the 7–9 h evidence range,
  confidence low.
- **≥ 28 nights:** need = median TST on nights where morning energy ≥ 7 and daytime
  sleepiness ≤ 4, excluding illness/travel/> 2 alcohol units (needs ≥ 5 such nights).
- **Rolling debt (7/14 nights):** Σ max(0, need − TST). Surplus offsets at most **half** of
  the accumulated debt — one long night does not clear chronic restriction.

## Chronotype

Categories: earlier / intermediate / later / insufficient data / schedule-constrained.
Method: median free-day sleep midpoint, corrected for workday sleep debt (MSFsc-style).
Cut-offs: corrected midpoint < 03:30 → earlier; > 05:30 → later.
Exclusions: travel, illness, ≥ 3 alcohol units, implausible durations (< 2 h or > 16 h),
low data-quality nights, alarm-constrained free days (wake within 15 min of required wake).
Needs ≥ 14 usable nights (≥ 28 + ≥ 8 free nights for high confidence). This estimates
behavioural preference; it does **not** measure circadian phase, melatonin or cortisol.

## Tonight's recommendation

`lights-out = required wake − target sleep − expected latency` where latency = median of
the last 14 recorded latencies (default 15 min). Adjustments: +min(45, debt/4) for > 1 h
debt, +20 min high training load, +30 min illness. The recommended shift from the median
recent bedtime is capped at **45 min/night**; larger changes are staged gradually with
morning-light guidance.

## Physiological baselines

Per (source, method) group — never blended across methods: 7/28/60-day medians + median
absolute deviation. Deviation flag uses robust z = (x − median28) / (1.4826 × MAD);
|z| > 1.5 → "notably low/high". Low HRV is context, not a verdict — always read alongside
sleep, alcohol, illness, training and travel.

## Data-quality score (0–100)

Weighted components: source reliability, core timing present, duration present, stage data,
HR/HRV coverage, timezone certainty, plausibility (TIB 1–18 h, TST ≤ TIB), manual edits,
cross-source agreement. Labels: ≥ 75 high, ≥ 55 moderate, else low. The score rates the
**data**, not the sleep.
