# This module wraps the reference 'affected people' script into a reusable
# package. It exposes the original functions and configuration as importable
# objects so that an interactive application can call them directly. The code
# below is largely identical to the reference implementation and retains all
# comments for clarity.

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lxml import etree

__all__ = [
    "Config",
    "CFG",
    "load_desinventar_xml",
    "clean_desinventar",
    "aggregate_desinventar_events",
    "add_event_affected_people",
    "build_desinventar_annual_people",
    "load_emdat_annual_people",
    "combine_annual_sources",
    "get_user_defined_poverty_scenario",
    "add_poverty_scenario_columns",
    "get_scenario_rates",
    "add_scenario_columns",
    "build_annual_exceedance_curve",
    "simulate_catalogues",
    "calculate_metrics",
    "build_scenario_outputs",
    "plot_dashboard_lec",
    "plot_dashboard_histograms",
    "plot_comparative_dashboard",
]


@dataclass(frozen=True)
class Config:
    """Configuration options controlling the analysis.

    Parameters are set with sensible defaults. To customise a run, create a new
    instance of this class and assign it to `CFG` before calling any of the
    functions below. The functions refer to the global `CFG` object to pick
    up updated settings.
    """

    country: str = "DOM"
    poverty_rate: float = 16.15
    household_size: float = 2.8
    # Additional user defined parameter controlling the vulnerability of the
    # population. This is analogous to the poverty rate: a fraction or
    # percentage that represents the proportion of people considered
    # vulnerable. The default of 20 means 20% of the affected people are
    # classified as vulnerable unless the user overrides it.
    vulnerability_rate: float = 20.0
    # A generic scenario name. Historically this represented the poverty
    # scenario but with the introduction of multiple impact scenarios it
    # no longer drives the core logic. The application code may still
    # override this to label a custom scenario for backwards compatibility.
    scenario_name: str = "user_defined"
    start_year: int = 1980
    catalogue_length_years: int = 5
    simulation_number: int = 1000
    random_seed: int = 1
    export_outputs: bool = True
    make_dashboard: bool = True
    save_figures: bool = False
    base_dir: Path = Path.cwd().parent
    output_dir: Path = Path.cwd()

    @property
    def desinventar_path(self) -> Path:
        return self.base_dir / "01 - DesInventar" / f"DI_export_{self.country.lower()}.xml"

    @property
    def emdat_path(self) -> Path:
        return self.base_dir / "02 - Codigo" / "EM-DAT.xlsx"

    @property
    def figure_dir(self) -> Path:
        return self.output_dir / "figures"


# Create a default configuration and some associated globals. External code can
# override `CFG` before calling functions to adjust behaviour.
CFG: Config = Config()
# Do not create a figures folder at import time. Figures are displayed in Streamlit only.

# ----------------------------------------------------------------------------
# Event classification and aggregation settings
# ----------------------------------------------------------------------------

# List of event names to retain from the DesInventar data. Only records with
# `evento` values present in this list will be processed.
EVENTS_TO_KEEP = [
    # Geophysical
    'Actividad Volcánica',
    'ACTIVIDAD VOLCÁNICA',
    'Flujo Lodo',
    'HUNDIMIENTO',
    'Lahares',
    'Licuación',
    'Sismo',
    'SISMO',
    'Tsunami',
    'TSUNAMI',

    # Hydrological
    'Alud',
    'Aluvión',
    'ALUVIÓN',
    'Avenida torrencial',
    'Cambio línea de costa',
    'Desbordamiento',
    'Deslizamiento',
    'DESLIZAMIENTO',
    'Inundación',
    'INUNDACIÓN',
    'Inundación gradual',
    'Inundación repentina',
    'Lluvias',
    'Marejada',
    'OLEAJE',
    'Riada',
    'Sedimentación',
    'SOCAVAMIENTO',

    # Meteorological
    'Huracán',
    'Tempestad',
    'Tormenta',
    'Tormenta eléctrica',
    'TORMENTA ELÉCTRICA',
    'Tormenta Tropical',
    'Tornado',
    'Tromba marina',
    'Vendaval',
    'VENDAVAL',
    'Vientos fuertes',

    # Climatological
    'DÉFICIT HÍDRICO',
    'Granizada',
    'GRANIZADA',
    'Helada',
    'HELADA',
    'Incendio',
    'INCENDIO ESTRUCTURAL',
    'Incendio de campo',
    'Incendio de interfase',
    'Incendio forestal',
    'INCENDIO FORESTAL',
    'Incendio urbano',
    'Incendios forestales',
    'Neblina',
    'Nevada',
    'Ola de calor',
    'Ola de frío',
    'Sequía',
]

# Mapping of high‑level causes to their associated event names. This is used
# when aggregating events into broader hazard categories.
CAUSE_DICT = {
    'Geophysical': [
        'Actividad Volcánica',
        'ACTIVIDAD VOLCÁNICA',
        'Flujo Lodo',
        'HUNDIMIENTO',
        'Lahares',
        'Licuación',
        'Sismo',
        'SISMO',
        'Tsunami',
        'TSUNAMI',
    ],

    'Hydrological': [
        'Alud',
        'Aluvión',
        'ALUVIÓN',
        'Avenida torrencial',
        'Cambio línea de costa',
        'Desbordamiento',
        'Deslizamiento',
        'DESLIZAMIENTO',
        'Inundación',
        'INUNDACIÓN',
        'Inundación gradual',
        'Inundación repentina',
        'Lluvias',
        'Marejada',
        'OLEAJE',
        'Riada',
        'Sedimentación',
        'SOCAVAMIENTO',
    ],

    'Meteorological': [
        'Huracán',
        'Tempestad',
        'Tormenta',
        'Tormenta eléctrica',
        'TORMENTA ELÉCTRICA',
        'Tormenta Tropical',
        'Tornado',
        'Tromba marina',
        'Vendaval',
        'VENDAVAL',
        'Vientos fuertes',
    ],

    'Climatological': [
        'DÉFICIT HÍDRICO',
        'Granizada',
        'GRANIZADA',
        'Helada',
        'HELADA',
        'Incendio',
        'INCENDIO ESTRUCTURAL',
        'Incendio de campo',
        'Incendio de interfase',
        'Incendio forestal',
        'INCENDIO FORESTAL',
        'Incendio urbano',
        'Incendios forestales',
        'Neblina',
        'Nevada',
        'Ola de calor',
        'Ola de frío',
        'Sequía',
    ],
}

# Reverse mapping from individual event names back to the high‑level cause.
EVENT_TO_CAUSE = {
    event: cause
    for cause, events in CAUSE_DICT.items()
    for event in events
}

# Time windows used to cluster events of the same cause. Events occurring
# within the specified time window of each other will be grouped into a
# single aggregated event. Different hazard categories have different
# characteristic durations, reflected in these windows.
AGGREGATION_WINDOWS = {
    "Meteorological": pd.Timedelta(days=5),
    "Hydrological": pd.Timedelta(days=2),
    "Climatological": pd.Timedelta(days=15),
    "Geophysical": pd.Timedelta(days=3),
    "Other": pd.Timedelta(days=7),
}

# Columns in the DesInventar data that capture people affected in various ways.
PEOPLE_COLUMNS = ["muertos", "heridos", "desaparece", "afectados", "vivdest", "vivafec"]

# Scenario handling. By default, three impact scenarios are defined. These
# represent the baseline number of affected people ("Affected"), the
# subset who are poor ("Affected Poor"), and the subset who are
# vulnerable ("Affected Vulnerable"). External code may override the
# lists and dictionaries to customise colours or add additional
# scenarios dynamically.
SCENARIOS = ["Affected", "Affected Poor", "Affected Vulnerable"]
SCENARIO_LABELS = {
    "Affected": "Affected",
    "Affected Poor": "Affected Poor",
    "Affected Vulnerable": "Affected Vulnerable",
}
SCENARIO_COLORS = {
    "Affected": "tab:blue",
    "Affected Poor": "tab:orange",
    "Affected Vulnerable": "tab:green",
}


def load_desinventar_xml(file_path: Path) -> pd.DataFrame:
    """Parse a DesInventar XML export and return it as a DataFrame."""
    tree = etree.parse(str(file_path))
    records = tree.getroot().find("fichas").findall("TR")
    return pd.DataFrame([
        {child.tag: child.text for child in record}
        for record in records
    ])


def clean_desinventar(df: pd.DataFrame) -> pd.DataFrame:
    """Filter and clean raw DesInventar data."""
    cols_to_keep = [
        "serial", "level0", "level1", "name0", "name1", "evento",
        "fechano", "fechames", "fechadia", *PEOPLE_COLUMNS,
    ]
    clean = df[cols_to_keep].copy()
    clean = clean.loc[clean["evento"].isin(EVENTS_TO_KEEP)].copy()
    for col in PEOPLE_COLUMNS:
        clean[col] = pd.to_numeric(clean[col], errors="coerce").fillna(0)
    # Drop records where nobody was affected
    clean = clean.loc[clean[PEOPLE_COLUMNS].sum(axis=1) > 0].copy()
    clean["cause"] = clean["evento"].map(EVENT_TO_CAUSE).fillna("Other")
    # Replace missing or zero month/day with 1
    clean[["fechames", "fechadia"]] = (
        clean[["fechames", "fechadia"]]
        .replace({"0": "1", 0: 1})
        .fillna(1)
    )
    clean["date"] = pd.to_datetime(
        clean["fechano"].astype(str)
        + "-"
        + clean["fechames"].astype(str)
        + "-"
        + clean["fechadia"].astype(str),
        format="%Y-%m-%d",
        errors="coerce",
    )
    return clean.dropna(subset=["date"]).copy()


def summarize_event_group(group: list, cause: str) -> dict:
    """Summarise a group of raw events into a single aggregated event."""
    out: dict[str, int | str | pd.Timestamp] = defaultdict(int)
    out["cause"] = cause
    out["start_date"] = group[0].date
    out["end_date"] = group[-1].date
    out["total_records"] = len(group)
    for row in group:
        for col in PEOPLE_COLUMNS:
            out[f"total_{col}"] += int(getattr(row, col, 0))
    return dict(out)


def aggregate_desinventar_events(df: pd.DataFrame) -> pd.DataFrame:
    """Group individual DesInventar events into aggregated events."""
    rows: list[dict] = []
    for cause, cause_df in df.groupby("cause", observed=True):
        cause_df = cause_df.sort_values("date")
        window = AGGREGATION_WINDOWS.get(cause, AGGREGATION_WINDOWS["Other"])
        current_group: list = []
        group_start: pd.Timestamp | None = None
        for row in cause_df.itertuples(index=False):
            if group_start is None:
                current_group = [row]
                group_start = row.date
                continue
            if row.date - group_start <= window:
                current_group.append(row)
            else:
                rows.append(summarize_event_group(current_group, cause))
                current_group = [row]
                group_start = row.date
        if current_group:
            rows.append(summarize_event_group(current_group, cause))
    return pd.DataFrame(rows)


def add_event_affected_people(event_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the total number of affected people for each aggregated event."""
    df = event_df.copy()
    df["year"] = df["start_date"].dt.year
    df["affected_people"] = (
        df["total_vivdest"] * CFG.household_size
        + df["total_vivafec"] * CFG.household_size
    )
    return df


def build_desinventar_annual_people(event_df: pd.DataFrame) -> pd.DataFrame:
    """Sum aggregated event impacts by year to form an annual time series."""
    return (
        event_df.groupby("year", as_index=False, observed=True)["affected_people"]
        .sum()
        .rename(columns={"affected_people": "DesInventar_Affected"})
    )


def load_emdat_annual_people(file_path: Path, country: str) -> pd.DataFrame:
    """Load EM‑DAT data and extract the annual number of affected people."""
    emdat = pd.read_excel(file_path)
    emdat_people = emdat.loc[
        emdat["ISO"] == country,
        ["Start Year", "No. Affected"],
    ].copy()
    emdat_people = emdat_people.rename(
        columns={
            "Start Year": "year",
            "No. Affected": "EM-DAT_Affected",
        }
    )
    emdat_people["year"] = pd.to_numeric(emdat_people["year"], errors="coerce")
    emdat_people["EM-DAT_Affected"] = (
        pd.to_numeric(emdat_people["EM-DAT_Affected"], errors="coerce")
        .fillna(0)
    )
    return (
        emdat_people.dropna(subset=["year"])
        .assign(year=lambda x: x["year"].astype(int))
        .groupby("year", as_index=False)["EM-DAT_Affected"]
        .sum()
    )


def combine_annual_sources(
    di_annual: pd.DataFrame,
    emdat_annual: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame:
    """Merge DesInventar and EM‑DAT annual series and take the maximum."""
    merged = (
        di_annual.merge(emdat_annual, on="year", how="outer")
        .fillna(0)
        .sort_values("year")
        .reset_index(drop=True)
    )
    merged["year"] = merged["year"].astype(int)
    first_year = max(start_year, int(merged["year"].min()))
    last_year = int(merged["year"].max())
    all_years = pd.DataFrame({
        "year": np.arange(first_year, last_year + 1)
    })
    merged = all_years.merge(merged, on="year", how="left").fillna(0)
    merged["Affected_People_Max"] = np.maximum(
        merged.get("DesInventar_Affected", 0),
        merged.get("EM-DAT_Affected", 0),
    )
    return merged


def get_user_defined_poverty_scenario() -> dict[str, float]:
    """Return a dictionary mapping the current scenario to the configured rate."""
    rate = CFG.poverty_rate
    if rate > 1:
        rate = rate / 100
    if not (0 <= rate <= 1):
        raise ValueError(
            "poverty_rate must be between 0 and 1, or between 0 and 100 if entered as percent."
        )
    return {CFG.scenario_name: float(rate)}


def get_scenario_rates() -> dict[str, float]:
    """
    Construct a dictionary mapping impact scenario names to their associated
    multiplicative rates. The returned dictionary always includes three
    scenarios:

    - ``Affected``: Represents the baseline number of affected people. The
      associated rate is always ``1.0``.
    - ``Affected Poor``: Represents the subset of affected people who are
      classified as poor. The rate is derived from ``CFG.poverty_rate``. If
      the poverty rate is supplied as a percentage (>1), it will be
      converted to a fraction. The value must lie between 0 and 1.
    - ``Affected Vulnerable``: Represents the subset of affected people who
      are classified as vulnerable. The rate is derived from
      ``CFG.vulnerability_rate``. If the vulnerability rate is supplied as a
      percentage (>1), it will be converted to a fraction. The value must
      also lie between 0 and 1.

    Returns
    -------
    dict[str, float]
        Mapping from scenario name to rate.

    Raises
    ------
    ValueError
        If either the poverty or vulnerability rates are outside the
        acceptable range [0, 1] or [0, 100] if given as a percentage.
    """
    rates: dict[str, float] = {}
    # Baseline scenario: all affected people
    rates["Affected"] = 1.0
    # Poverty scenario
    p_rate = CFG.poverty_rate
    if p_rate > 1:
        p_rate = p_rate / 100.0
    if not (0.0 <= p_rate <= 1.0):
        raise ValueError(
            "poverty_rate must be between 0 and 1, or between 0 and 100 if entered as a percent."
        )
    rates["Affected Poor"] = float(p_rate)
    # Vulnerability scenario
    v_rate = CFG.vulnerability_rate
    if v_rate > 1:
        v_rate = v_rate / 100.0
    if not (0.0 <= v_rate <= 1.0):
        raise ValueError(
            "vulnerability_rate must be between 0 and 1, or between 0 and 100 if entered as a percent."
        )
    rates["Affected Vulnerable"] = float(v_rate)
    return rates


def add_scenario_columns(
    annual_df: pd.DataFrame,
    scenario_rates: dict[str, float],
) -> pd.DataFrame:
    """
    Apply scenario rates to the annual maximum affected people series.

    This generalises the poverty scenario computation by allowing an
    arbitrary mapping of scenario names to their multiplicative rates. For
    each scenario in ``scenario_rates``, this function creates a new
    column in ``annual_df`` named ``Affected_People_<scenario>`` (spaces in
    the scenario name are replaced by underscores) that contains the
    product of ``Affected_People_Max`` and the scenario rate.

    Parameters
    ----------
    annual_df : pandas.DataFrame
        DataFrame containing the ``Affected_People_Max`` column.
    scenario_rates : dict[str, float]
        Mapping from scenario name to multiplicative rate.

    Returns
    -------
    pandas.DataFrame
        DataFrame with additional columns for each scenario.
    """
    df = annual_df.copy()
    for scenario, rate in scenario_rates.items():
        # Sanitize column name by replacing spaces with underscores
        col_suffix = scenario.replace(" ", "_")
        df[f"Affected_People_{col_suffix}"] = df["Affected_People_Max"] * rate
    return df


def add_poverty_scenario_columns(
    annual_df: pd.DataFrame,
    poverty_scenarios: dict[str, float],
) -> pd.DataFrame:
    """
    Backwards compatible wrapper for applying poverty scenarios. This
    function delegates to :func:`add_scenario_columns`. The name is
    retained for compatibility with earlier versions of the module that
    only supported poverty scenarios. Each key in ``poverty_scenarios``
    corresponds to a scenario name; the values are multiplicative rates.

    Parameters
    ----------
    annual_df : pandas.DataFrame
        DataFrame containing the ``Affected_People_Max`` column.
    poverty_scenarios : dict[str, float]
        Mapping from scenario name to multiplicative rate. Historically
        these represented poverty scenarios, but any scenario is accepted.

    Returns
    -------
    pandas.DataFrame
        DataFrame with additional scenario columns.
    """
    return add_scenario_columns(annual_df, poverty_scenarios)


def build_annual_exceedance_curve(
    annual_df: pd.DataFrame,
    value_col: str,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Construct an annual exceedance curve from a series of values."""
    values = np.sort(annual_df[value_col].to_numpy(dtype=float))[::-1]
    valid_years = int(
        annual_df["year"].max() - annual_df["year"].min() + 1
    )
    frequency = np.arange(1, len(values) + 1) / valid_years
    lec = pd.DataFrame({
        "annual_affected_people": values,
        "annual_frequency_exceedance": frequency,
    })
    return lec, values, frequency


def simulate_catalogues(
    sorted_annual_values: np.ndarray,
    frequency: np.ndarray,
    catalogue_length: int,
    simulation_number: int,
    random_seed: int,
) -> pd.DataFrame:
    """Generate synthetic catalogues by sampling from the exceedance curve."""
    rng = np.random.default_rng(random_seed)
    lambda_min = np.max(frequency)
    cdf_values = 1 - frequency / lambda_min
    cdf_values += np.arange(1, len(cdf_values) + 1) * np.finfo(float).eps
    people_sorted = sorted_annual_values[::-1]
    cdf_sorted = cdf_values[::-1]
    random_values = rng.random((catalogue_length, simulation_number))
    catalogue = np.interp(
        random_values,
        cdf_sorted,
        people_sorted,
        left=people_sorted[0],
        right=people_sorted[-1],
    )
    synthetic = pd.DataFrame(
        catalogue.T,
        columns=[f"Year_{i + 1}" for i in range(catalogue_length)],
    )
    synthetic[f"Total_{catalogue_length}yr_Affected_People"] = synthetic.sum(axis=1)
    return synthetic


def calculate_metrics(
    annual_df: pd.DataFrame,
    annual_values: np.ndarray,
    synthetic_df: pd.DataFrame,
    catalogue_length: int,
    scenario: str,
    poverty_rate: float,
) -> pd.DataFrame:
    """Compute summary statistics for a given scenario."""
    total_col = f"Total_{catalogue_length}yr_Affected_People"
    valid_years = int(
        annual_df["year"].max() - annual_df["year"].min() + 1
    )
    metrics = {
        "country": CFG.country,
        "poverty_scenario": scenario,
        "poverty_rate_applied": poverty_rate,
        "household_size_applied": CFG.household_size,
        "start_year": int(annual_df["year"].min()),
        "end_year": int(annual_df["year"].max()),
        "valid_timeframe_years": valid_years,
        "years_with_affected_people": int((annual_values > 0).sum()),
        "average_annual_affected_people": int(np.ceil(annual_values.sum() / valid_years)),
        "median_annual_affected_people": int(np.ceil(np.median(annual_values))),
        "p16_annual_affected_people": int(np.ceil(np.percentile(annual_values, 16))),
        "p84_annual_affectedr_people": int(np.ceil(np.percentile(annual_values, 84))),
        "max_annual_affected_people": int(np.ceil(np.max(annual_values))),
        f"mean_{catalogue_length}yr_simulated_affected_people": int(np.ceil(synthetic_df[total_col].mean())),
        f"median_{catalogue_length}yr_simulated_affected_people": int(np.ceil(synthetic_df[total_col].median())),
        f"p16_{catalogue_length}yr_simulated_affected_people": int(np.ceil(np.percentile(synthetic_df[total_col], 16))),
        f"p84_{catalogue_length}yr_simulated_affected_people": int(np.ceil(np.percentile(synthetic_df[total_col], 84))),
        f"max_{catalogue_length}yr_simulated_affected_people": int(np.ceil(synthetic_df[total_col].max())),
    }
    return pd.DataFrame([metrics])


def build_scenario_outputs(
    annual_df: pd.DataFrame,
    poverty_scenarios: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Generate exceedance curves, synthetic catalogues and summary metrics for
    each impact scenario.

    Parameters
    ----------
    annual_df : pandas.DataFrame
        DataFrame containing the annual maximum affected people series and
        scenario columns (e.g. ``Affected_People_Affected``).
    poverty_scenarios : dict[str, float]
        Mapping from scenario name to multiplicative rate. The name of this
        argument is retained for backwards compatibility but it now
        represents generic impact scenarios. The function iterates over
        all keys in this dictionary rather than using the global
        ``SCENARIOS`` list, allowing the caller to specify which
        scenarios to compute.

    Returns
    -------
    tuple of pandas.DataFrame
        A tuple ``(lec_df, synthetic_df, metrics_df)`` where:

        * ``lec_df`` is the concatenated exceedance curve data for each
          scenario.
        * ``synthetic_df`` is the concatenated synthetic catalogue data
          for each scenario.
        * ``metrics_df`` is the concatenated summary metrics for each
          scenario.
    """
    lec_outputs: list[pd.DataFrame] = []
    synthetic_outputs: list[pd.DataFrame] = []
    metrics_outputs: list[pd.DataFrame] = []
    # Iterate over the scenario mapping instead of the global SCENARIOS list
    for scenario in poverty_scenarios.keys():
        # Sanitize column suffix
        col_suffix = scenario.replace(" ", "_")
        value_col = f"Affected_People_{col_suffix}"
        lec, annual_values, frequency = build_annual_exceedance_curve(
            annual_df,
            value_col,
        )
        if len(annual_values) == 0 or annual_values.sum() == 0:
            raise ValueError(
                f"No affected people values available for scenario: {scenario}"
            )
        synthetic = simulate_catalogues(
            sorted_annual_values=annual_values,
            frequency=frequency,
            catalogue_length=CFG.catalogue_length_years,
            simulation_number=CFG.simulation_number,
            random_seed=CFG.random_seed,
        )
        # Record scenario and applied rate in outputs. The column names are
        # retained for backwards compatibility but now represent generic
        # scenarios.
        lec["poverty_scenario"] = scenario
        lec["poverty_rate_applied"] = poverty_scenarios[scenario]
        synthetic.insert(0, "poverty_scenario", scenario)
        synthetic.insert(1, "poverty_rate_applied", poverty_scenarios[scenario])
        metrics = calculate_metrics(
            annual_df=annual_df,
            annual_values=annual_values,
            synthetic_df=synthetic,
            catalogue_length=CFG.catalogue_length_years,
            scenario=scenario,
            poverty_rate=poverty_scenarios[scenario],
        )
        lec_outputs.append(lec)
        synthetic_outputs.append(synthetic)
        metrics_outputs.append(metrics)
    return (
        pd.concat(lec_outputs, ignore_index=True),
        pd.concat(synthetic_outputs, ignore_index=True),
        pd.concat(metrics_outputs, ignore_index=True),
    )


# Plotting helpers

def plot_dashboard_lec(
    ax: plt.Axes,
    lec_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    *,
    scenario: str | None = None,
) -> None:
    """
    Plot the exceedance curve for one or more scenarios on the given axes.

    If ``scenario`` is provided, only that scenario's curve and associated
    annotations are plotted. Otherwise, all scenarios listed in
    ``SCENARIOS`` are drawn. This behaviour helps avoid overlapping
    curves when the caller wishes to display a single scenario per
    figure.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes on which to draw the exceedance curve(s).
    lec_df : pandas.DataFrame
        DataFrame containing the exceedance curve data with columns
        ``annual_affected_people``, ``annual_frequency_exceedance`` and
        ``poverty_scenario``.
    metrics_df : pandas.DataFrame
        DataFrame containing summary metrics for each scenario. Used
        to annotate the average annual affected people, household size
        and applied rate.
    scenario : str, optional (keyword-only)
        The name of a single scenario to plot. If ``None`` (default),
        all scenarios in ``SCENARIOS`` are plotted.
    """
    # Determine which scenarios to plot
    scenarios_to_plot = [scenario] if scenario else SCENARIOS
    for sc in scenarios_to_plot:
        plot_df = lec_df.loc[
            (lec_df["poverty_scenario"] == sc)
            & (lec_df["annual_affected_people"] > 0)
            & (lec_df["annual_frequency_exceedance"] > 0)
        ]
        if plot_df.empty:
            continue
        color = SCENARIO_COLORS.get(sc, "tab:blue")
        ax.plot(
            plot_df["annual_affected_people"],
            plot_df["annual_frequency_exceedance"],
            linewidth=2,
            color=color,
            label=SCENARIO_LABELS.get(sc, sc),
        )
        # Fetch metrics for this scenario
        avg_value = metrics_df.loc[
            metrics_df["poverty_scenario"] == sc,
            "average_annual_affected_people",
        ].iloc[0]
        rate_value = metrics_df.loc[
            metrics_df["poverty_scenario"] == sc,
            "poverty_rate_applied",
        ].iloc[0]
        household_size = metrics_df.loc[
            metrics_df["poverty_scenario"] == sc,
            "household_size_applied",
        ].iloc[0]
        ax.axvline(
            avg_value,
            color=color,
            linestyle="--",
            linewidth=1.8,
        )
        ax.text(
            avg_value,
            0.05,
            (
                f"Average annual affected people\n"
                f"{avg_value:,.0f}\n\n"
                f"Average household composition\n"
                f"{household_size:,.1f} people/household\n\n"
                f"Rate used\n"
                f"{rate_value:.1%}"
            ),
            rotation=0,
            va="top",
            ha="right",
            fontsize=9,
            color=color,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_title("Affected People Exceedance Curve", fontweight="bold")
    ax.set_xlabel("Affected People")
    ax.set_ylabel("Annual Probability of Exceedance")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.6)
    # Only show legend if multiple scenarios are plotted
    if len(scenarios_to_plot) > 1:
        ax.legend(loc="lower left", frameon=True)


def plot_dashboard_histograms(
    ax: plt.Axes,
    synthetic_df: pd.DataFrame,
    *,
    scenario: str | None = None,
) -> None:
    """
    Plot the histogram of total affected people across simulations for a
    given scenario.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes on which to draw the histogram.
    synthetic_df : pandas.DataFrame
        DataFrame containing a column ``Total_<N>yr_Affected_People`` and
        optionally ``poverty_scenario``. If the DataFrame contains
        multiple scenarios, the caller should provide the ``scenario``
        argument to select the appropriate subset. If ``scenario`` is
        ``None``, the function will use ``CFG.scenario_name`` to determine
        the scenario and plot all rows in ``synthetic_df``.
    scenario : str, optional (keyword-only)
        Name of the scenario to plot. If provided, the DataFrame will be
        filtered to rows where ``synthetic_df['poverty_scenario'] == scenario``.

    Returns
    -------
    None
    """
    total_col = f"Total_{CFG.catalogue_length_years}yr_Affected_People"
    # Filter by scenario if necessary
    df = synthetic_df
    if scenario is None:
        scenario = CFG.scenario_name
    else:
        # If the column is present, filter by scenario name
        if "poverty_scenario" in synthetic_df.columns:
            df = synthetic_df.loc[synthetic_df["poverty_scenario"] == scenario]
    values = df[total_col].to_numpy(dtype=float)
    if len(values) == 0:
        # Nothing to plot
        return
    mean_value = values.mean()
    median_value = np.median(values)
    p16_value = np.percentile(values, 16)
    p84_value = np.percentile(values, 84)
    color = SCENARIO_COLORS.get(scenario, "tab:blue")
    ax.hist(values, bins=35, color=color, edgecolor="black", alpha=0.72)
    ax.axvline(median_value, color=color, linestyle="-", linewidth=2)
    ax.axvline(mean_value, color=color, linestyle="--", linewidth=2)
    ax.axvline(p16_value, color=color, linestyle=":", linewidth=2)
    ax.axvline(p84_value, color=color, linestyle=":", linewidth=2)
    ax.set_title(
        f"Distribution of Total Affected People over {CFG.catalogue_length_years} Years",
        fontweight="bold",
    )
    ax.set_xlabel(f"Total Affected People over {CFG.catalogue_length_years} Years")
    ax.set_ylabel("Number of Simulations")
    ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.55)
    ax.set_axisbelow(True)
    ax.text(
        0.50,
        0.93,
        (
            f"Mean = {mean_value:,.0f}\n"
            f"Median = {median_value:,.0f}\n"
            f"16th percentile = {p16_value:,.0f}\n"
            f"84th percentile = {p84_value:,.0f}"
        ),
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        color=color,
    )


def plot_comparative_dashboard(
    annual_df: pd.DataFrame,
    lec_df: pd.DataFrame,
    synthetic_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
) -> Path | None:
    """Render both the LEC curve and histogram into a single figure."""
    fig = plt.figure(figsize=(16, 7))
    grid = fig.add_gridspec(
        1,
        2,
        left=0.07,
        right=0.98,
        bottom=0.12,
        top=0.88,
        wspace=0.22,
    )
    plot_dashboard_lec(fig.add_subplot(grid[0, 0]), lec_df, metrics_df)
    plot_dashboard_histograms(fig.add_subplot(grid[0, 1]), synthetic_df)
    fig.suptitle(
        "Affected People: LEC Curve and Simulation Distribution",
        fontsize=15,
        fontweight="bold",
    )
    # Figures are intentionally not saved to disk.
    # The Streamlit app renders figures in memory with st.pyplot(fig).
    return None
