import plotly.graph_objects as go

#---------------------------------------------------------------------------------------------------------------
# Colours and labels
#---------------------------------------------------------------------------------------------------------------

COLOURS = {
    "Solar": "#D6D637",
    "Wind": "#47D9D9",
    "Hydro": "#3737D6",
    "Nuclear": "#1BCE1B",
    "Battery": "#EC25EC",
    "Pumped hydro": "#7A5CFF",
    "Gas": "#F8B230",
    "Coal": "#808080",
}

# Dispatch results column and chart label, in the order they are stacked (bottom to top)
DISPATCH_COLS = [
    ("Solar_dispatch", "Solar"),
    ("Wind_dispatch", "Wind"),
    ("Hydro_dispatch", "Hydro"),
    ("Nuclear_dispatch", "Nuclear"),
    ("Battery_dispatch", "Battery"),
    ("PumpedHydro_dispatch", "Pumped hydro"),
    ("Gas_dispatch", "Gas"),
    ("Coal_dispatch", "Coal"),
]

# Storage output column and its stored energy column (shown on hover)
STORAGE_LEVEL = {
    "Battery_dispatch": "Battery_SOC",
    "PumpedHydro_dispatch": "PumpedHydro_SOC",
}

#---------------------------------------------------------------------------------------------------------------
# Generation chart: output of each source stacked over time, with demand as a dotted line
#---------------------------------------------------------------------------------------------------------------

def build_generation_chart(chart_data, title, nuclear_mw):
    fig = go.Figure()
    time = chart_data["Time-ending"]

    for col, label in DISPATCH_COLS:
        # Leave out nuclear and pumped hydro when they aren't in the mix
        if col == "Nuclear_dispatch" and nuclear_mw == 0:
            continue
        if col == "PumpedHydro_dispatch" and not (chart_data[col] != 0).any():
            continue

        if col in STORAGE_LEVEL:
            output = chart_data[col].clip(lower=0)      # show output only (charging is negative)
            stored = chart_data[STORAGE_LEVEL[col]]
            hover = f"{label}: %{{y:.0f}} MW<br>{label} level: %{{customdata:.0f}} MWh<extra></extra>"
        else:
            output = chart_data[col]
            stored = None
            hover = f"{label}: %{{y:.0f}} MW<extra></extra>"

        fig.add_trace(go.Scatter(
            x=time, y=output, name=label, stackgroup="gen",
            line=dict(width=0), fillcolor=COLOURS[label], mode="lines",
            customdata=stored, hovertemplate=hover,
        ))

    # Demand that couldn't be supplied, stacked on top in red
    if chart_data["Shortfall"].sum() > 0:
        fig.add_trace(go.Scatter(
            x=time, y=chart_data["Shortfall"], name="Energy not supplied", stackgroup="gen",
            line=dict(width=0), fillcolor="red", mode="lines",
            hovertemplate="Energy not supplied: %{y:.0f} MW<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        x=time, y=chart_data["Demand"], name="Demand", mode="lines",
        line=dict(color="black", width=2, dash="dot"),
        hovertemplate="Demand: %{y:.0f} MW<extra></extra>",
    ))

    fig.update_layout(
        title=title, xaxis_title="", yaxis_title="Power (MW)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500, plot_bgcolor="white", paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")
    return fig

#---------------------------------------------------------------------------------------------------------------
# Cost chart: cost of each source, split into capital, fixed O&M and fuel + variable O&M
#---------------------------------------------------------------------------------------------------------------

# Cost part (from costs.py), legend label and colour
COST_COMPONENTS = [
    ("capital", "Capital (CRF)", "#4C6A92"),
    ("fixed", "Fixed O&M", "#8FA9C8"),
    ("variable", "Fuel + variable O&M", "#E07B39"),
]

SOURCE_LABELS = {"BlackCoal": "Coal", "PumpedHydro": "Pumped hydro"}


def _cost_hover(cost):
    # Extra detail shown when hovering over a source's bar
    text = f"Total: ${cost['total'] / 1e6:,.0f}M<br>"
    if cost["mwh"] > 0:
        text += f"Cost per MWh generated: ${cost['total'] / cost['mwh']:,.0f}"
    else:
        text += "No generation"
    return text


def build_cost_chart(costs, avg_cost_mwh, year):
    sources = list(costs)
    names = [SOURCE_LABELS.get(source, source) for source in sources]
    hover = [_cost_hover(costs[source]) for source in sources]

    fig = go.Figure()
    for part, label, colour in COST_COMPONENTS:
        fig.add_trace(go.Bar(
            x=names, y=[costs[source][part] / 1e6 for source in sources],      # $ million
            name=label, marker_color=colour, customdata=hover,
            hovertemplate=f"{label}: $%{{y:,.0f}}M<br>%{{customdata}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        title=f"Cost by source — {year} (average ${avg_cost_mwh:.0f}/MWh)",
        yaxis_title="$ million", xaxis_title="",
        height=620, plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=13),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0")
    fig.update_xaxes(tickfont=dict(size=13))
    return fig
