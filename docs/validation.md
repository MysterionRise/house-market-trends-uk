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
| Hampstead | Hampstead Town, Camden | 73 | 98 | 88 | 95 | 71 | 90 | 17 | 30 | 94 |
| Shoreditch | Shoreditch, Hackney | 63 | 100 | 44 | 99 | 57 | 71 | 28 | 9 | 95 |
| Whitechapel | Spitalfields, Tower Hamlets | 61 | 100 | 27 | 100 | 53 | 71 | 35 | 8 | 90 |
| Kensington | Kensington Abingdon, Kensington and Chelsea | 70 | 100 | 91 | 100 | 64 | 71 | 18 | 24 | 95 |
| Manchester | Castlefield & Deansgate, Manchester | 70 | 100 | 63 | 89 | 71 | 72 | 57 | 19 | 90 |
| Salford | Weaste & Seedley, Salford | 61 | 50 | 22 | 84 | 75 | 87 | 54 | 31 | 87 |
| Jesmond | South Jesmond & Sandyford, Newcastle upon Tyne | 76 | 96 | 70 | 89 | 87 | 89 | 46 | 43 | 87 |
| Headingley | Headingley, Leeds | 73 | 92 | 62 | 90 | 81 | 88 | 49 | 30 | 89 |
| Harrogate | Central Harrogate, North Yorkshire | 72 | 93 | 67 | 76 | 97 | 80 | 34 | 42 | 86 |
| Winchester | Winchester East, Winchester | 66 | 82 | 42 | 58 | 92 | 95 | 41 | 45 | 76 |
| St Albans | St Albans Central, St Albans | 74 | 99 | 73 | 99 | 88 | 87 | 30 | 29 | 90 |
| Royal Sutton Coldfield | Sutton Coldfield South & Central, Birmingham | 69 | 71 | 62 | 80 | 76 | 85 | 44 | 43 | 88 |
| Cambridge | Central & West Cambridge, Cambridge | 69 | 88 | 95 | 72 | 86 | 88 | 13 | 34 | 75 |
| Chipping Campden | Willersey, Chipping Campden & Blockley, Cotswold | 50 | 20 | 78 | 17 | 82 | 67 | 29 | 60 | 43 |
| Holsworthy | Holsworthy, Bradworthy & Welcombe, Torridge | 47 | 25 | 53 | 16 | 88 | 60 | 34 | 76 | 23 |
| Sidmouth | Sidmouth Town, East Devon | 61 | 64 | 78 | 19 | 88 | 93 | 26 | 71 | 45 |
| Jaywick Sands | Tendring 018A (Jaywick & St Osyth), Tendring | 42 | 29 | 0 | 17 | 64 | 81 | 67 | 21 | 57 |
| Blackpool | North Shore, Blackpool | 60 | 78 | 5 | 63 | 97 | 87 | 59 | 8 | 85 |
| Middlesbrough | Middlesbrough Central, Middlesbrough | 62 | 81 | 8 | 80 | 83 | 85 | 66 | 7 | 85 |
| Burnley | Central Burnley & Daneshouse, Burnley | 59 | 51 | 8 | 75 | 95 | 69 | 60 | 31 | 84 |
| Spalding | Spalding North, South Holland | 66 | 65 | 59 | 63 | 61 | 66 | 76 | 57 | 79 |
| Wisbech | Wisbech South & Peckover, Fenland | 54 | 58 | 25 | 55 | 73 | 67 | 65 | 29 | 56 |
| Milton Keynes | Central Milton Keynes & Newlands, Milton Keynes | 66 | 79 | 29 | 76 | 90 | 79 | 74 | 19 | 78 |
| Clifton | Clifton East, Bristol, City of | 76 | 100 | 90 | 91 | 90 | 90 | 18 | 38 | 92 |
| Bexhill-on-Sea | Bexhill Central, Rother | 64 | 96 | 25 | 57 | 89 | 78 | 50 | 30 | 84 |

## Observations

- **Density dominates the default overall score.** Theme scores behave as expected, but deprived town centres (Middlesbrough Central 62, Blackpool North Shore 60) end up close to affluent towns (Winchester East 66, Sidmouth 61), because five of the eight themes measure access to places, which rises with density. Options: rank within the same urban/rural class by default, let access measures saturate sooner, or give community and safety more weight in the balanced preset.
- **School access counts good schools nearby rather than the quality of the nearest.** Rural towns score 16–19 on education (Chipping Campden, Holsworthy, Sidmouth) even where the local primary is good. A measure based on the quality of the nearest two or three schools would treat rural families more fairly.
- **Place points aren't always the part people mean.** OS Open Names puts "Jaywick" in a Clacton West LSOA, not the Jaywick Sands plotlands (England's most deprived LSOA), so a place search shows the neighbourhood around the named point.

## Checks

**Hampstead** (Hampstead Town). Affluent, expensive, well connected. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 30: 16.6 ⚓
- ✅ transport score ≥ 75: 93.8 ⚓
- ✅ overall score ≥ 55: 72.8

**Shoreditch** (Shoreditch). Nightlife hub with high crime per resident and expensive homes. Flags: broadcast_lad, broadcast_msoa.

- ✅ amenities score ≥ 80: 100.0 ⚓
- ✅ safety score ≤ 30: 9.5 ⚓
- ✅ transport score ≥ 85: 95.1

**Whitechapel** (Spitalfields). Dense, central, high income deprivation. Flags: broadcast_lad, broadcast_msoa.

- ✅ transport score ≥ 85: 89.6 ⚓
- ✅ community score ≤ 40: 27.0

**Kensington** (Kensington Abingdon). Among the most expensive places in England. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 25: 17.9 ⚓
- ✅ amenities score ≥ 70: 100.0

**Manchester** (Castlefield & Deansgate). City centre; Greater Manchester crime is estimated (no police.uk data). Flags: broadcast_lad, broadcast_msoa, imputed.

- ✅ flag imputed: crime_asb, crime_burglary, crime_damage_disorder, crime_theft, crime_violence ⚓
- ✅ safety score ≤ 25: 18.6 ⚓
- ✅ transport score ≥ 85: 89.8

**Salford** (Weaste & Seedley). Greater Manchester, so crime is estimated. Flags: broadcast_lad, broadcast_msoa, imputed.

- ✅ flag imputed: crime_asb, crime_burglary, crime_damage_disorder, crime_theft, crime_violence ⚓

**Jesmond** (South Jesmond & Sandyford). Popular inner suburb with bars and restaurants. Flags: broadcast_lad, broadcast_msoa.

- ✅ amenities score ≥ 70: 95.6
- ✅ overall score ≥ 50: 75.9

**Headingley** (Headingley). Student suburb: lively, but high burglary and theft. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ amenities score ≥ 70: 92.0
- ✅ safety score ≤ 45: 29.6

**Harrogate** (Central Harrogate). Affluent spa town. Flags: broadcast_lad, broadcast_msoa.

- ✅ overall score ≥ 55: 72.0 ⚓
- ✅ community score ≥ 60: 67.1

**Winchester** (Winchester East). Affluent cathedral city with strong schools. Flags: broadcast_lad, broadcast_msoa.

- ✅ overall score ≥ 55: 66.4
- ✅ education score ≥ 55: 58.0

**St Albans** (St Albans Central). London commuter city, expensive. Flags: broadcast_lad, broadcast_msoa.

- ✅ housing score ≤ 35: 29.5 ⚓
- ✅ community score ≥ 65: 73.4

**Royal Sutton Coldfield** (Sutton Coldfield South & Central). Affluent suburb of Birmingham. Flags: broadcast_lad, broadcast_msoa.

- ✅ community score ≥ 55: 62.3
- ✅ overall score ≥ 50: 68.7

**Cambridge** (Central & West Cambridge). Expensive university city, cycling and rail. Flags: broadcast_lad, broadcast_msoa, low_n.

- ✅ housing score ≤ 30: 13.4 ⚓
- ✅ gigabit_broadband ≥ 80: 87.0

**Chipping Campden** (Willersey, Chipping Campden & Blockley). Cotswolds market town: green, remote from rail. Flags: broadcast_lad, broadcast_msoa.

- ✅ transport score ≤ 45: 42.9 ⚓
- ✅ station_distance ≥ 5,000: 5,469.4 ⚓
- ✅ no2 ≤ 8: 3.7

**Holsworthy** (Holsworthy, Bradworthy & Welcombe). Remote north Devon town: no railway, patchy broadband. Flags: broadcast_lad, broadcast_msoa.

- ✅ station_distance ≥ 15,000: 26,214.4 ⚓
- ✅ transport score ≤ 35: 22.9 ⚓
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

- ✅ amenities score ≥ 70: 99.9
- ✅ housing score ≤ 40: 17.9

**Bexhill-on-Sea** (Bexhill Central). Older seaside town. Flags: broadcast_lad, broadcast_msoa.

- ✅ aged_65_plus ≥ 30: 30.5
