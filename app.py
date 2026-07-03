"""
Streamlit application for multi-country, multi-scenario affected people analysis.

Run locally with:
    streamlit run app.py

Required packages:
    pip install streamlit pandas numpy matplotlib plotly lxml openpyxl
"""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st

import affected_poor_script as aps


IDB_SCENARIO_COLORS = {
    "Affected": "#0F5B9A",
    "Affected Poor": "#8BC5E8",
    "Affected Vulnerable": "#A8D5BA",
}

IDB_SERIES_COLORS = {
    "DesInventar": "#8BC5E8",
    "EM-DAT": "#A8D5BA",
    "Maximum source value": "#0F5B9A",
}


def get_scenario_color(scenario: str) -> str:
    """Return a Plotly-compatible HEX color for each scenario."""
    return IDB_SCENARIO_COLORS.get(scenario, "#0F5B9A")


AMERICAS_ISO3 = [
    "CAN", "USA", "MEX", "GTM", "BLZ", "SLV", "HND", "NIC", "CRI", "PAN",
    "CUB", "HTI", "DOM", "JAM", "TTO", "BRB", "BHS", "ATG", "DMA", "GRD",
    "KNA", "LCA", "VCT",
    "COL", "VEN", "GUY", "SUR", "ECU", "PER", "BRA", "BOL", "PRY", "URY",
    "ARG", "CHL",
]


@st.cache_data(show_spinner="Processing analysis...")
def run_country_analysis(
    country: str,
    poverty_rate: float,
    vulnerability_rate: float,
    household_size: float,
    start_year: int,
    catalogue_length_years: int,
    simulation_number: int,
    random_seed: int,
    des_file_bytes: bytes,
    em_file_bytes: bytes,
) -> dict:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp_di:
        tmp_di.write(des_file_bytes)
        tmp_di_path = Path(tmp_di.name)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_em:
        tmp_em.write(em_file_bytes)
        tmp_em_path = Path(tmp_em.name)

    cfg_obj = aps.Config(
        country=country.strip().upper(),
        poverty_rate=float(poverty_rate),
        vulnerability_rate=float(vulnerability_rate),
        household_size=float(household_size),
        scenario_name="user_defined",
        start_year=int(start_year),
        catalogue_length_years=int(catalogue_length_years),
        simulation_number=int(simulation_number),
        random_seed=int(random_seed),
        export_outputs=False,
        make_dashboard=False,
        save_figures=False,
        base_dir=Path("."),
        output_dir=Path("."),
    )

    aps.CFG = cfg_obj

    scenario_rates = aps.get_scenario_rates()

    aps.SCENARIOS = list(scenario_rates.keys())
    aps.SCENARIO_LABELS = {sc: sc for sc in scenario_rates.keys()}
    aps.SCENARIO_COLORS = IDB_SCENARIO_COLORS.copy()

    di_df_raw = aps.load_desinventar_xml(tmp_di_path)
    di_df = aps.clean_desinventar(di_df_raw)
    aggregated = aps.aggregate_desinventar_events(di_df)
    with_af = aps.add_event_affected_people(aggregated)

    with_af = with_af.loc[
        (with_af["year"] >= cfg_obj.start_year)
        & (with_af["affected_people"] > 0)
    ].copy()

    di_annual = aps.build_desinventar_annual_people(with_af)
    em_annual = aps.load_emdat_annual_people(tmp_em_path, cfg_obj.country)

    combined = aps.combine_annual_sources(
        di_annual,
        em_annual,
        cfg_obj.start_year,
    )

    combined_with_rates = aps.add_scenario_columns(
        combined,
        scenario_rates,
    )

    lec_df, synthetic_df, metrics_df = aps.build_scenario_outputs(
        combined_with_rates,
        scenario_rates,
    )

    return {
        "country": cfg_obj.country,
        "combined": combined_with_rates,
        "lec": lec_df,
        "synthetic": synthetic_df,
        "metrics": metrics_df,
        "scenario_rates": scenario_rates,
        "catalogue_length": cfg_obj.catalogue_length_years,
    }


def build_regional_dataframe(results: list[dict]) -> pd.DataFrame:
    regional_rows = []

    for res in results:
        country_code = res["country"]
        metrics_df = res["metrics"]
        catalogue_length = res["catalogue_length"]

        for _, row in metrics_df.iterrows():
            regional_rows.append({
                "country": country_code,
                "scenario": row["poverty_scenario"],
                "catalogue_length": catalogue_length,
                "average_annual_affected_people": row["average_annual_affected_people"],
                f"mean_{catalogue_length}yr_simulated_affected_people": row[
                    f"mean_{catalogue_length}yr_simulated_affected_people"
                ],
                f"median_{catalogue_length}yr_simulated_affected_people": row[
                    f"median_{catalogue_length}yr_simulated_affected_people"
                ],
                f"p16_{catalogue_length}yr_simulated_affected_people": row[
                    f"p16_{catalogue_length}yr_simulated_affected_people"
                ],
                f"p84_{catalogue_length}yr_simulated_affected_people": row[
                    f"p84_{catalogue_length}yr_simulated_affected_people"
                ],
                f"max_{catalogue_length}yr_simulated_affected_people": row[
                    f"max_{catalogue_length}yr_simulated_affected_people"
                ],
            })

    return pd.DataFrame(regional_rows)




def format_compact_number(value: float) -> str:
    """Format large dashboard values in a compact, readable way."""
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:,.1f}K"
    return f"{value:,.0f}"


def format_full_number(value: float) -> str:
    """Format dashboard values as full whole numbers."""
    return f"{float(value):,.0f}"


def build_country_annual_figure(
    combined_df: pd.DataFrame,
    selected_scenario: str,
    selected_scenario_col: str,
):
    """Create a clean annual affected-people trend figure for a country tab."""
    plot_df = combined_df[
        [
            "year",
            "DesInventar_Affected",
            "EM-DAT_Affected",
            "Affected_People_Max",
            selected_scenario_col,
        ]
    ].copy()

    plot_df = plot_df.rename(
        columns={
            "DesInventar_Affected": "DesInventar",
            "EM-DAT_Affected": "EM-DAT",
            "Affected_People_Max": "Maximum source value",
            selected_scenario_col: selected_scenario,
        }
    )

    plot_df = plot_df.melt(
        id_vars="year",
        var_name="Series",
        value_name="Affected people",
    )

    color_map = IDB_SERIES_COLORS.copy()
    color_map[selected_scenario] = get_scenario_color(selected_scenario)

    fig = px.line(
        plot_df,
        x="year",
        y="Affected people",
        color="Series",
        markers=True,
        color_discrete_map=color_map,
        labels={
            "year": "Year",
            "Affected people": "Affected people",
            "Series": "",
        },
    )

    fig.update_traces(line_width=3, marker_size=6)
    fig.update_layout(
        height=390,
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.03,
            xanchor="left",
            x=0,
        ),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#DCE5EF", rangemode="tozero"),
    )

    return fig


def render_country_tab(res: dict) -> None:
    country_name = res["country"]
    scenario_names = list(res["scenario_rates"].keys())

    st.header(f"Country {country_name}")

    selected_scenario = st.selectbox(
        "Scenario",
        options=scenario_names,
        key=f"scenario_select_{country_name}",
    )

    col_suffix = selected_scenario.replace(" ", "_")
    selected_scenario_col = f"Affected_People_{col_suffix}"
    combined_df = res["combined"]
    metrics_df = res["metrics"]

    metrics_scenario = metrics_df.loc[
        metrics_df["poverty_scenario"] == selected_scenario
    ].copy()

    metrics_row = metrics_scenario.iloc[0]
    catalogue_length = res["catalogue_length"]

    st.subheader("Country summary")

    kpi_cols = st.columns(4)

    kpi_cols[0].metric(
        "Average annual",
        format_full_number(metrics_row["average_annual_affected_people"]),
    )

    kpi_cols[1].metric(
        f"Mean total ({catalogue_length} years)",
        format_full_number(
            metrics_row[f"mean_{catalogue_length}yr_simulated_affected_people"]
        ),
    )

    kpi_cols[2].metric(
        f"Median total ({catalogue_length} years)",
        format_full_number(
            metrics_row[f"median_{catalogue_length}yr_simulated_affected_people"]
        ),
    )

    kpi_cols[3].metric(
        "Maximum annual",
        format_full_number(metrics_row["max_annual_affected_people"]),
    )

    st.subheader("Annual affected people")

    annual_fig = build_country_annual_figure(
        combined_df,
        selected_scenario,
        selected_scenario_col,
    )
    st.plotly_chart(
        annual_fig,
        use_container_width=True,
        key=f"annual_country_figure_{country_name}_{selected_scenario}",
    )

    cols_to_show = [
        "year",
        "DesInventar_Affected",
        "EM-DAT_Affected",
        "Affected_People_Max",
        selected_scenario_col,
    ]

    with st.expander("Affected people by year", expanded=False):
        st.dataframe(
            combined_df[cols_to_show],
            use_container_width=True,
        )

    st.subheader("Risk curves and simulation distribution")

    fig = plt.figure(figsize=(16, 7))
    grid = fig.add_gridspec(
        1,
        2,
        left=0.07,
        right=0.98,
        bottom=0.15,
        top=0.88,
        wspace=0.22,
    )

    ax1 = fig.add_subplot(grid[0, 0])
    ax2 = fig.add_subplot(grid[0, 1])

    aps.plot_dashboard_lec(
        ax1,
        res["lec"],
        metrics_df,
        scenario=selected_scenario,
    )

    aps.plot_dashboard_histograms(
        ax2,
        res["synthetic"],
        scenario=selected_scenario,
    )

    ax1.set_title(
        "Exceedance curve",
        fontweight="bold",
    )

    ax2.set_title(
        f"{catalogue_length}-year simulation distribution",
        fontweight="bold",
    )

    fig.suptitle(
        f"{country_name} · {selected_scenario}",
        fontsize=15,
        fontweight="bold",
    )

    st.pyplot(fig)
    plt.close(fig)

    with st.expander("Simulation metrics table", expanded=False):
        st.dataframe(metrics_scenario, use_container_width=True)


def render_regional_tab(results: list[dict]) -> None:
    st.header("Regional comparison")
    # Build the aggregated dataframe for the region.  Each row corresponds to a country
    # and a poverty scenario and contains various summary metrics computed during
    # analysis.  If no data is available, show an informational message and exit.
    regional_df = build_regional_dataframe(results)
    if regional_df.empty:
        st.info("No regional data to display.")
        return

    # Create a top row with two filter selectors (Scenario and Metric) and a
    # radial gauge showing the regional average.  This layout mirrors the
    # exemplar dashboard: filters on the left and a headline metric on the right.
    top_cols = st.columns([2, 2])
    with top_cols[0]:
        selected_scenario = st.selectbox(
            "Scenario",
            options=regional_df["scenario"].unique().tolist(),
            key="regional_scenario_select",
        )
    # Determine the length of the catalogue (number of years simulated) from the
    # first result.  This is used to build the metric options dynamically.
    first_catalogue_length = results[0]["catalogue_length"]

    # Define available metrics and map their human‑readable labels to dataframe
    # column names.  Only include those metrics that actually exist in the
    # regional dataframe.
    metric_options = {
        "Average Annual Affected People": "average_annual_affected_people",
        f"Mean Total Affected People ({first_catalogue_length} years)": f"mean_{first_catalogue_length}yr_simulated_affected_people",
        f"Median Total Affected People ({first_catalogue_length} years)": f"median_{first_catalogue_length}yr_simulated_affected_people",
        f"16th Percentile ({first_catalogue_length} years)": f"p16_{first_catalogue_length}yr_simulated_affected_people",
        f"84th Percentile ({first_catalogue_length} years)": f"p84_{first_catalogue_length}yr_simulated_affected_people",
        f"Maximum Affected People ({first_catalogue_length} years)": f"max_{first_catalogue_length}yr_simulated_affected_people",
    }
    metric_options = {lbl: col for lbl, col in metric_options.items() if col in regional_df.columns}
    with top_cols[1]:
        selected_metric_label = st.selectbox(
            "Metric",
            options=list(metric_options.keys()),
            key="regional_metric_select",
        )
    selected_metric = metric_options[selected_metric_label]

    # Filter the dataframe by the selected scenario and drop NaN values for the
    # chosen metric.  Sort the resulting dataframe descending by the metric so
    # that the ranking bar chart orders countries from largest to smallest.
    df_sel = regional_df.loc[
        regional_df["scenario"] == selected_scenario
    ].copy()
    df_sel[selected_metric] = pd.to_numeric(df_sel[selected_metric], errors="coerce")
    df_sel = df_sel.loc[df_sel[selected_metric].notna()].copy()
    if df_sel.empty:
        st.info("No data available for this scenario and metric.")
        return
    df_sel.sort_values(selected_metric, ascending=False, inplace=True)

    # Compute summary statistics used in the gauge and metrics section.
    total_metric_value = df_sel[selected_metric].sum()
    avg_metric_value = df_sel[selected_metric].mean()
    max_metric_value = df_sel[selected_metric].max()
    min_metric_value = df_sel[selected_metric].min()
    max_country = df_sel.loc[df_sel[selected_metric].idxmax(), "country"]
    min_country = df_sel.loc[df_sel[selected_metric].idxmin(), "country"]

    # Build the choropleth map.  Use the custom colour scale defined earlier
    # (yellow→green→blue) to align with the overall theme.
    map_df = df_sel[["country", "scenario", selected_metric]].copy()
    map_df = map_df.rename(columns={selected_metric: "metric_value"})
    map_df["iso_alpha"] = map_df["country"]
    custom_color_scale = ["#F3D9A5", "#A8D5BA", "#8BC5E8", "#0F5B9A"]
    fig_map = px.choropleth(
        map_df,
        locations="iso_alpha",
        color="metric_value",
        color_continuous_scale=custom_color_scale,
        locationmode="ISO-3",
        hover_name="country",
        hover_data={
            "iso_alpha": False,
            "metric_value": ":,.0f",
            "scenario": True,
        },
        labels={"metric_value": selected_metric_label},
    )
    fig_map.update_traces(marker_line_color="#FFFFFF", marker_line_width=0.6)
    fig_map.update_geos(
        fitbounds="locations",
        visible=False,
        showcountries=True,
        showcoastlines=True,
        showland=True,
        landcolor="#F7F9FC",
        countrycolor="#DCE5EF",
        coastlinecolor="#DCE5EF",
        resolution=50,
        projection_type="natural earth",
    )
    fig_map.update_layout(
        height=500,
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar=dict(title=selected_metric_label),
    )

    # Create a middle row with the map on the left and the ranking bar chart on
    # the right.  Use a 3:2 ratio to give more space to the map, as in the
    # example image.
    mid_cols = st.columns([3, 2])
    with mid_cols[0]:
        st.subheader("Regional map")
        st.plotly_chart(
            fig_map,
            use_container_width=True,
            key=f"regional_map_{selected_scenario}_{selected_metric}",
        )
    # Build the ranking bar chart for the selected metric.  Use our palette to
    # colour the bars consistently.  The chart orders countries by metric value.
    fig_bar = px.bar(
        df_sel,
        x="country",
        y=selected_metric,
        color="country",
        labels={
            "country": "Country",
            selected_metric: selected_metric_label,
        },
        color_discrete_sequence=["#0F5B9A", "#8BC5E8", "#A8D5BA", "#F3D9A5"] * 10,
    )
    fig_bar.update_layout(
        height=500,
        xaxis_title="Country",
        yaxis_title=selected_metric_label,
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
    )
    with mid_cols[1]:
        st.subheader("Country ranking")
        st.plotly_chart(
            fig_bar,
            use_container_width=True,
            key=f"regional_bar_{selected_scenario}_{selected_metric}",
        )

    # Bottom row: display summary metrics in four metric cards and a table of
    # underlying data.  These cards show total, average, maximum and minimum
    # values, with annotations for the countries corresponding to the extrema.
    st.subheader("Regional summary")
    card_cols = st.columns(4)
    card_cols[0].metric("Total", f"{total_metric_value:,.0f}")
    card_cols[1].metric("Average", f"{avg_metric_value:,.0f}")
    card_cols[2].metric("Maximum", f"{max_metric_value:,.0f}", max_country)
    card_cols[3].metric("Minimum", f"{min_metric_value:,.0f}", min_country)

    # Display the detailed table of country values for the selected scenario and
    # metric.  Keep the table within the available width and let users scroll
    # horizontally if necessary.
    st.dataframe(
        df_sel[["country", "scenario", selected_metric]].rename(
            columns={"country": "Country", "scenario": "Scenario", selected_metric: selected_metric_label}
        ),
        use_container_width=True,
    )


def remove_country(index: int) -> None:
    """Remove a country configuration and clear saved results to avoid stale outputs."""
    if 0 <= index < len(st.session_state["countries"]):
        st.session_state["countries"].pop(index)
        st.session_state["analysis_results"] = None
        run_country_analysis.clear()
        st.session_state["country_pending_removal"] = None


def request_country_removal(index: int) -> None:
    """Store the selected country index until the user confirms removal."""
    if 0 <= index < len(st.session_state["countries"]):
        st.session_state["country_pending_removal"] = index


def cancel_country_removal() -> None:
    """Cancel the pending country removal request."""
    st.session_state["country_pending_removal"] = None


def main() -> None:
    aps.SCENARIO_COLORS = IDB_SCENARIO_COLORS.copy()

    # Configure the page layout.  The wide layout maximises the available
    # horizontal space for charts and tables.
    st.set_page_config(layout="wide")

    # -------------------------------------------------------------------
    # Inject custom CSS styles.  These styles adjust the global font,
    # progress bar colours, metric cards, and table formatting.  They
    # complement the theme defined in `.streamlit/config.toml` and provide a
    # cohesive aesthetic inspired by the provided design reference.  Use
    # `unsafe_allow_html=True` because we are injecting raw HTML/CSS.
    st.markdown(
        """
        <style>
        :root {
            --idb-blue: #0F5B9A;
            --idb-blue-soft: #8BC5E8;
            --idb-green-soft: #A8D5BA;
            --idb-sand-soft: #F3D9A5;
            --idb-bg: #F7F9FC;
            --idb-card: #FFFFFF;
            --idb-text: #2E3A46;
            --idb-border: #DCE5EF;
        }

        .stApp {
            background-color: var(--idb-bg);
            color: var(--idb-text);
        }

        html, body, [class*="st"] {
            font-family: "Segoe UI", "Roboto", sans-serif;
        }

        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }

        .idb-header {
            background: linear-gradient(90deg, #0F5B9A 0%, #5B8DB8 100%);
            padding: 20px 24px;
            border-radius: 0 0 18px 18px;
            margin-bottom: 22px;
            box-shadow: 0 8px 24px rgba(15, 91, 154, 0.18);
        }

        .idb-header h1 {
            color: #FFFFFF;
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .idb-header p {
            color: #EAF2FA;
            margin: 6px 0 0 0;
            font-size: 0.95rem;
        }

        [data-testid="stSidebar"] {
            background-color: #EEF6FC;
            border-right: 1px solid var(--idb-border);
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: var(--idb-blue);
        }

        .stButton button {
            background-color: var(--idb-blue);
            color: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 0.55rem 1rem;
            font-weight: 600;
            box-shadow: 0 4px 10px rgba(15, 91, 154, 0.18);
            white-space: nowrap;
        }

        .stButton button:hover {
            background-color: #0B4D83;
            color: #FFFFFF;
            border: none;
        }

        div[data-testid="stMetric"] {
            background: var(--idb-card);
            border: 1px solid var(--idb-border);
            border-left: 5px solid var(--idb-blue);
            border-radius: 16px;
            padding: 18px 18px;
            box-shadow: 0 8px 20px rgba(46, 58, 70, 0.06);
            height: 124px !important;
            min-height: 124px !important;
            max-height: 124px !important;
            box-sizing: border-box;
            overflow: hidden;
        }

        div[data-testid="stMetric"] label {
            color: var(--idb-blue);
            font-weight: 700;
        }

        div[data-testid="stMetricLabel"] {
            height: 22px !important;
            min-height: 22px !important;
            margin: 0 !important;
            display: flex;
            align-items: center;
        }

        div[data-testid="stMetricValue"] {
            color: var(--idb-text);
            font-weight: 800;
            height: 46px !important;
            min-height: 46px !important;
            margin-top: 5px !important;
            display: flex;
            align-items: center;
            line-height: 1 !important;
        }

        div[data-testid="stMetricDelta"] {
            height: 22px !important;
            min-height: 22px !important;
            margin-top: 3px !important;
            display: flex;
            align-items: center;
        }

        .stDataFrame, div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid var(--idb-border);
            box-shadow: 0 6px 16px rgba(46, 58, 70, 0.04);
        }

        thead tr th {
            background-color: #EAF2FA !important;
            color: var(--idb-blue) !important;
            font-weight: 700 !important;
        }

        tbody tr:nth-child(even) {
            background-color: #F7F9FC !important;
        }

        tbody tr:nth-child(odd) {
            background-color: #FFFFFF !important;
        }

        div[data-baseweb="select"] > div,
        input, textarea {
            border-radius: 10px !important;
            border-color: var(--idb-border) !important;
        }



        [data-testid="stExpander"] details summary {
            background-color: #F7FBFF;
            border-radius: 12px;
            padding: 0.35rem 0.5rem;
        }

        [data-testid="stExpander"] details summary p {
            color: var(--idb-blue) !important;
            font-weight: 800 !important;
            font-size: 1.02rem !important;
            letter-spacing: -0.01em;
        }

        .stRadio > div {
            background: #FFFFFF;
            border: 1px solid var(--idb-border);
            border-radius: 14px;
            padding: 8px 12px;
        }

        .stProgress > div > div {
            background-color: #DCE5EF;
            border-radius: 10px;
        }

        .stProgress > div > div > div > div {
            background-color: var(--idb-blue-soft);
            border-radius: 10px;
        }

        .remove-confirm-box {
            background: #FFF7E6;
            border: 1px solid #F3D9A5;
            border-left: 4px solid #E5B85C;
            border-radius: 12px;
            padding: 12px 14px;
            margin: 8px 0 10px 0;
            color: var(--idb-text);
            font-size: 0.92rem;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="idb-header">
            <h1>Affected People Risk Dashboard</h1>
            <p>Multi-country scenario analysis</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "countries" not in st.session_state:
        st.session_state["countries"] = []

    if "analysis_results" not in st.session_state:
        st.session_state["analysis_results"] = None

    if "country_pending_removal" not in st.session_state:
        st.session_state["country_pending_removal"] = None

    with st.sidebar:
        st.header("Country Inputs")

        if st.button("Add country", key="add_country"):
            st.session_state["countries"].append({
                "country": aps.CFG.country,
                "poverty_rate": aps.CFG.poverty_rate,
                "vulnerability_rate": aps.CFG.vulnerability_rate,
                "household_size": aps.CFG.household_size,
                "start_year": aps.CFG.start_year,
                "catalogue_length_years": aps.CFG.catalogue_length_years,
                "simulation_number": aps.CFG.simulation_number,
                "random_seed": aps.CFG.random_seed,
                "des_file": None,
                "em_file": None,
            })

        if st.session_state["countries"]:
            st.caption("Add, edit, or remove country configurations before running the analysis.")

        for idx, cfg in enumerate(st.session_state["countries"]):
            with st.expander(f"Country {idx + 1} · {cfg['country']}", expanded=True):
                cfg["country"] = st.text_input(
                    f"Country ISO Code #{idx + 1}",
                    value=cfg["country"],
                    key=f"country_iso_{idx}",
                ).strip().upper()

                cfg["poverty_rate"] = st.number_input(
                    f"Poverty Rate (% or fraction) #{idx + 1}",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(cfg["poverty_rate"]),
                    key=f"poverty_rate_{idx}",
                )

                cfg["vulnerability_rate"] = st.number_input(
                    f"Vulnerability Rate (% or fraction) #{idx + 1}",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(cfg["vulnerability_rate"]),
                    key=f"vulnerability_rate_{idx}",
                )

                cfg["household_size"] = st.number_input(
                    f"Household Size #{idx + 1}",
                    min_value=1.0,
                    value=float(cfg["household_size"]),
                    key=f"household_size_{idx}",
                )

                cfg["start_year"] = st.number_input(
                    f"Start Year #{idx + 1}",
                    min_value=1900,
                    max_value=2100,
                    value=int(cfg["start_year"]),
                    key=f"start_year_{idx}",
                )

                cfg["catalogue_length_years"] = st.number_input(
                    f"Catalogue Length (years) #{idx + 1}",
                    min_value=1,
                    max_value=50,
                    value=int(cfg["catalogue_length_years"]),
                    key=f"catalogue_length_{idx}",
                )

                cfg["simulation_number"] = st.number_input(
                    f"Number of Simulations #{idx + 1}",
                    min_value=100,
                    max_value=10000,
                    step=100,
                    value=int(cfg["simulation_number"]),
                    key=f"simulation_number_{idx}",
                )

                cfg["random_seed"] = st.number_input(
                    f"Random Seed #{idx + 1}",
                    min_value=0,
                    value=int(cfg["random_seed"]),
                    key=f"random_seed_{idx}",
                )

                cfg["des_file"] = st.file_uploader(
                    f"Upload DesInventar XML File #{idx + 1}",
                    type=["xml"],
                    key=f"des_file_{idx}",
                )

                cfg["em_file"] = st.file_uploader(
                    f"Upload EM-DAT Excel File #{idx + 1}",
                    type=["xlsx", "xls"],
                    key=f"em_file_{idx}",
                )

                st.divider()

                pending_idx = st.session_state.get("country_pending_removal")
                if pending_idx == idx:
                    st.markdown(
                        f"""
                        <div class="remove-confirm-box">
                            <strong>Remove {cfg['country']}?</strong><br>
                            Saved analysis results will be cleared.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    if st.button(
                        "Yes, remove",
                        key=f"confirm_remove_country_{idx}",
                        use_container_width=True,
                    ):
                        remove_country(idx)
                        st.rerun()

                    if st.button(
                        "Cancel",
                        key=f"cancel_remove_country_{idx}",
                        use_container_width=True,
                    ):
                        cancel_country_removal()
                        st.rerun()
                else:
                    if st.button(
                        "Remove country",
                        key=f"remove_country_{idx}",
                        use_container_width=True,
                    ):
                        request_country_removal(idx)
                        st.rerun()

        run_button = st.button("Run analysis", key="run_analysis")

        if st.button("Clear results", key="clear_results"):
            st.session_state["analysis_results"] = None
            run_country_analysis.clear()
            st.success("Results cleared.")

    if run_button:
        if not st.session_state["countries"]:
            st.warning("Please add at least one country configuration before running the analysis.")
            return

        for idx, cfg in enumerate(st.session_state["countries"]):
            if cfg["des_file"] is None or cfg["em_file"] is None:
                st.warning(
                    f"Please upload both the DesInventar XML and EM-DAT Excel files "
                    f"for Country {idx + 1} ({cfg['country']})."
                )
                return

        results = []

        progress = st.progress(0)
        status = st.empty()

        for idx, cfg_data in enumerate(st.session_state["countries"]):
            status.info(f"Processing {cfg_data['country']}...")

            try:
                result = run_country_analysis(
                    country=cfg_data["country"],
                    poverty_rate=float(cfg_data["poverty_rate"]),
                    vulnerability_rate=float(cfg_data["vulnerability_rate"]),
                    household_size=float(cfg_data["household_size"]),
                    start_year=int(cfg_data["start_year"]),
                    catalogue_length_years=int(cfg_data["catalogue_length_years"]),
                    simulation_number=int(cfg_data["simulation_number"]),
                    random_seed=int(cfg_data["random_seed"]),
                    des_file_bytes=cfg_data["des_file"].getvalue(),
                    em_file_bytes=cfg_data["em_file"].getvalue(),
                )

                results.append(result)

            except Exception as e:
                st.error(f"An error occurred while analysing {cfg_data['country']}: {e}")
                st.exception(e)
                return

            progress.progress((idx + 1) / len(st.session_state["countries"]))

        status.empty()
        progress.empty()

        st.session_state["analysis_results"] = results
        st.success("Analysis completed.")

    if st.session_state["analysis_results"] is None:
        return

    results = st.session_state["analysis_results"]
    country_names = [res["country"] for res in results]

    display_options = country_names + ["Regional comparison"]

    selected_view = st.radio(
        "Dashboard view",
        options=display_options,
        horizontal=True,
        key="dashboard_view",
    )

    if selected_view == "Regional comparison":
        render_regional_tab(results)
    else:
        selected_result = next(
            res for res in results
            if res["country"] == selected_view
        )
        render_country_tab(selected_result)


if __name__ == "__main__":
    main()
