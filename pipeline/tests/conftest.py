"""Shared test fixtures for the UK Liveability Index test suite."""

import polars as pl
import pytest


@pytest.fixture(autouse=True)
def _england_only(monkeypatch):
    """Stagers filter by the active nations; tests that don't say otherwise build England."""
    monkeypatch.setenv("LIX_NATIONS", "E")


# Real NSPL Aug 2026 header (35 columns), so tests catch column renames
NSPL_HEADER = (
    "pcd7,pcd8,pcds,dointr,doterm,usrtypind,east1m,north1m,gridind,oa21cd,cty26cd,ced25cd,"
    "lad26cd,wd26cd,nhser24cd,ctry26cd,rgn26cd,pcon24cd,ttwa15cd,itl25cd,npark16cd,lsoa21cd,"
    "msoa21cd,wz11cd,sicbl26cd,bua24cd,ruc21ind,oac21ind,lat,long,lep21cd1,lep21cd2,pfa23cd,"
    "imd25ind,icb26cd"
)

# (pcds, doterm, oa21cd, lad26cd, ctry26cd, rgn26cd, lsoa21cd, msoa21cd, pfa23cd, lat, long)
NSPL_ROWS = [
    (
        "SW1A 1AA",
        "",
        "E00023938",
        "E09000033",
        "E92000001",
        "E12000007",
        "E01000001",
        "E02000001",
        "E23000001",
        51.501,
        -0.141,
    ),
    (
        "EC1A 1BB",
        "",
        "E00000001",
        "E09000001",
        "E92000001",
        "E12000007",
        "E01000002",
        "E02000001",
        "E23000034",
        51.520,
        -0.097,
    ),
    (
        "W1A 1AB",
        "",
        "E00023939",
        "E09000033",
        "E92000001",
        "E12000007",
        "E01000003",
        "E02000002",
        "E23000001",
        51.518,
        -0.144,
    ),
    (
        "N1 9GU",
        "",
        "E00008540",
        "E09000019",
        "E92000001",
        "E12000007",
        "E01000004",
        "E02000003",
        "E23000001",
        51.546,
        -0.075,
    ),
    (
        "SE1 7PB",
        "",
        "E00023940",
        "E09000022",
        "E92000001",
        "E12000007",
        "E01000005",
        "E02000004",
        "E23000001",
        51.504,
        -0.114,
    ),
    # Terminated postcode
    (
        "E1 6AN",
        "202301",
        "E00021723",
        "E09000030",
        "E92000001",
        "E12000007",
        "E01000006",
        "E02000005",
        "E23000001",
        51.517,
        -0.065,
    ),
    # Welsh postcode
    (
        "CF10 1AA",
        "",
        "W00009078",
        "W06000015",
        "W92000004",
        "W99999999",
        "W01001880",
        "W02000384",
        "W15000003",
        51.476,
        -3.177,
    ),
]


def _nspl_line(row) -> str:
    pcds, doterm, oa, lad, ctry, rgn, lsoa, msoa, pfa, lat, long = row
    values = dict.fromkeys(NSPL_HEADER.split(","), "")
    values.update(
        pcd7=pcds,
        pcd8=pcds,
        pcds=pcds,
        dointr="198001",
        doterm=doterm,
        usrtypind="0",
        east1m="529090",
        north1m="179645",
        gridind="1",
        oa21cd=oa,
        lad26cd=lad,
        ctry26cd=ctry,
        rgn26cd=rgn,
        lsoa21cd=lsoa,
        msoa21cd=msoa,
        ruc21ind="UN1",
        pfa23cd=pfa,
        imd25ind="5",
    )
    quoted = [f'"{v}"' for v in values.values()]
    # lat/long are unquoted numbers in the real file
    names = list(values)
    quoted[names.index("lat")] = str(lat)
    quoted[names.index("long")] = str(long)
    return ",".join(quoted)


@pytest.fixture
def nspl_csv(tmp_path):
    """Write a minimal NSPL CSV with the real header. Shared across geo and stage tests."""
    csv_path = tmp_path / "NSPL_AUG_2026_UK.csv"
    csv_path.write_text("\n".join([NSPL_HEADER, *map(_nspl_line, NSPL_ROWS)]) + "\n")
    return csv_path


@pytest.fixture
def nspl_parts():
    """(header, rows, line builder) for tests that need a custom NSPL file."""
    return NSPL_HEADER, NSPL_ROWS, _nspl_line


@pytest.fixture(scope="session")
def httpserver_listen_address():
    """Bind pytest-httpserver to IPv4 loopback, the only host pytest-socket allows."""
    return ("127.0.0.1", 0)


@pytest.fixture
def sample_price_paid() -> pl.DataFrame:
    """1000 sample Price Paid transactions using postcodes from nspl_csv fixture."""
    import random

    random.seed(42)

    n = 1000
    # Use realistic postcodes that overlap with nspl_csv fixture
    valid_postcodes = ["SW1A 1AA", "EC1A 1BB", "W1A 1AB", "N1 9GU", "SE1 7PB"]
    postcodes = [valid_postcodes[i % len(valid_postcodes)] for i in range(n)]

    return pl.DataFrame(
        {
            "transaction_id": [f"{{TXN-{i:06d}}}" for i in range(n)],
            "price": [random.randint(100000, 1000000) for _ in range(n)],
            "date_of_transfer": pl.Series(
                [f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
            ).str.strptime(pl.Date, "%Y-%m-%d"),
            "postcode": postcodes,
            "property_type": [random.choice(["D", "S", "T", "F"]) for _ in range(n)],
            "old_new": [random.choice(["Y", "N"]) for _ in range(n)],
            "duration": [random.choice(["F", "L"]) for _ in range(n)],
            "paon": ["1"] * n,
            "saon": [""] * n,
            "street": ["TEST STREET"] * n,
            "locality": [""] * n,
            "town_city": ["LONDON"] * n,
            "district": ["CITY OF LONDON"] * n,
            "county": ["GREATER LONDON"] * n,
            "ppd_category": ["A"] * n,
            "record_status": ["A"] * 950 + ["D"] * 50,
        }
    )
