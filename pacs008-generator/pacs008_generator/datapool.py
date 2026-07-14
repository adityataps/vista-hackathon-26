"""Realistic, internally consistent reference data (agents, parties, IBANs)."""
import random
import string
import uuid

# BIC -> (country, city) ; real-looking correspondents per country
AGENTS = [
    {"bic": "COBADEFFXXX", "ctry": "DE"}, {"bic": "DEUTDEFFXXX", "ctry": "DE"},
    {"bic": "BNPAFRPPXXX", "ctry": "FR"}, {"bic": "SOGEFRPPXXX", "ctry": "FR"},
    {"bic": "HSBCGB2LXXX", "ctry": "GB"}, {"bic": "BARCGB22XXX", "ctry": "GB"},
    {"bic": "UBSWCHZH80A", "ctry": "CH"}, {"bic": "CRESCHZZ80A", "ctry": "CH"},
    {"bic": "INGBNL2AXXX", "ctry": "NL"}, {"bic": "ABNANL2AXXX", "ctry": "NL"},
    {"bic": "CITIUS33XXX", "ctry": "US"}, {"bic": "CHASUS33XXX", "ctry": "US"},
    {"bic": "BOTKJPJTXXX", "ctry": "JP"},
]

# currency -> max decimals
CURRENCIES = {"EUR": 2, "USD": 2, "CHF": 2, "GBP": 2, "JPY": 0}

FIRST = ["Alpine", "Nordwind", "Provence", "Thames", "Rhein", "Delta", "Pacific",
         "Meridian", "Helvetia", "Atlas", "Baltic", "Sakura"]
KIND = ["Trading", "Logistics", "Engineering", "Consulting", "Textiles",
        "Machinery", "Foods", "Pharma", "Components", "Metals"]
FORM = {"DE": "GmbH", "FR": "SARL", "GB": "Ltd", "CH": "AG", "NL": "BV",
        "US": "Inc.", "JP": "K.K."}

ADDR = {
    "DE": ("Industriestrasse", "60313", "Frankfurt am Main"),
    "FR": ("Rue de la Paix", "75002", "Paris"),
    "GB": ("Lombard Street", "EC3V 9AA", "London"),
    "CH": ("Bahnhofstrasse", "8001", "Zuerich"),
    "NL": ("Herengracht", "1017 BZ", "Amsterdam"),
    "US": ("Market Street", "94111", "San Francisco"),
    "JP": ("Marunouchi", "100-8388", "Tokyo"),
}

# country -> (BBAN length, BBAN alphabet) for IBAN construction; None = no IBAN (US/JP)
IBAN_FMT = {"DE": (18, "d"), "FR": (23, "m"), "GB": (18, "b"),
            "CH": (17, "d"), "NL": (14, "b")}


def _mod97(iban):
    s = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in s)) % 97


def make_iban(rng, ctry):
    """Construct a checksum-valid IBAN for the given country."""
    fmt = IBAN_FMT.get(ctry)
    if not fmt:
        return None
    n, kind = fmt
    if kind == "d":
        bban = "".join(rng.choice(string.digits) for _ in range(n))
    elif kind == "b":  # 4 bank letters + digits
        bban = "".join(rng.choice(string.ascii_uppercase) for _ in range(4)) + \
               "".join(rng.choice(string.digits) for _ in range(n - 4))
    else:  # mixed digits
        bban = "".join(rng.choice(string.digits) for _ in range(n))
    chk = 98 - _mod97(ctry + "00" + bban)
    return "%s%02d%s" % (ctry, chk, bban)


def make_party(rng, ctry):
    name = "%s %s %s" % (rng.choice(FIRST), rng.choice(KIND), FORM[ctry])
    strt, pstcd, town = ADDR[ctry]
    return {
        "nm": name, "strt": strt, "bldgnb": str(rng.randint(1, 250)),
        "pstcd": pstcd, "twn": town, "ctry": ctry,
        "iban": make_iban(rng, ctry),
        "othr_id": None if IBAN_FMT.get(ctry) else str(rng.randint(10 ** 9, 10 ** 10 - 1)),
    }


def make_amount(rng, ccy):
    dec = CURRENCIES[ccy]
    if dec == 0:
        return str(rng.randint(100000, 50000000))
    return "%.2f" % (rng.randint(10000, 50000000) / 100.0)


def make_uetr(rng):
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))
