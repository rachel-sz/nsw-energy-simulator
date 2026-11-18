import os

#---------------------------------------------------------------------------------------------------------------
# Data files
# 2023: NSW half-hourly generation (via NEMSight)
# 2030/2040: AEMO demand traces (Step Change, POE50, 2018 weather pattern)
#---------------------------------------------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")     # data folder next to this file

DATA_FILES = {
    2023: os.path.join(_DATA_DIR, "nsw_2023_clean.csv"),
    2030: os.path.join(_DATA_DIR, "nsw_demand_2030_step_change_aggregated.csv"),
    2040: os.path.join(_DATA_DIR, "nsw_demand_2040_step_change_aggregated.csv"),
}

GEN_PROFILE_FILE = os.path.join(_DATA_DIR, "nsw_2023_clean.csv")

#---------------------------------------------------------------------------------------------------------------
# Emissions (kg CO2-e/MWh), Scope 1
# Gas and coal: average of NSW stations (AEMO IASR)
#---------------------------------------------------------------------------------------------------------------

EMISSIONS = {
    2023: {
        "Solar": 0,
        "Wind": 0,
        "Hydro": 0,
        "Battery": 0,
        "Nuclear": 0,
        "Gas": 566.4,
        "BlackCoal": 880.4,
    },
    2030: {
        "Solar": 0,
        "Wind": 0,
        "Hydro": 0,
        "Battery": 0,
        "Nuclear": 0,
        "Gas": 568.5,
        "BlackCoal": 870.5,
    },
    2040: {
        "Solar": 0,
        "Wind": 0,
        "Hydro": 0,
        "Battery": 0,
        "Nuclear": 0,
        "Gas": 554.5,
        "BlackCoal": 845.4,
    },
}

#---------------------------------------------------------------------------------------------------------------
# Installed capacity (MW)
# 2023: NSW capacity 2023 table
# 2030/2040: 2026 ISP Step Change
#---------------------------------------------------------------------------------------------------------------

BASELINE_CAPACITY = {
    2023: {
        "Solar": 3379,
        "Wind": 2224,
        "Hydro": 2670,
        "PumpedHydro": 0,
        "Gas": 2041,
        "BlackCoal": 8335,
        "Battery": 200,
    },
    2030: {
        "Solar": 9945,
        "Wind": 7783,
        "Hydro": 2670,
        "PumpedHydro": 2202,    # Snowy 2.0
        "Gas": 3232,
        "BlackCoal": 5465,      # Eraring closes 2027
        "Battery": 11377,
    },
    2040: {
        "Solar": 24497,
        "Wind": 14224,
        "Hydro": 2670,
        "PumpedHydro": 3012,    # Snowy 2.0 + new deep storage
        "Gas": 6472,
        "BlackCoal": 0,         # All coal retired
        "Battery": 11805,
    },
}

#---------------------------------------------------------------------------------------------------------------
# Battery storage
#---------------------------------------------------------------------------------------------------------------

BATTERY_DURATION_H = {      # Storage hours
    2023: 2,
    2030: 4,
    2040: 8,
}

BATTERY_BASELINE_MWH = {
    2023: 375,      # Baseline Capacities sheet
    2030: 45508,    # 11,377 MW × 4 h
    2040: 94440,    # 11,805 MW × 8 h
}

BATTERY_EFFICIENCY = 0.85       # Round trip

#---------------------------------------------------------------------------------------------------------------
# Pumped hydro
#---------------------------------------------------------------------------------------------------------------

SNOWY_2 = {"mw": 2202, "hours": 359660 / 2202}     # From 2030

PUMPED_HYDRO_NEW_DURATION_H = 24        # New pumped hydro entrants have 24 h storage

PUMPED_HYDRO_EFFICIENCY = 0.76          # Round trip

PUMPED_HYDRO_PEAK_HOURS = (16, 22)      # From 4pm to 10pm, dispatched before coal and gas; other times held in reserve

#---------------------------------------------------------------------------------------------------------------
# NSW coal fleet
#---------------------------------------------------------------------------------------------------------------

COAL_UNITS_AT_BASELINE = 12
COAL_AVG_UNIT_MW = 695          # 8,335 MW / 12 units

# Minimum stable level to run reliably (MW per unit)
COAL_MIN_STABLE_PER_UNIT = {
    2023: 171.7,
    2030: 167.5,
    2040: 150,
}

# Maximum ramp rate per unit (MW/min)
COAL_RAMP_MW_PER_MIN = {
    2023: 5.367,
    2030: 5.55,
    2040: 6.0,
}

# Unplanned outages (2030 and 2040): 1 − full outage rate − partial outage rate × derating factor
COAL_AVAILABILITY = 1 - 0.053 - 0.305 * 0.186

#---------------------------------------------------------------------------------------------------------------
# Costs: capital (CRF), fixed and variable O&M, and fuel
# 2023: AEMO 2023 IASR; 2030/2040: AEMO 2025 IASR; nuclear: CSIRO GenCost 2024-25
#---------------------------------------------------------------------------------------------------------------

DISCOUNT_RATE = 0.07    # AEMO 2025 IASR Table 31; CSIRO GenCost 2024-25, Apx Table B.9

# Economic life (years)
ECONOMIC_LIFE = {
    "Solar": 30,
    "Wind": 25,
    "Gas": 25,
    "Battery": 20,
    "BlackCoal": 30,
    "Nuclear": 30,
    "PumpedHydro": 40,
}

#-----------------------------------------------
# Capital cost ($/kW)
# Battery and pumped hydro: cost by storage hours
#-----------------------------------------------

CAPEX = {
    2023: {
        "Solar": 1621.06,
        "Wind": 2827.23,
        "Gas": (1387 + 1824.23) / 2,        # Gas: average of OCGT and CCGT
        "BlackCoal": 6037.2,
        "Battery": {1: 1000.86, 2: 1447.83, 4: 2348.18, 8: 4174.55},
        "PumpedHydro": {8: 3290.24, 24: 4618.31, 48: 6937.62},
    },
    2030: {
        "Solar": 1094,
        "Wind": 2749,
        "Gas": (1729 + 2260) / 2,
        # No coal value for 2030 or 2040; coal added by the user uses the 2023 cost
        "Battery": {1: 563, 2: 794.27, 4: 1152.72, 8: 1946.99},
        "PumpedHydro": {10: 7071, 24: 5983, 48: 7204},
    },
    2040: {
        "Solar": 893,
        "Wind": 2207,
        "Gas": (1366 + 1949) / 2,
        "Nuclear": 9312.8,      # GenCost 2024-25, Table B.9, 2040: average of 9,102 and 9,524
        "Battery": {1: 471, 2: 651.71, 4: 932.76, 8: 1555.96},
        "PumpedHydro": {10: 7273, 24: 6155, 48: 7411},
    },
}

#-----------------------------------------------
# Fixed O&M ($/kW/year), existing plant
# 2040 uses the 2029-30 values
#-----------------------------------------------

_FIXED_OPEX_2030 = {
    "Solar": 12.22,
    "Wind": 28.51,
    "Gas": (73 + 28.5) / 2,     # Gas: average of CCGT and OCGT
    "BlackCoal": 28,
    "Hydro": 91.14,
    "Battery": {1: 9.16, 2: 13.54, 4: 21.59, 8: 37.98},
}

FIXED_OPEX = {
    2023: {
        "Solar": 18.18,
        "Wind": 26.73,
        "Gas": (12.53 + 15.69) / 2,
        "BlackCoal": 64.5,
        "Hydro": 19.09,
        "Battery": {1: 7.59, 2: 10.8, 4: 17.32, 8: 30.69},
    },
    2030: _FIXED_OPEX_2030,
    2040: {**_FIXED_OPEX_2030, "Nuclear": 200},     # Nuclear: GenCost Apx Table B.9
}

#-----------------------------------------------
# Variable O&M ($/MWh), existing plant
# 2040 uses the 2029-30 values
#-----------------------------------------------

_VARIABLE_OPEX_2030 = {
    "Gas": (11 + 10.333) / 2,   # Gas: average of CCGT and OCGT
    "BlackCoal": 8,
}

VARIABLE_OPEX = {
    2023: {
        "Gas": (8.794 + 10.19) / 2,
        "BlackCoal": 5.1,
    },
    2030: _VARIABLE_OPEX_2030,
    2040: {**_VARIABLE_OPEX_2030, "Nuclear": 5.33},
}

#-----------------------------------------------
# New entrant O&M: only for capacity added after 2023
# Coal has no new entrant values; 2040 uses the 2029-30 values
#-----------------------------------------------

_NEW_FIXED_OPEX_2030 = {
    "Solar": 12.22,
    "Wind": 28.51,
    "Gas": (15.3 + 16) / 2,     # Gas: average of CCGT and OCGT
    "PumpedHydro": 85.71,
    "Battery": {1: 9.1647, 2: 13.54339, 4: 21.58796, 8: 37.98259},
}

NEW_FIXED_OPEX = {
    2023: {
        "Solar": 19.69,
        "Wind": 28.96,
        "Gas": (12.63 + 13.21) / 2,
        "PumpedHydro": 20.68,
        "Battery": {1: 8.22, 2: 11.7, 4: 18.77, 8: 33.25},
    },
    2030: _NEW_FIXED_OPEX_2030,
    2040: _NEW_FIXED_OPEX_2030,
}

NEW_VARIABLE_OPEX = {
    2023: {"Gas": (4.21 + 11.18) / 2},
    2030: {"Gas": (4.21 + 15.162) / 2},
    2040: {"Gas": (4.21 + 15.162) / 2},
}

#-----------------------------------------------
# Fuel: (price $/GJ, heat rate GJ/MWh)
#-----------------------------------------------

COAL_FUEL = {       # Average of NSW coal stations
    2023: (3.4207, 10.0582),
    2030: (4.4008, 10.0081),
    2040: (3.2925, 9.7416),
}

GAS_FUEL = {        # Average of NSW gas stations
    2023: (17.3601, 9.6288),
    2030: (13.7675, 10.0629),
    2040: (14.5089, 10.0629),
}

NUCLEAR_FUEL = (0.6, 3.6 / 0.33)    # Large-scale nuclear; heat rate = 3.6 GJ/MWh / 33% efficiency

#---------------------------------------------------------------------------------------------------------------
# 2023 capacity still within its economic life (MW), for capital costs
# Coal and hydro are paid off; 2023 gas (built ~2009, 25-year life) is paid off by 2040
#---------------------------------------------------------------------------------------------------------------

EXISTING_WITHIN_LIFE_MW = {
    2023: {
        "Solar": 3379,
        "Wind": 2224,
        "Gas": 1856,
        "Battery": 200,
    },
    2030: {
        "Solar": 3379,
        "Wind": 2224,
        "Gas": 1856,
        "Battery": 200,
    },
    2040: {
        "Solar": 3379,
        "Wind": 2224,
        "Gas": 0,
        "Battery": 200,
    },
}

#---------------------------------------------------------------------------------------------------------------
# Technologies that can be chosen in each year
#---------------------------------------------------------------------------------------------------------------

TECH_AVAILABILITY = {
    2023: {"nuclear": False},
    2030: {"nuclear": False},
    2040: {"nuclear": True},
}
