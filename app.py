import pandas as pd
import streamlit as st  # App that hosts the simulator

import help_text as ht
from charts import build_generation_chart, build_cost_chart
from Config import (BASELINE_CAPACITY, BATTERY_BASELINE_MWH, BATTERY_DURATION_H, EMISSIONS,
                    TECH_AVAILABILITY)
from data_loader import load_generation_profile, load_demand_trace
from dispatch import (build_year_dataframe, calculate_coal_minimum, calculate_metrics, pumped_hydro_storage,
                      run_dispatch)

#---------------------------------------------------------------------------------------------------------------
# Page setup
#---------------------------------------------------------------------------------------------------------------

st.set_page_config(page_title="NSW Energy Simulator", layout="wide")

RELIABILITY_STANDARD_PCT = 0.002    # AEMO reliability standard: max unserved energy (% of demand)

gen_profile = load_generation_profile()     # 2023 half-hourly generation profile

#---------------------------------------------------------------------------------------------------------------
# Baseline capacities and reset
# Slider values are stored in st.session_state so they are kept each time the app reruns
#---------------------------------------------------------------------------------------------------------------

def get_baseline_capacity(year, technology):
    return BASELINE_CAPACITY[year][technology]


def reset_to_baseline(year):     # sets every slider back to the year's baseline (nuclear to 0)
    st.session_state["solar_mw"] = get_baseline_capacity(year, "Solar")
    st.session_state["wind_mw"] = get_baseline_capacity(year, "Wind")
    st.session_state["hydro_mw"] = get_baseline_capacity(year, "Hydro")
    st.session_state["pumped_mw"] = get_baseline_capacity(year, "PumpedHydro")
    st.session_state["gas_mw"] = get_baseline_capacity(year, "Gas")
    st.session_state["coal_mw"] = get_baseline_capacity(year, "BlackCoal")
    st.session_state["battery_mwh"] = BATTERY_BASELINE_MWH[year]    # battery slider is in MWh, not MW
    st.session_state["nuclear_mw"] = 0


#---------------------------------------------------------------------------------------------------------------
# Sidebar: scenario year
#---------------------------------------------------------------------------------------------------------------

st.sidebar.title("NSW Energy Simulator")
st.sidebar.subheader("Scenario year")

year = st.sidebar.selectbox(
    "Which year are you exploring?", [2023, 2030, 2040],
    help="Each year has its own electricity use and costs.",
)

# Short description shown under the year selector
year_context = {
    2023: "2023 electricity grid",
    2030: "NSW uses about 16% more electricity than in 2023",
    2040: "NSW uses about 30% more electricity than in 2023",
}
st.sidebar.info(year_context[year])

# Half-hourly demand and generation for the chosen year
demand_trace = load_demand_trace(year)

df = build_year_dataframe(year, gen_profile, demand_trace)

availability = TECH_AVAILABILITY[year]      # which technologies can be chosen in this year

#---------------------------------------------------------------------------------------------------------------
# Sidebar: turn sources on and off
# Storage (battery and pumped hydro) has no switch; set it to 0 with its slider instead
#---------------------------------------------------------------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.subheader("Enable / disable sources")

left, right = st.sidebar.columns(2)     # two columns of checkboxes
with left:
    solar_on = st.checkbox("Solar", value=True)
    wind_on = st.checkbox("Wind", value=True)
    hydro_on = st.checkbox("Hydro", value=True)
with right:
    gas_on = st.checkbox("Gas", value=True)
    coal_on = st.checkbox("Coal", value=get_baseline_capacity(year, "BlackCoal") > 0)   # off once all coal retires (2040)

# Nuclear: only offered in years where it is available (2040)
nuclear_on = False
if availability["nuclear"]:
    nuclear_on = st.sidebar.checkbox("Nuclear", value=False,
                                     help="Nuclear power runs steadily day and night and doesn't release CO₂.")

#---------------------------------------------------------------------------------------------------------------
# Sidebar: capacity sliders
# Sliders start at the chosen year's baseline and go back to it when the year changes
#---------------------------------------------------------------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.subheader("Add or remove capacity")
st.sidebar.button(f"Reset to {year} baseline", on_click=reset_to_baseline, args=(year,), width="stretch")

if st.session_state.get("_last_year") != year:      # first load, or the year has changed
    reset_to_baseline(year)
    st.session_state["_last_year"] = year

# Baseline capacity for the chosen year (MW)
solar_base = get_baseline_capacity(year, "Solar")
wind_base = get_baseline_capacity(year, "Wind")
hydro_base = get_baseline_capacity(year, "Hydro")
pumped_base = get_baseline_capacity(year, "PumpedHydro")
gas_base = get_baseline_capacity(year, "Gas")
coal_base = get_baseline_capacity(year, "BlackCoal")

# Slider limits that come from the data
hydro_fleet_mw = BASELINE_CAPACITY[2023]["Hydro"]                # existing fleet; no new hydro can be added
coal_slider_max = BASELINE_CAPACITY[2023]["BlackCoal"] + 2000   # 2023 fleet + headroom for user experimentation

# Sliders
st.sidebar.slider("Solar (MW)", 0, 50000, step=500, key="solar_mw", disabled=not solar_on)

st.sidebar.slider("Wind (MW)", 0, 30000, step=500, key="wind_mw", disabled=not wind_on)

st.sidebar.slider("Hydro (MW)", 0, hydro_fleet_mw, step=100, key="hydro_mw", disabled=not hydro_on,
                  help="Power from water flowing through NSW's existing dams. New dams are unlikely to be built, "
                       "so this simulator only lets you keep or reduce them. Pumped hydro, which stores energy "
                       "using water, can be added below.")

st.sidebar.slider("Pumped hydro (MW)", 0, 15000, step=100, key="pumped_mw",
                  help="Works like a giant battery. It pumps water uphill when there is spare electricity, "
                       "then lets it flow back down to make power when it's needed.")

st.sidebar.slider("Battery storage (MWh)", 0, 200000, step=500, key="battery_mwh",
                  help="Large batteries that store spare electricity to use later. "
                       "MWh is how much energy they can hold.")

st.sidebar.slider("Gas (MW)", 0, 15000, step=100, key="gas_mw", disabled=not gas_on)

st.sidebar.slider("Coal (MW)", 0, coal_slider_max, step=500, key="coal_mw", disabled=not coal_on)

if nuclear_on:
    st.sidebar.slider("Nuclear (MW)", 0, 10000, step=500, key="nuclear_mw",
                      help="How much nuclear power to build.")

# Values chosen on the sliders
solar_mw = st.session_state["solar_mw"]
wind_mw = st.session_state["wind_mw"]
hydro_mw = st.session_state["hydro_mw"]
pumped_mw = st.session_state["pumped_mw"]
gas_mw = st.session_state["gas_mw"]
coal_mw = st.session_state["coal_mw"]
battery_mwh = st.session_state["battery_mwh"]
nuclear_mw = st.session_state["nuclear_mw"] if nuclear_on else 0

# Change from the baseline (MW), which is what run_dispatch takes
solar_add = solar_mw - solar_base
wind_add = wind_mw - wind_base
hydro_add = hydro_mw - hydro_base
pumped_add = pumped_mw - pumped_base
gas_add = gas_mw - gas_base
coal_add = coal_mw - coal_base

#---------------------------------------------------------------------------------------------------------------
# Sidebar: time period
# User can specify the month, week or day instead of the full year
# The selected period is simulated independently, with storage starting half full
# --------------------------------------------------------------------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.subheader("Time period")

year_start = df["Time-ending"].min()
year_end = df["Time-ending"].max()
default_day = (year_start + pd.Timedelta(days=150)).date()     # 1 June, so winter is shown first

time_mode = st.sidebar.selectbox("View period:", ["Full year", "Month", "Week", "Day"])

if time_mode == "Month":
    month_options = pd.date_range(year_start, year_end, freq="MS")      # first day of each month
    month_labels = [d.strftime("%B %Y") for d in month_options]
    selected_idx = month_labels.index(st.sidebar.selectbox("Select month:", month_labels))
    date_start = month_options[selected_idx]
    if selected_idx + 1 < len(month_options):
        date_end = month_options[selected_idx + 1]
    else:
        date_end = year_end + pd.Timedelta(days=1)                     # December runs to the end of the data

elif time_mode == "Week":
    week_start = st.sidebar.date_input("Week starting:", value=default_day,
                                       min_value=year_start.date(),
                                       max_value=(year_end - pd.Timedelta(days=7)).date())
    date_start = pd.to_datetime(week_start)
    date_end = date_start + pd.Timedelta(days=7)

elif time_mode == "Day":
    day_pick = st.sidebar.date_input("Select day:", value=default_day,
                                     min_value=year_start.date(), max_value=year_end.date())
    date_start = pd.to_datetime(day_pick)
    date_end = date_start + pd.Timedelta(days=1)

#---------------------------------------------------------------------------------------------------------------
# Data for the chosen period
#---------------------------------------------------------------------------------------------------------------

if time_mode == "Full year":
    df_view = df.copy()
else:
    in_period = (df["Time-ending"] >= date_start) & (df["Time-ending"] < date_end)
    df_view = df[in_period].copy()

if len(df_view) == 0:
    st.error("No data for the selected period. Please choose a different date.")
    st.stop()

#---------------------------------------------------------------------------------------------------------------
# Run dispatch and calculate metrics
#---------------------------------------------------------------------------------------------------------------

# Half-hourly dispatch for the chosen period
results = run_dispatch(
    df_view,
    capacity_additions={"solar": solar_add, "wind": wind_add, "hydro": hydro_add,
                        "pumped_hydro": pumped_add, "gas": gas_add, "coal": coal_add},
    source_toggles={"solar": solar_on, "wind": wind_on, "hydro": hydro_on,
                    "gas": gas_on, "coal": coal_on},
    battery_capacity_mwh=battery_mwh,
    year=year,
    nuclear_mw=nuclear_mw,
)

# Capacity of each source (MW), 0 if switched off; used for costs
coal_fleet = coal_mw if coal_on else 0
existing_hydro_mw = hydro_mw if hydro_on else 0
capacities_mw = {
    "Solar": solar_mw if solar_on else 0,
    "Wind": wind_mw if wind_on else 0,
    "Hydro": existing_hydro_mw,
    "PumpedHydro": pumped_mw,
    "Gas": gas_mw if gas_on else 0,
    "BlackCoal": coal_fleet,
    "Battery": battery_mwh / BATTERY_DURATION_H[year],      # MWh / hours = MW
    "Nuclear": nuclear_mw,
}

# Storage hours, used to pick the storage cost
pumped_mwh = pumped_hydro_storage(pumped_mw, year)
storage_hours = {
    "Battery": BATTERY_DURATION_H[year],
    "PumpedHydro": pumped_mwh / pumped_mw if pumped_mw > 0 else 0,     # average across the pumped hydro fleet
}

metrics = calculate_metrics(results, EMISSIONS[year], capacities_mw, year, storage_hours)

#---------------------------------------------------------------------------------------------------------------
# Page title, blackout warning and key metrics
#---------------------------------------------------------------------------------------------------------------

st.title(f"NSW Energy Simulator — {year}")

# Warning if unserved energy is above AEMO's reliability standard, otherwise a short introduction
has_blackout = metrics["pct_unserved"] > RELIABILITY_STANDARD_PCT

if has_blackout:
    st.warning(
        f"### Not enough electricity\n"
        f"Your {year} mix couldn't always meet demand. **{metrics['unserved_mwh']:,.0f} MWh** "
        f"({metrics['pct_unserved']:.2f}% of demand) couldn't be supplied, which would mean blackouts. "
        f"A reliable grid keeps this almost at zero.\n\n"
        f"Try adding more generation or storage, or turning sources back on."
    )
else:
    st.markdown(
        f"Explore how NSW's electricity grid performs in **{year}**. "
        "Use the sidebar controls to build your own mix — there's no right answer, "
        "only trade-offs to discover."
    )

# Key metrics: five numbers across the page, each with a help tooltip (from help_text.py)
st.markdown("### Key metrics")
renew_col, cost_col, emissions_col, unserved_col, curtailed_col = st.columns(5)

show_clean = nuclear_mw > 0                         # also show the clean share when nuclear is used
some_unserved = metrics["pct_unserved"] > 0

with renew_col:
    st.metric("Renewable share", f"{metrics['pct_renewable']:.1f}%",
              delta=f"Clean incl. nuclear: {metrics['pct_clean']:.1f}%" if show_clean else None,
              delta_color="off", help=ht.renewable_share(show_clean))

with cost_col:
    st.metric("Average cost of electricity", f"${metrics['avg_cost_mwh']:.0f}/MWh",
              help=ht.avg_cost())

with emissions_col:
    st.metric("Emissions intensity", f"{metrics['emissions_intensity']:.0f} kg/MWh",
              delta=f"{metrics['total_emissions_mt']:.2f} Mt total",
              delta_color="off", help=ht.emissions_intensity(year))

with unserved_col:
    st.metric("Unserved energy", f"{metrics['unserved_mwh']:,.0f} MWh",
              delta=f"{metrics['pct_unserved']:.2f}% of demand" if some_unserved else "Supply met",
              delta_color="inverse" if some_unserved else "off",      # red when demand is not met
              help=ht.unserved_energy(metrics["pct_unserved"]))

with curtailed_col:
    st.metric("Curtailed energy", f"{metrics['curtailed_mwh']:,.0f} MWh",
              help=ht.curtailment())

#---------------------------------------------------------------------------------------------------------------
# Charts: generation over time and cost breakdown
#---------------------------------------------------------------------------------------------------------------

st.markdown("---")

# Name of the chosen period, used in the chart title
if time_mode == "Full year":
    period_label = str(year)
elif time_mode == "Month":
    period_label = month_labels[selected_idx]
elif time_mode == "Week":
    period_label = f"Week of {week_start.strftime('%d %b %Y')}"
else:
    period_label = day_pick.strftime("%d %b %Y")

if time_mode != "Full year":
    st.markdown(f"**{period_label}**")

# Generation chart: a year or month is averaged so it is readable; a week or day shows every half hour
chart_data = results.copy()

if time_mode in ("Full year", "Month"):
    for col in ["Battery_dispatch", "PumpedHydro_dispatch"]:
        chart_data[col] = chart_data[col].clip(lower=0)     # remove charging (negative) before averaging
    average_over = "D" if time_mode == "Full year" else "6h"   # daily for a year, 6-hourly for a month
    chart_data = chart_data.set_index("Time-ending").resample(average_over).mean().reset_index()
    chart_title = ("Average daily generation" if time_mode == "Full year"
                   else "Generation (6-hour average)")
else:
    chart_title = "Generation (every half hour)"

st.plotly_chart(build_generation_chart(chart_data, f"{chart_title} — {period_label}", nuclear_mw),
                width="stretch")

# Cost chart: only sources that have a cost
st.markdown(f"### Cost breakdown — {year}")
costs_display = {source: cost for source, cost in metrics["costs"].items() if cost["total"] > 0}

if costs_display:
    st.plotly_chart(build_cost_chart(costs_display, metrics["avg_cost_mwh"], year), width="stretch")

#---------------------------------------------------------------------------------------------------------------
# Summary of the chosen energy mix
#---------------------------------------------------------------------------------------------------------------

st.markdown("---")
st.markdown(f"### Your {year} energy mix")

renew_col, storage_col, steady_col = st.columns(3)

with renew_col:
    st.markdown("**Renewables**")
    st.write(f"Solar: {solar_mw:,} MW" if solar_on else "Solar: off")
    st.write(f"Wind: {wind_mw:,} MW" if wind_on else "Wind: off")
    st.write(f"Hydro: {hydro_mw:,} MW" if hydro_on else "Hydro: off")

with storage_col:
    st.markdown("**Storage and backup**")
    st.write(f"Battery: {capacities_mw['Battery']:,.0f} MW / {battery_mwh:,} MWh")
    if pumped_mw > 0:
        st.write(f"Pumped hydro: {pumped_mw:,} MW / {pumped_mwh:,.0f} MWh")
    st.write(f"Gas: {gas_mw:,} MW" if gas_on else "Gas: off")

with steady_col:
    st.markdown("**Coal and nuclear**")
    if coal_on:
        coal_minimum = calculate_coal_minimum(coal_fleet, year)
        st.write(f"Coal: {coal_fleet:,} MW")
        st.caption(f"Always runs at least {coal_minimum:,.0f} MW, as coal plants can't turn down further")
    else:
        st.write("Coal: off")
    if nuclear_mw > 0:
        st.write(f"Nuclear: {nuclear_mw:,} MW")

#---------------------------------------------------------------------------------------------------------------
# Footer
# Full sources are listed in the Methods chapter
#---------------------------------------------------------------------------------------------------------------

st.markdown("---")
st.caption(
    "Built from real NSW electricity data for 2023, and forecasts from the Australian Energy Market "
    "Operator (AEMO) and CSIRO for 2030 and 2040. This tool is for learning only and is not a forecast."
)