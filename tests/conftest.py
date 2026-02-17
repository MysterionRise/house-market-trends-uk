"""Shared test fixtures for the UK Liveability Index test suite."""

import polars as pl
import pytest


@pytest.fixture
def nspl_csv(tmp_path):
    """Write a minimal NSPL CSV for testing. Shared across geocode and clean tests."""
    csv_content = """pcds,lsoa21,doterm,lat,long
SW1A 1AA,E01000001,,51.501,-0.141
EC1A 1BB,E01000002,,51.520,-0.097
W1A 1AB,E01000003,,51.518,-0.144
N1 9GU,E01000004,,51.546,-0.075
SE1 7PB,E01000005,,51.504,-0.114
E1 6AN,E01000006,202301,51.517,-0.065
"""
    csv_path = tmp_path / "nspl_test.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def sample_price_paid() -> pl.DataFrame:
    """1000 sample Price Paid transactions using postcodes from nspl_csv fixture."""
    import random

    random.seed(42)

    n = 1000
    # Use realistic postcodes that overlap with nspl_csv fixture
    valid_postcodes = ["SW1A 1AA", "EC1A 1BB", "W1A 1AB", "N1 9GU", "SE1 7PB"]
    postcodes = [valid_postcodes[i % len(valid_postcodes)] for i in range(n)]

    return pl.DataFrame({
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
    })
