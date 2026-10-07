# Face-validity review

How well-known places score, against what someone who knows them would expect.
Each place is scored as the neighbourhood (MSOA) its OS Open Names point sits in,
population-weighted, with the default (balanced) weights. Expectations are in
[config/validation_places.yaml](../config/validation_places.yaml); regenerate this
page with `uv run lix qa places`. Checks marked ⚓ also run in `make validate`.

**49 of 49 checks pass** (23 of 23 anchors) across 25 places.

## Scores

| Place | Neighbourhood | Overall | Amenities | Community | Education | Environment | Health | Housing | Safety | Transport |
|---|---|---|---|---|---|---|---|---|---|---|
| Hampstead | Hampstead Town, Camden | 72 | 99 | 88 | 88 | 71 | 86 | 17 | 30 | 99 |
| Shoreditch | Shoreditch, Hackney | 62 | 100 | 44 | 90 | 57 | 71 | 28 | 9 | 96 |
| Whitechapel | Spitalfields, Tower Hamlets | 58 | 100 | 27 | 81 | 53 | 71 | 35 | 8 | 91 |
| Kensington | Kensington Abingdon, Kensington and Chelsea | 70 | 100 | 91 | 96 | 64 | 71 | 18 | 24 | 99 |
| Manchester | Castlefield & Deansgate, Manchester | 67 | 100 | 63 | 58 | 71 | 74 | 57 | 19 | 97 |
| Salford | Weaste & Seedley, Salford | 60 | 63 | 22 | 51 | 75 | 85 | 54 | 31 | 98 |
| Jesmond | South Jesmond & Sandyford, Newcastle upon Tyne | 75 | 99 | 70 | 71 | 87 | 87 | 46 | 43 | 97 |
| Headingley | Headingley, Leeds | 71 | 99 | 62 | 62 | 81 | 87 | 49 | 30 | 100 |
| Harrogate | Central Harrogate, North Yorkshire | 72 | 98 | 67 | 65 | 97 | 79 | 34 | 42 | 97 |
| Winchester | Winchester East, Winchester | 71 | 91 | 42 | 78 | 92 | 93 | 41 | 45 | 87 |
| St Albans | St Albans Central, St Albans | 74 | 100 | 73 | 94 | 88 | 84 | 30 | 29 | 98 |
| Royal Sutton Coldfield | Sutton Coldfield South & Central, Birmingham | 71 | 83 | 62 | 82 | 76 | 82 | 44 | 43 | 98 |
| Cambridge | Central & West Cambridge, Cambridge | 72 | 92 | 95 | 84 | 86 | 85 | 13 | 34 | 85 |
| Chipping Campden | Willersey, Chipping Campden & Blockley, Cotswold | 55 | 34 | 78 | 41 | 82 | 68 | 29 | 60 | 48 |
| Holsworthy | Holsworthy, Bradworthy & Welcombe, Torridge | 50 | 35 | 53 | 23 | 88 | 62 | 34 | 76 | 27 |
| Sidmouth | Sidmouth Town, East Devon | 66 | 81 | 78 | 40 | 88 | 89 | 26 | 71 | 54 |
| Jaywick Sands | Tendring 018A (Jaywick & St Osyth), Tendring | 44 | 38 | 0 | 30 | 64 | 68 | 67 | 21 | 65 |
| Blackpool | North Shore, Blackpool | 59 | 91 | 5 | 29 | 97 | 83 | 59 | 8 | 97 |
| Middlesbrough | Middlesbrough Central, Middlesbrough | 61 | 96 | 8 | 49 | 83 | 82 | 66 | 7 | 95 |
| Burnley | Central Burnley & Daneshouse, Burnley | 58 | 64 | 8 | 41 | 95 | 68 | 60 | 31 | 96 |
| Spalding | Spalding North, South Holland | 68 | 75 | 59 | 63 | 61 | 67 | 76 | 57 | 90 |
| Wisbech | Wisbech South & Peckover, Fenland | 55 | 71 | 25 | 44 | 73 | 68 | 65 | 29 | 67 |
| Milton Keynes | Central Milton Keynes & Newlands, Milton Keynes | 65 | 90 | 29 | 52 | 90 | 77 | 74 | 19 | 90 |
| Clifton | Clifton East, Bristol, City of | 76 | 100 | 90 | 84 | 90 | 86 | 18 | 38 | 100 |
| Bexhill-on-Sea | Bexhill Central, Rother | 64 | 99 | 25 | 55 | 89 | 69 | 50 | 30 | 96 |

## Observations

- **Density no longer piles up points (changed 8 Oct 2026).** Access measures now saturate at a typical suburb's level (fewer cafés, pubs and venues needed for full marks; DfT connectivity full at 75). Middlesbrough Central fell from 62 to 61 and Winchester East rose from 67 to 71, and larger rural areas moved from the 19th to the 34th percentile. Small villages still sit near the bottom (median 3rd–6th percentile): they genuinely lack nearby GPs, shops and buses, which the balanced preset weighs heavily; "compare like with like" ranks them against other villages.
- **Schools are judged by the quality of the nearest, not their number (changed 8 Oct 2026).** Each home gets the quality of its three nearest state schools (Ofsted 60%, results 40%), plus a small "choice" indicator. Education rose in Sidmouth (19 → 40) and Chipping Campden (17 → 41) and fell in Blackpool (63 → 29) and Middlesbrough (80 → 49), where nearby schools are many but weaker.
- **Place points aren't always the part people mean.** OS Open Names puts "Jaywick" in a Clacton West LSOA, not the Jaywick Sands plotlands (England's most deprived LSOA), so a place search shows the neighbourhood around the named point.

## Checks

**Hampstead** (Hampstead Town). Affluent, expensive, well connected. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 30: 16.6 ⚓
- ✅ transport score ≥ 75: 98.6 ⚓
- ✅ overall score ≥ 55: 72.3

**Shoreditch** (Shoreditch). Nightlife hub with high crime per resident and expensive homes. Flags: broadcast_lad, broadcast_msoa.

- ✅ amenities score ≥ 80: 100.0 ⚓
- ✅ safety score ≤ 30: 9.5 ⚓
- ✅ transport score ≥ 85: 96.4

**Whitechapel** (Spitalfields). Dense, central, high income deprivation. Flags: broadcast_lad, broadcast_msoa.

- ✅ transport score ≥ 85: 90.7 ⚓
- ✅ community score ≤ 40: 27.0

**Kensington** (Kensington Abingdon). Among the most expensive places in England. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 25: 17.9 ⚓
- ✅ amenities score ≥ 70: 100.0

**Manchester** (Castlefield & Deansgate). City centre; Greater Manchester crime is estimated (no police.uk data). Flags: broadcast_lad, broadcast_msoa, imputed.

- ✅ flag imputed: crime_asb, crime_burglary, crime_damage_disorder, crime_theft, crime_violence ⚓
- ✅ safety score ≤ 25: 18.6 ⚓
- ✅ transport score ≥ 85: 96.8

**Salford** (Weaste & Seedley). Greater Manchester, so crime is estimated. Flags: broadcast_lad, broadcast_msoa, imputed.

- ✅ flag imputed: crime_asb, crime_burglary, crime_damage_disorder, crime_theft, crime_violence ⚓

**Jesmond** (South Jesmond & Sandyford). Popular inner suburb with bars and restaurants. Flags: broadcast_lad, broadcast_msoa.

- ✅ amenities score ≥ 70: 99.3
- ✅ overall score ≥ 50: 75.0

**Headingley** (Headingley). Student suburb: lively, but high burglary and theft. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ amenities score ≥ 70: 99.4
- ✅ safety score ≤ 45: 29.6

**Harrogate** (Central Harrogate). Affluent spa town. Flags: broadcast_lad, broadcast_msoa.

- ✅ overall score ≥ 55: 72.5 ⚓
- ✅ community score ≥ 60: 67.1

**Winchester** (Winchester East). Affluent cathedral city with strong schools. Flags: broadcast_lad, broadcast_msoa.

- ✅ overall score ≥ 55: 71.1
- ✅ education score ≥ 55: 78.0

**St Albans** (St Albans Central). London commuter city, expensive. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 35: 29.5 ⚓
- ✅ community score ≥ 65: 73.4

**Royal Sutton Coldfield** (Sutton Coldfield South & Central). Affluent suburb of Birmingham. Flags: broadcast_lad, broadcast_msoa.

- ✅ community score ≥ 55: 62.3
- ✅ overall score ≥ 50: 71.4

**Cambridge** (Central & West Cambridge). Expensive university city, cycling and rail. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ housing score ≤ 30: 13.4 ⚓
- ✅ gigabit_broadband ≥ 80: 87.0

**Chipping Campden** (Willersey, Chipping Campden & Blockley). Cotswolds market town: green, remote from rail. Flags: broadcast_lad, broadcast_msoa.

- ✅ transport score ≤ 55: 48.2 ⚓
- ✅ station_distance ≥ 5,000: 5,469.4 ⚓
- ✅ no2 ≤ 8: 3.7

**Holsworthy** (Holsworthy, Bradworthy & Welcombe). Remote north Devon town: no railway, patchy broadband. Flags: broadcast_lad, broadcast_msoa.

- ✅ station_distance ≥ 15,000: 26,214.4 ⚓
- ✅ transport score ≤ 35: 26.8 ⚓
- ✅ gigabit_broadband ≤ 85: 44.7

**Sidmouth** (Sidmouth Town). Seaside retirement town. Flags: broadcast_lad, broadcast_msoa.

- ✅ aged_65_plus ≥ 35: 50.6 ⚓
- ✅ no2 ≤ 8: 3.7

**Jaywick Sands** (Tendring 018A (Jaywick & St Osyth)). Among the most deprived neighbourhoods in England, with cheap homes. Flags: broadcast_lad, broadcast_msoa.

- ✅ community score ≤ 15: 0.2 ⚓
- ✅ housing score ≥ 60: 67.3

**Blackpool** (North Shore). Deprived seaside town centre. Flags: broadcast_lad, broadcast_msoa.

- ✅ community score ≤ 15: 5.4 ⚓
- ✅ housing score ≥ 50: 59.5

**Middlesbrough** (Middlesbrough Central). Post-industrial town centre with high deprivation. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ community score ≤ 20: 8.2 ⚓

**Burnley** (Central Burnley & Daneshouse). Among the cheapest homes in England. Flags: broadcast_lad, broadcast_msoa.

- ✅ house_price ≤ 150,000: 92,826.0 ⚓
- ✅ housing score ≥ 55: 60.3

**Spalding** (Spalding North). Fenland town, much of it at risk from rivers and the sea. Flags: broadcast_lad, broadcast_msoa.

- ✅ flood_risk ≥ 25: 73.9 ⚓

**Wisbech** (Wisbech South & Peckover). Fenland town on the tidal Nene. Flags: broadcast_lad, broadcast_msoa.

- ✅ flood_risk ≥ 10: 30.5

**Milton Keynes** (Central Milton Keynes & Newlands). New town: almost no homes from before 1919. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ period_homes ≤ 5: 0.0 ⚓

**Clifton** (Clifton East). Affluent inner suburb of Bristol, expensive, lots nearby. Flags: broadcast_lad, broadcast_msoa.

- ✅ amenities score ≥ 70: 100.0
- ✅ housing score ≤ 40: 17.9

**Bexhill-on-Sea** (Bexhill Central). Older seaside town. Flags: broadcast_lad, broadcast_msoa.

- ✅ aged_65_plus ≥ 30: 30.5
