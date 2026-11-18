import os
import pandas as pd
import streamlit as st
from Config import DATA_FILES, GEN_PROFILE_FILE

#---------------------------------------------------------------------------------------------------------------
# Data loading
# Each file is read once and cached, so moving a slider doesn't reload it
#---------------------------------------------------------------------------------------------------------------

# Generation columns in the 2023 file (MW)
GEN_COLS = ["Solar_MW", "Wind_MW", "Hydro_MW", "Gas_MW", "BlackCoal_MW", "Battery_MW"]


def _check_file(path):      # stop the app with a message if a data file is missing
    if not os.path.exists(path):
        st.error(f"Could not find {path}.")
        st.stop()


# 2023 half-hourly generation by source (Time-ending = end of each half-hour)
@st.cache_data
def load_generation_profile():
    _check_file(GEN_PROFILE_FILE)
    return pd.read_csv(GEN_PROFILE_FILE, parse_dates=["Time-ending"])


# Half-hourly demand for the chosen year, with columns datetime and demand_mw
@st.cache_data
def load_demand_trace(year):
    path = DATA_FILES[year]
    _check_file(path)

    if year == 2023:    # 2023 demand = total NSW generation
        df = pd.read_csv(path, parse_dates=["Time-ending"])
        return pd.DataFrame({"datetime": df["Time-ending"], "demand_mw": df[GEN_COLS].sum(axis=1)})

    return pd.read_csv(path, parse_dates=["datetime"])     # 2030 and 2040: AEMO demand traces
