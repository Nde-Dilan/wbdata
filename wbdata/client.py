"""
The client class defines the wbdata client class and associated support classes.
"""

import contextlib
import dataclasses
import datetime as dt
import re
from collections.abc import Generator, Iterable, Sequence
from pathlib import Path
from typing import Any

import decorator
import requests
import tabulate

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:
    pd = None  # type: ignore[assignment]


from . import cache, dates, fetcher

BASE_URL = "https://api.worldbank.org/v2"
COUNTRIES_URL = f"{BASE_URL}/countries"
ILEVEL_URL = f"{BASE_URL}/incomeLevels"
INDICATOR_URL = f"{BASE_URL}/indicators"
LTYPE_URL = f"{BASE_URL}/lendingTypes"
SOURCE_URL = f"{BASE_URL}/sources"
TOPIC_URL = f"{BASE_URL}/topics"

NON_SOVEREIGN_COUNTRIES: tuple[str, ...] = (
    "American Samoa",
    "Aruba",
    "Bermuda",
    "British Virgin Islands",
    "Cayman Islands",
    "Channel Islands",
    "Curacao",
    "Faroe Islands",
    "French Polynesia",
    "Gibraltar",
    "Greenland",
    "Guam",
    "Hong Kong SAR, China",
    "Isle of Man",
    "Macao SAR, China",
    "New Caledonia",
    "Northern Mariana Islands",
    "Puerto Rico (US)",
    "Sint Maarten (Dutch part)",
    "St. Martin (French part)",
    "Turks and Caicos Islands",
    "Virgin Islands (U.S.)",
    "West Bank and Gaza",
)
non_sovereign_countries = list(NON_SOVEREIGN_COUNTRIES)

NON_SOVEREIGN_IDS: frozenset[str] = frozenset(
    {
        "ABW",
        "ASM",
        "BMU",
        "CHI",
        "CUW",
        "CYM",
        "FRO",
        "GIB",
        "GRL",
        "GUM",
        "HKG",
        "IMN",
        "MAC",
        "MAF",
        "MNP",
        "NCL",
        "PRI",
        "PSE",
        "PYF",
        "SXM",
        "TCA",
        "VGB",
        "VIR",
    }
)

NON_SOVEREIGN_ISO2: frozenset[str] = frozenset(
    {
        "AW",
        "AS",
        "BM",
        "JG",
        "CW",
        "KY",
        "FO",
        "GI",
        "GL",
        "GU",
        "HK",
        "IM",
        "MO",
        "MF",
        "MP",
        "NC",
        "PR",
        "PS",
        "PF",
        "SX",
        "TC",
        "VG",
        "VI",
    }
)

AGGREGATE_IDS: frozenset[str] = frozenset(
    {
        "AFE",
        "AFR",
        "AFW",
        "ARB",
        "BEA",
        "BEC",
        "BHI",
        "BLA",
        "BMN",
        "BSS",
        "CAA",
        "CEA",
        "CEB",
        "CEU",
        "CLA",
        "CME",
        "CSA",
        "CSS",
        "DEA",
        "DEC",
        "DLA",
        "DMN",
        "DNS",
        "DSA",
        "DSF",
        "DSS",
        "EAP",
        "EAR",
        "EAS",
        "ECA",
        "ECS",
        "EMU",
        "EUU",
        "FXS",
        "HIC",
        "HPC",
        "IBB",
        "IBD",
        "IBT",
        "IDA",
        "IDB",
        "IDX",
        "INX",
        "LAC",
        "LCN",
        "LDC",
        "LIC",
        "LMC",
        "LMY",
        "LTE",
        "MDE",
        "MEA",
        "MIC",
        "MNA",
        "NAC",
        "NAF",
        "NRS",
        "NXS",
        "OED",
        "OSS",
        "PRE",
        "PSS",
        "PST",
        "RRS",
        "SAS",
        "SSA",
        "SSF",
        "SST",
        "SXZ",
        "TEA",
        "TEC",
        "TLA",
        "TMN",
        "TSA",
        "TSS",
        "UMC",
        "WLD",
        "XZN",
    }
)

AGGREGATE_ISO2: frozenset[str] = frozenset(
    {
        "1A",
        "1W",
        "4E",
        "7E",
        "8S",
        "B1",
        "B2",
        "B3",
        "B4",
        "B6",
        "B7",
        "B8",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
        "C9",
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
        "D7",
        "EU",
        "F1",
        "F6",
        "M1",
        "M2",
        "N6",
        "OE",
        "S1",
        "S2",
        "S3",
        "S4",
        "T2",
        "T3",
        "T4",
        "T5",
        "T6",
        "T7",
        "V1",
        "V2",
        "V3",
        "V4",
        "XC",
        "XD",
        "XE",
        "XF",
        "XG",
        "XH",
        "XI",
        "XJ",
        "XL",
        "XM",
        "XN",
        "XO",
        "XP",
        "XQ",
        "XR",
        "XS",
        "XT",
        "XU",
        "XY",
        "XZ",
        "Z4",
        "Z7",
        "ZB",
        "ZF",
        "ZG",
        "ZH",
        "ZI",
        "ZJ",
        "ZQ",
        "ZT",
    }
)

AGGREGATE_NAMES: frozenset[str] = frozenset(
    {
        "Africa",
        "Africa Eastern and Southern",
        "Africa Western and Central",
        "Arab World",
        "Caribbean small states",
        "Central Europe and the Baltics",
        "Early-demographic dividend",
        "East Asia & Pacific",
        "East Asia & Pacific (IBRD-only countries)",
        "East Asia & Pacific (IDA & IBRD countries)",
        "East Asia & Pacific (IDA-eligible countries)",
        "East Asia & Pacific (excluding high income)",
        "East Asia and the Pacific (IFC classification)",
        "Euro area",
        "Europe & Central Asia",
        "Europe & Central Asia (IBRD-only countries)",
        "Europe & Central Asia (IDA & IBRD countries)",
        "Europe & Central Asia (IDA-eligible countries)",
        "Europe & Central Asia (excluding high income)",
        "Europe and Central Asia (IFC classification)",
        "European Union",
        "Heavily indebted poor countries (HIPC)",
        "High income",
        "IBRD countries classified as high income",
        "IBRD only",
        "IBRD, including blend",
        "IDA & IBRD total",
        (
            "IDA countries classified as fragile situations, "
            "excluding Sub-Saharan Africa"
        ),
        "IDA countries in Sub-Saharan Africa classified as fragile situations ",
        "IDA countries in Sub-Saharan Africa not classified as fragile situations ",
        (
            "IDA countries not classified as fragile situations, "
            "excluding Sub-Saharan Africa"
        ),
        "IDA only",
        "IDA total",
        "Late-demographic dividend",
        "Latin America & Caribbean ",
        "Latin America & Caribbean (excluding high income)",
        "Latin America & the Caribbean (IBRD-only countries)",
        "Latin America & the Caribbean (IDA & IBRD countries)",
        "Latin America & the Caribbean (IDA-eligible countries)",
        "Latin America and the Caribbean (IFC classification)",
        "Least developed countries: UN classification",
        "Low & middle income",
        "Low income",
        "Lower middle income",
        "Middle East (developing only)",
        "Middle East and North Africa (IFC classification)",
        "Middle East, North Africa, Afghanistan & Pakistan",
        "Middle East, North Africa, Afghanistan & Pakistan (IBRD only)",
        "Middle East, North Africa, Afghanistan & Pakistan (IDA & IBRD)",
        "Middle East, North Africa, Afghanistan & Pakistan (IDA total)",
        "Middle East, North Africa, Afghanistan & Pakistan (excluding high income)",
        "Middle income",
        "Non-resource rich Sub-Saharan Africa countries",
        "North Africa",
        "North America",
        "Not classified",
        "OECD members",
        "Other small states",
        "Pacific island small states",
        "Post-demographic dividend",
        "Pre-demographic dividend",
        "Resource rich Sub-Saharan Africa countries",
        "Small states",
        "South Asia",
        "South Asia (IDA & IBRD)",
        "South Asia (IDA-eligible countries)",
        "South Asia (IFC classification)",
        "Sub-Saharan Africa ",
        "Sub-Saharan Africa (IBRD-only countries)",
        "Sub-Saharan Africa (IDA & IBRD countries)",
        "Sub-Saharan Africa (IDA-eligible countries)",
        "Sub-Saharan Africa (IFC classification)",
        "Sub-Saharan Africa (excluding high income)",
        "Sub-Saharan Africa excluding South Africa",
        "Sub-Saharan Africa excluding South Africa and Nigeria",
        "Upper middle income",
        "World",
    }
)


class SearchResult(list):
    """
    A list that prints out a user-friendly table when printed or returned on the
    command line


    Items are expected to be dict-like and have an "id" key and a "name" or
    "value" key
    """

    def __repr__(self) -> str:
        try:
            return tabulate.tabulate(
                [[o["id"], o["name"]] for o in self],
                headers=["id", "name"],
                tablefmt="simple",
            )
        except KeyError:
            return tabulate.tabulate(
                [[o["id"], o["value"]] for o in self],
                headers=["id", "value"],
                tablefmt="simple",
            )


if pd:

    class Series(pd.Series):
        """
        A `pandas.Series` with a `last_updated` attribute.


        The `last_updated` attribute is set when the `Series` is created but not
        automatically updated. Its value is either `None` or a `datetime.datetime`
        object.
        """

        def __init__(
            self,
            *args,
            last_updated: None | dt.datetime = None,
            **kwargs,
        ):
            super().__init__(*args, **kwargs)
            self.last_updated = last_updated

        _metadata = ["last_updated"]

        @property
        def _constructor(self):
            return Series

    class DataFrame(pd.DataFrame):
        def __init__(self, *args, serieses: dict[str, Series] | None = None, **kwargs):
            """
            A `pandas.DataFrame` with a `last_updated` attribute


            The `last_updated` attribute is set when the Series is created but not
            automatically updated. Its value is a dictionary where the keys are the
            column names and the values are `None` or a `datetime.datetime` object.
            """
            if serieses:
                super().__init__(serieses)
                self.last_updated: dict[str, dt.datetime | None] | None = {
                    name: s.last_updated for name, s in serieses.items()
                }
            else:
                super().__init__(*args, **kwargs)
                self.last_updated = None

        _metadata = ["last_updated"]

        @property
        def _constructor(self):
            return DataFrame
else:
    Series = Any  # type: ignore[misc, assignment]
    DataFrame = Any  # type: ignore[misc, assignment]


@decorator.decorator
def needs_pandas(f, *args, **kwargs):
    if pd is None:
        raise RuntimeError(f"{f.__name__} requires pandas")
    return f(*args, **kwargs)


def _parse_value_or_iterable(arg: Any) -> str:
    """
    If arg is a single value, return it as a string; if an iterable, return a
    ;-joined string of all values
    """
    if isinstance(arg, str):
        return arg
    if isinstance(arg, Iterable):
        return ";".join(str(i) for i in arg)
    return str(arg)


def _cast_float(value: str) -> float | None:
    """Return a value coerced to float or None"""
    with contextlib.suppress(ValueError, TypeError):
        return float(value)
    return None


def _filter_by_pattern(
    rows: Iterable[dict[str, Any]], pattern=str | re.Pattern
) -> Generator[dict[str, Any], None, None]:
    """Return a generator of rows matching the pattern"""
    if isinstance(pattern, str):
        pattern = re.compile(pattern, re.IGNORECASE)
    assert isinstance(pattern, re.Pattern)
    return (row for row in rows if pattern.search(row["name"]))


def _is_aggregate_entity(entity: dict[str, Any]) -> bool:
    """Return True if an entity dict represents an aggregate region or group."""
    income_level = entity.get("incomeLevel")
    if isinstance(income_level, dict) and income_level.get("value") == "Aggregates":
        return True
    region = entity.get("region")
    if isinstance(region, dict) and (
        region.get("value") == "Aggregates" or region.get("id") == "NA"
    ):
        return True
    lending_type = entity.get("lendingType")
    if isinstance(lending_type, dict) and lending_type.get("value") == "Aggregates":
        return True
    if entity.get("id") in AGGREGATE_IDS:
        return True
    if entity.get("iso2Code") in AGGREGATE_ISO2:
        return True
    return entity.get("name") in AGGREGATE_NAMES


def _is_non_sovereign_entity(entity: dict[str, Any]) -> bool:
    """Return True if an entity dict represents a non-sovereign country/territory."""
    if entity.get("name") in NON_SOVEREIGN_COUNTRIES:
        return True
    if entity.get("id") in NON_SOVEREIGN_IDS:
        return True
    return entity.get("iso2Code") in NON_SOVEREIGN_ISO2


def _is_aggregate_row(row: dict[str, Any]) -> bool:
    """Return True if an observation row represents an aggregate."""
    iso3 = row.get("countryiso3code")
    if iso3 and iso3 in AGGREGATE_IDS:
        return True
    country_obj = row.get("country")
    if isinstance(country_obj, dict):
        if country_obj.get("id") in AGGREGATE_ISO2:
            return True
        if country_obj.get("value") in AGGREGATE_NAMES:
            return True
    return False


def _is_non_sovereign_row(row: dict[str, Any]) -> bool:
    """Return True if an observation row represents a non-sovereign country."""
    iso3 = row.get("countryiso3code")
    if iso3 and iso3 in NON_SOVEREIGN_IDS:
        return True
    country_obj = row.get("country")
    if isinstance(country_obj, dict):
        if country_obj.get("value") in NON_SOVEREIGN_COUNTRIES:
            return True
        if country_obj.get("id") in NON_SOVEREIGN_ISO2:
            return True
    return False


def _resolve_country_and_flags(
    country: str | Sequence[str],
    include_aggregates: bool,
    include_non_sovereign: bool,
    sovereign_only: bool,
    exclude_aggregates: bool | None,
) -> tuple[str | Sequence[str], bool, bool]:
    """Resolve and normalize country and filter flags."""
    if isinstance(country, str):
        c_lower = country.strip().lower()
        if c_lower in ("countries", "countries_only"):
            country = "all"
            include_aggregates = False
        elif c_lower == "sovereign":
            country = "all"
            include_aggregates = False
            include_non_sovereign = False

    if exclude_aggregates is not None:
        include_aggregates = not exclude_aggregates

    if sovereign_only:
        include_aggregates = False
        include_non_sovereign = False

    return country, include_aggregates, include_non_sovereign


@dataclasses.dataclass
class Client:
    """
    The client object for the World Bank API.

    Most users will only need to create this if they need more than one cache,
    want to specify a cache programmatically rather than through environment
    variables, or want to specify a requests Session.

    Parameters:
        cache_path: path to the cache file
        cache_ttl_days: number of days to retain cached results
        cache_max_size: number of items to retain in the cache
        session: requests Session object to use to make requests
    """

    cache_path: str | Path | None = None
    cache_ttl_days: int | None = None
    cache_max_size: int | None = None
    session: requests.Session | None = None

    def __post_init__(self):
        self.fetcher = fetcher.Fetcher(
            cache=cache.get_cache(
                path=self.cache_path,
                ttl_days=self.cache_ttl_days,
                max_size=self.cache_max_size,
            )
        )
        self.has_pandas = pd is None

    def get_data(
        self,
        indicator: str,
        country: str | Sequence[str] = "all",
        date: str
        | dt.datetime
        | tuple[str | dt.datetime, str | dt.datetime]
        | None = None,
        freq: str = "Y",
        source: int | str | Sequence[int | str] | None = None,
        parse_dates: bool = False,
        skip_cache: bool = False,
        include_aggregates: bool = True,
        include_non_sovereign: bool = True,
        sovereign_only: bool = False,
        exclude_aggregates: bool | None = None,
    ) -> fetcher.Result:
        """
        Retrieve indicators for given countries and years

        Parameters:
            indicator: the desired indicator code
            country: a country code, sequence of country codes, or "all" (default).
                Also accepts special strings "countries" / "countries_only" (exclude
                aggregates) and "sovereign" (sovereign countries only).
            date: the desired date as a string, datetime object or a 2-tuple
                with start and end dates
            freq: the desired periodicity of the data, one of 'Y' (yearly), 'M'
                (monthly), or 'Q' (quarterly). The indicator may or may not
                support the specified frequency.
            source: the specific source to retrieve data from (defaults on API
                to 2, World Development Indicators)
            parse_dates: if True, convert date field to a datetime.datetime
                object.
            skip_cache: bypass the cache when downloading
            include_aggregates: if False, exclude aggregate regions and groups
                from the returned data. Defaults to True.
            include_non_sovereign: if False, exclude non-sovereign
                countries/territories from the returned data. Defaults to True.
            sovereign_only: if True, exclude both aggregates and non-sovereign
                countries. Defaults to False.
            exclude_aggregates: if specified, sets include_aggregates to its negation.

        Returns:
            A list of dictionaries of observations
        """
        country, include_aggregates, include_non_sovereign = (
            _resolve_country_and_flags(
                country=country,
                include_aggregates=include_aggregates,
                include_non_sovereign=include_non_sovereign,
                sovereign_only=sovereign_only,
                exclude_aggregates=exclude_aggregates,
            )
        )
        url = COUNTRIES_URL
        try:
            c_part = _parse_value_or_iterable(country)
        except TypeError as e:
            raise TypeError("'country' must be a string or iterable'") from e
        url = "/".join((url, c_part, "indicators", indicator))
        params: dict[str, Any] = {}
        if date:
            params["date"] = dates.format_dates(date, freq)
        if source:
            params["source"] = source
        data = self.fetcher.fetch(url=url, params=params, skip_cache=skip_cache)
        if parse_dates:
            dates.parse_row_dates(data)
        if (not include_aggregates or not include_non_sovereign) and isinstance(
            data, list
        ):
                filtered_rows = [
                    row
                    for row in data
                    if (include_aggregates or not _is_aggregate_row(row))
                    and (include_non_sovereign or not _is_non_sovereign_row(row))
                ]
                data = fetcher.Result(
                    filtered_rows,
                    last_updated=getattr(data, "last_updated", None),
                )
        return data

    def _id_only_query(self, url: str, id_: Any, skip_cache: bool) -> SearchResult:
        """
        Utility to retrieve information when ids are the only arguments

        Parameters:
            url: the base url to use for the query
            id_: an id or sequence of ids
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects describing results
        """
        if id_:
            url = "/".join((url, _parse_value_or_iterable(id_)))
        return SearchResult(self.fetcher.fetch(url=url, skip_cache=skip_cache))

    def get_sources(
        self,
        source_id: int | str | Sequence[int | str] | None = None,
        skip_cache: bool = False,
    ) -> SearchResult:
        """
        Retrieve information on one or more sources

        Parameters:
            source_id: a source id or sequence thereof.  None returns all sources
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects describing selected sources
        """
        return self._id_only_query(url=SOURCE_URL, id_=source_id, skip_cache=skip_cache)

    def get_incomelevels(
        self,
        level_id: int | str | Sequence[int | str] | None = None,
        skip_cache: bool = False,
    ) -> SearchResult:
        """
        Retrieve information on one or more income level aggregates

        Parameters:
            level_id: a level id or sequence thereof.  None returns all income level
                aggregates
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects describing selected
                income level aggregates
        """
        return self._id_only_query(ILEVEL_URL, level_id, skip_cache=skip_cache)

    def get_topics(
        self,
        topic_id: int | str | Sequence[int | str] | None = None,
        skip_cache: bool = False,
    ) -> SearchResult:
        """
        Retrieve information on one or more topics

        Parameters:
            topic_id: a topic id or sequence thereof.  None returns all topics
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects describing selected topic
                aggregates
        """
        return self._id_only_query(TOPIC_URL, topic_id, skip_cache=skip_cache)

    def get_lendingtypes(
        self,
        type_id: int | str | Sequence[int | str] | None = None,
        skip_cache: bool = False,
    ) -> SearchResult:
        """
        Retrieve information on one or more lending type aggregates

        Parameters:
            type_id: lending type id or sequence thereof.  None returns all lending
                type aggregates
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects describing selected lending type aggregates
        """
        return self._id_only_query(LTYPE_URL, type_id, skip_cache=skip_cache)

    def get_countries(
        self,
        country_id: str | Sequence[str] | None = None,
        query: str | re.Pattern | None = None,
        incomelevel: int | str | Sequence[int | str] | None = None,
        lendingtype: int | str | Sequence[int | str] | None = None,
        skip_cache: bool = False,
        include_aggregates: bool = True,
        include_non_sovereign: bool = True,
        sovereign_only: bool = False,
        exclude_aggregates: bool | None = None,
    ) -> SearchResult:
        """
        Retrieve information on one or more country or regional aggregates.

        You can filter your results by specifying `query`, `incomelevel`, or
        `lendingtype`.  Specifying `query` will only return countries with
        names that match the query as a regular expression. If a string is
        supplied, the match is case insensitive.

        Specifying `query`, `incomelevel`, or `lendingtype` along with
        `country_id` will raise a `ValueError`.

        Parameters:
            country_id: a country id or sequence thereof. None returns all
                countries and aggregates.
            query: a regular expression on which to filter results
            incomelevel: desired incomelevel id or ids on which to filter results
            lendingtype: desired lendingtype id or ids on which to filter results
            skip_cache: bypass cache when downloading
            include_aggregates: if False, exclude aggregate regions and groups
                from results. Defaults to True.
            include_non_sovereign: if False, exclude non-sovereign
                countries/territories from results. Defaults to True.
            sovereign_only: if True, exclude both aggregates and non-sovereign
                countries. Defaults to False.
            exclude_aggregates: if specified, sets include_aggregates to its negation.

        Returns:
            list of dictionaries describing countries

        """
        if exclude_aggregates is not None:
            include_aggregates = not exclude_aggregates
        if sovereign_only:
            include_aggregates = False
            include_non_sovereign = False

        raw_results: Iterable[dict[str, Any]]
        if country_id:
            if incomelevel or lendingtype or query:
                raise ValueError("Can't specify country_id and aggregates")
            raw_results = self._id_only_query(
                COUNTRIES_URL, country_id, skip_cache=skip_cache
            )
        else:
            params = {}
            if incomelevel:
                params["incomeLevel"] = _parse_value_or_iterable(incomelevel)
            if lendingtype:
                params["lendingType"] = _parse_value_or_iterable(lendingtype)
            fetched = self.fetcher.fetch(
                url=COUNTRIES_URL, params=params, skip_cache=skip_cache
            )
            raw_results = _filter_by_pattern(fetched, query) if query else fetched

        if not include_aggregates or not include_non_sovereign:
            raw_results = [
                row
                for row in raw_results
                if (include_aggregates or not _is_aggregate_entity(row))
                and (include_non_sovereign or not _is_non_sovereign_entity(row))
            ]

        return SearchResult(raw_results)

    def get_indicators(
        self,
        indicator: str | Sequence[str] | None = None,
        query: str | re.Pattern | None = None,
        source: str | int | Sequence[str | int] | None = None,
        topic: str | int | Sequence[str | int] | None = None,
        skip_cache: bool = False,
    ) -> SearchResult:
        """
        Retrieve information about an indicator or indicators.

        When called with no arguments, returns all indicators.  You can specify
        one or more indicators to retrieve, or you can specify a source or a
        topic for which to list all indicators.  Specifying more than one of
        `indicators`, `source`, and `topic` will raise a ValueError.

        Specifying `query` will only return indicators with names that match
        the query as a regular expression. If a string is supplied, the match
        is case insensitive. Specifying both `query` and `indicators` will raise
        a ValueError.

        Parameters:
            indicator: an indicator code or sequence thereof
            query: a regular expression on which to filter results
            source: a source id or sequence thereof
            topic: a topic id or sequence thereof
            skip_cache: bypass cache when downloading

        Returns:
            list of dictionary objects representing indicators
        """
        if query and indicator:
            raise ValueError("Cannot specify indicator and query")
        if sum(bool(i) for i in (indicator, source, topic)) > 1:
            raise ValueError(
                "Cannot specify more than one of indicator, source, and topic"
            )
        if indicator:
            url = "/".join((INDICATOR_URL, _parse_value_or_iterable(indicator)))
        elif source:
            url = "/".join((SOURCE_URL, _parse_value_or_iterable(source), "indicators"))
        elif topic:
            url = "/".join((TOPIC_URL, _parse_value_or_iterable(topic), "indicators"))
        else:
            url = INDICATOR_URL
        results = self.fetcher.fetch(url=url, skip_cache=skip_cache)
        if query:
            results = _filter_by_pattern(results, query)
        return SearchResult(results)

    @needs_pandas
    def get_series(
        self,
        indicator: str,
        country: str | Sequence[str] = "all",
        date: str
        | dt.datetime
        | tuple[str | dt.datetime, str | dt.datetime]
        | None = None,
        freq: str = "Y",
        source: int | str | Sequence[int | str] | None = None,
        parse_dates: bool = False,
        name: str = "value",
        keep_levels: bool = False,
        skip_cache: bool = False,
        include_aggregates: bool = True,
        include_non_sovereign: bool = True,
        sovereign_only: bool = False,
        exclude_aggregates: bool | None = None,
    ) -> Series:
        """
        Retrieve data for a single indicator as a pandas Series.

        If pandas is not installed, a RuntimeError will be raised.

        Parameters:
            indicator: the desired indicator code
            country: a country code, sequence of country codes, or "all" (default).
                Also accepts special strings "countries" / "countries_only" (exclude
                aggregates) and "sovereign" (sovereign countries only).
            date: the desired date as a string, datetime object or a 2-tuple
                with start and end dates
            freq: the desired periodicity of the data, one of 'Y' (yearly), 'M'
                (monthly), or 'Q' (quarterly). The indicator may or may not
                support the specified frequency.
            source: the specific source to retrieve data from (defaults on API
                to 2, World Development Indicators)
            parse_dates: if True, convert date field to a datetime.datetime
                object.
            name: the desired name for the pandas Series
            keep_levels: if True don't reduce the number of index
                levels returned if only getting one date or country
            skip_cache: bypass the cache when downloading
            include_aggregates: if False, exclude aggregate regions and groups
                from the returned data. Defaults to True.
            include_non_sovereign: if False, exclude non-sovereign
                countries/territories from the returned data. Defaults to True.
            sovereign_only: if True, exclude both aggregates and non-sovereign
                countries. Defaults to False.
            exclude_aggregates: if specified, sets include_aggregates to its negation.

        Returns:
            Series with the requested data. The index of the series depends on
                the data returned and the specified options. If the data spans
                multiple dates and countries or if `keep_levels` is `True`, the
                index will be a 2-level MultiIndex with levels "country" and
                "name". If `keep_levels` is `False` (the default) and the data
                only has one country or date, the level with only one value
                will be dropped. If `keep_levels` is `False` and both levels
                only have one value, the country level is dropped.
        """
        extra_kwargs: dict[str, Any] = {}
        if not include_aggregates:
            extra_kwargs["include_aggregates"] = include_aggregates
        if not include_non_sovereign:
            extra_kwargs["include_non_sovereign"] = include_non_sovereign
        if sovereign_only:
            extra_kwargs["sovereign_only"] = sovereign_only
        if exclude_aggregates is not None:
            extra_kwargs["exclude_aggregates"] = exclude_aggregates

        raw_data = self.get_data(
            indicator=indicator,
            country=country,
            date=date,
            freq=freq,
            source=source,
            parse_dates=parse_dates,
            skip_cache=skip_cache,
            **extra_kwargs,
        )
        df = pd.DataFrame(
            [[i["country"]["value"], i["date"], i["value"]] for i in raw_data],
            columns=["country", "date", name],
        )
        df[name] = df[name].map(_cast_float)
        if not keep_levels and len(df["country"].unique()) == 1:
            df = df.set_index("date")
        elif not keep_levels and len(df["date"].unique()) == 1:
            df = df.set_index("country")
        else:
            df = df.set_index(["country", "date"])
        return Series(df[name], last_updated=getattr(raw_data, "last_updated", None))

    @needs_pandas
    def get_dataframe(
        self,
        indicators: dict[str, str],
        country: str | Sequence[str] = "all",
        date: str
        | dt.datetime
        | tuple[str | dt.datetime, str | dt.datetime]
        | None = None,
        freq: str = "Y",
        source: int | str | Sequence[int | str] | None = None,
        parse_dates: bool = False,
        keep_levels: bool = False,
        skip_cache: bool = False,
        include_aggregates: bool = True,
        include_non_sovereign: bool = True,
        sovereign_only: bool = False,
        exclude_aggregates: bool | None = None,
    ) -> DataFrame:
        """
        Download a set of indicators and merge them into a pandas DataFrame.

        If pandas is not installed, a RuntimeError will be raised.

        Parameters:
            indicators: A dictionary where the keys are desired indicators and the
                values are the desired column names
            country: a country code, sequence of country codes, or "all" (default).
                Also accepts special strings "countries" / "countries_only" (exclude
                aggregates) and "sovereign" (sovereign countries only).
            date: the desired date as a string, datetime object or a 2-tuple
                with start and end dates
            freq: the desired periodicity of the data, one of 'Y' (yearly), 'M'
                (monthly), or 'Q' (quarterly). The indicator may or may not
                support the specified frequency.
            source: the specific source to retrieve data from (defaults on API
                to 2, World Development Indicators)
            parse_dates: if True, convert date field to a datetime.datetime
                object.
            keep_levels: if True don't reduce the number of index
                levels returned if only getting one date or country
            skip_cache: bypass the cache when downloading
            include_aggregates: if False, exclude aggregate regions and groups
                from the returned data. Defaults to True.
            include_non_sovereign: if False, exclude non-sovereign
                countries/territories from the returned data. Defaults to True.
            sovereign_only: if True, exclude both aggregates and non-sovereign
                countries. Defaults to False.
            exclude_aggregates: if specified, sets include_aggregates to its negation.

        Returns:
            DataFrame with one column per indicator. The index of the DataFrame
                depends on the data returned and the specified options. If the
                data spans multiple dates and countries or if `keep_levels` is
                `True`, the index will be a 2-level MultiIndex with levels
                "country" and "name". If `keep_levels` is `False` (the default)
                and the data only has one country or date, the level with only
                one value will be dropped. If `keep_levels` is `False` and both
                levels only have one value, the country level is dropped.

        """
        extra_kwargs: dict[str, Any] = {}
        if not include_aggregates:
            extra_kwargs["include_aggregates"] = include_aggregates
        if not include_non_sovereign:
            extra_kwargs["include_non_sovereign"] = include_non_sovereign
        if sovereign_only:
            extra_kwargs["sovereign_only"] = sovereign_only
        if exclude_aggregates is not None:
            extra_kwargs["exclude_aggregates"] = exclude_aggregates

        df = DataFrame(
            serieses={
                name: self.get_series(
                    indicator=indicator,
                    country=country,
                    date=date,
                    freq=freq,
                    source=source,
                    parse_dates=parse_dates,
                    keep_levels=True,
                    skip_cache=skip_cache,
                    **extra_kwargs,
                )
                for indicator, name in indicators.items()
            }
        )
        if (
            not keep_levels
            and isinstance(df.index, pd.MultiIndex)
            and len(df.index) > 0
        ):
            if len(set(df.index.get_level_values(0))) == 1:
                df.index = df.index.droplevel(0)
            elif len(set(df.index.get_level_values(1))) == 1:
                df.index = df.index.droplevel(1)
        return df
