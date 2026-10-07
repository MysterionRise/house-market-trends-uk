# Methodology

How the UK Liveability Index turns open data into a score for each of England's
33,755 neighbourhoods (LSOAs, 2021 boundaries). The indicator list itself lives in
[`config/indicators.yaml`](../config/indicators.yaml), the presets in
[`config/weights.yaml`](../config/weights.yaml), and the sources in
[data-sources.md](data-sources.md).

## 1. Unit: the LSOA

Lower Layer Super Output Areas have 1,000–3,000 residents (1,600 on average), are
stable between censuses and are the smallest unit most official statistics use.
Scores describe an LSOA as a whole, not any one street or household in it.

## 2. Indicators

Each indicator is built for every LSOA from one or more sources, then given one of
three roles:

- **scored**: counts towards its theme and the overall score;
- **context**: shown to users (and the assistant) but not scored — characteristics
  some people want and others avoid (density, age profile, tenure), or measures that
  duplicate a scored one;
- **diagnostic**: kept for checks and imputation only.

Indicators that measure the same thing share an `overlap_group`; only one per group
may be scored. The build's QA report lists scored indicators that correlate above
ρ = 0.8 within a theme.

### How values are measured

- **Access to places** (GPs, schools, pubs, shops, parks, ...) is measured from every
  residential postcode in the LSOA, not from one central point, and averaged. Distances
  are straight-line in British National Grid metres. Access indices count places within
  a radius, weighting each by a Gaussian decay with distance and capping with
  `log(1 + count) / log(1 + cap)`, so the second café matters more than the twentieth.
- **Gridded data** (Defra's 1km air-quality model) takes the value of the grid cell
  each residential postcode falls in, averaged per LSOA — close to a population-weighted
  mean.
- **Rates** use mid-2022 resident population as the denominator; the claimant rate uses
  residents aged 16–64, and flood risk uses the VOA's count of dwellings.
- **Green space** is measured to the entrances of public parks, gardens and playing
  fields (OS Open Greenspace access points), not their centres: a park is only as close
  as its nearest gate, and a large park with many gates counts for more.
- **Road danger** counts collisions in which someone was killed or seriously injured
  within 500m of homes, averaged over five years.
- **Area-level values** are copied to each LSOA where a source isn't published for
  smaller areas: council tax per billing authority (`broadcast_lad`) and household
  income per MSOA (`broadcast_msoa`).

## 3. From raw value to a 0–100 score

Every indicator is converted to 0–100, higher always better, by one of three methods:

| Method | Used for | How |
|---|---|---|
| `rank` | relative measures with no "good enough" level: crime rates, prices, deprivation | England percentile, ties averaged |
| `scale` | indices already on a bounded scale: access indices (0–1), DfT connectivity (0–100) | mapped linearly to 0–100 |
| `threshold` | distances and pollution | 100 at or better than `good`, 0 at or worse than `bad`, linear between (log scale for distances) |

Percentile-ranking everything was tried first and rejected: it turns trivial
differences (a GP 300m vs 900m away) into large score gaps and put most rural areas in
England's bottom 10%. Thresholds say what "good enough" means: a GP within 1km, a
supermarket within 1km, NO₂ at the WHO guideline of 10 µg/m³.

## 4. Themes and the overall score

- **Theme score**: weighted mean of the theme's scored indicators that the LSOA has.
  If less than half of the theme's weight is available, the theme score is missing.
- **Overall score**: weighted mean of theme scores, using the preset's theme weights.
- **Percentiles** of each theme and of the overall score are reported alongside
  ("better than 72% of England's neighbourhoods"). The consumer view shows a band of
  1–5 (England quintiles) rather than a rank: a "#1 of 33,755" would claim far more
  precision than the data have.
- **Coverage** is the share of the weight that was available; it is shown when below 70%.

### Presets and custom weights

Five presets set starting weights: balanced, family, young professional, retired and
commuter. Users (or the assistant) can change any theme weight, or scale individual
indicators, and the map recolours immediately. The browser recomputes the scores
with the same maths as the pipeline; both are tested against the same golden cases in
[`contracts/fixtures/scoring_golden.json`](../contracts/fixtures/scoring_golden.json).

## 5. Missing and imperfect data

| Problem | Treatment | Flag |
|---|---|---|
| Greater Manchester Police publishes no crime data (since 2019) | Rates for its 1,702 LSOAs are estimated from IoD 2025's crime domain score, using a monotone fit on the rest of England | `imputed` |
| Forces missing months (Gloucestershire stopped reporting in January 2026) | Each force's counts are divided by the months it reported, then annualised | — |
| British Transport Police records crime on the railway | Excluded | — |
| Few house sales | The LSOA median is blended with its MSOA's median, weighted as if the MSOA were 5 extra sales | `low_n` (fewer than 5 sales) |
| GP practices reporting under 1 FTE qualified GP | Left out of the patients-per-GP average; LSOAs with under half their patients at usable practices have no value | `missing` |
| Schools never inspected | Count as average (0.6 on the quality scale) | — |
| Nurseries never inspected | Count as average (0.6), as do school nursery classes, which share their school's grade | — |
| Childminders' addresses are withheld by Ofsted | Only nurseries and pre-schools on non-domestic premises are located | — |
| Flood-risk file includes pseudo-postcodes that aren't in NSPL | Dropped; they hold under 0.1% of the homes at high or medium risk | — |

### School quality across Ofsted's framework changes

Ofsted graded schools 1–4 overall until September 2024, graded only sub-judgements
until November 2025, and has published report cards (five-point grades per area)
since. Each school's latest inspection is put on one 0–1 scale:

- report cards: mean of the area grades (Exceptional 1.0, Strong 0.8, Expected 0.6,
  Needs attention 0.35, Urgent improvement 0.1), capped at 0.2 if safeguarding wasn't met;
- legacy grades: Outstanding 0.95, Good 0.7, Requires improvement 0.4, Inadequate 0.15;
  where the overall grade was "Not judged", the mean of the sub-judgements;
- a later ungraded inspection nudges the result (+0.1 "improved significantly", −0.1
  "concerns");
- the score then fades towards average with a half-life of 6 years, since some
  "Outstanding" grades are over a decade old.

### Well-run pubs

A pub counts when it is mapped in OpenStreetMap as a pub (which excludes nightclubs and
bars) and matches a Food Standards Agency record rated 4 or 5 at an inspection in the
last three years. Matching uses the `fhrs:id` tag OpenStreetMap mappers added to 63% of
pubs, and otherwise the nearest pub, restaurant or hotel within 75m whose name is
similar enough. 18,193 of England's 33,188 mapped pubs qualify. Pubs tagged with real
ale, food, outdoor seating or a microbrewery count up to 30% more. Hygiene ratings say
how well a pub is run, not how good the beer is, hence the name.

## 6. Known limitations

- **Urban bias in access measures.** Every access indicator rises with density, so
  rural areas score lower on health services, schools, transport and amenities. That
  reflects real travel distances, but rural strengths are under-measured: green space
  counts public parks and playing fields, not open countryside or footpaths, and quiet
  isn't measured yet. Compare within the same urban/rural class (an option in analyst
  mode) for like-for-like rankings, as the DfT advises for its connectivity scores.
- **Flood risk** covers rivers and the sea only; surface water flooding, which affects
  more homes, isn't included yet.
- **Crime rates per resident** overstate risk in town centres, where visitors
  outnumber residents.
- **Correlated measures.** Three scored pairs within a theme correlate above ρ = 0.8
  and are kept because they describe different things: income and health deprivation
  (ρ ≈ 0.81), primary and secondary school access (ρ ≈ 0.84), and primary school and
  nursery access (ρ ≈ 0.83), all of which rise with density. The claimant rate tracks
  income deprivation at ρ ≈ 0.89, so it is shown as context rather than scored.
- **Mixed vintages.** Sources range from Census 2021 to data published this month; the
  manifest records each source's version.
- **Ecological fallacy.** An LSOA's score describes the area, not every home in it.
- **Affluence.** Several measures track affluence; the overall score is not a measure
  of whether an area is "nice", and no indicator uses ethnicity, religion or any other
  protected characteristic.
