import numpy as np
import pandas as pd
from Config import (BASELINE_CAPACITY, BATTERY_DURATION_H, BATTERY_EFFICIENCY, COAL_AVAILABILITY, COAL_AVG_UNIT_MW,
                    COAL_MIN_STABLE_PER_UNIT, COAL_RAMP_MW_PER_MIN, GAS_RAMP_SHARE_PER_MIN,
                    ISP_DEEP_STORAGE_DURATION_H, PUMPED_HYDRO_EFFICIENCY, PUMPED_HYDRO_LOOKAHEAD_DAYS,
                    PUMPED_HYDRO_NEW_DURATION_H, SNOWY_2)

from costs import calculate_costs

INTERVAL_HOURS = 0.5        # each step is half an hour

#---------------------------------------------------------------------------------------------------------------
# Year data: the chosen year's demand, solar and wind, with hydro and coal from the 2023 profile
#---------------------------------------------------------------------------------------------------------------

def _calendar_key(timestamps):      # month, day and time of day
    return pd.to_datetime(timestamps).dt.strftime("%m-%d %H:%M")


def _match(df, trace, column, year):     # take a trace column for each half-hour, matched on day and time of day
    values = pd.Series(trace[column].values, index=_calendar_key(trace["datetime"]))
    matched = _calendar_key(df["Time-ending"]).map(values)
    if matched.isna().any():    # error check: every half-hour needs a value
        raise ValueError(f"{year} {column} trace is missing {matched.isna().sum()} half-hours")
    return matched.values


def build_year_dataframe(year, gen_profile, demand_trace, solar_wind_trace=None):
    df = gen_profile.copy()

    if year == 2023:    # 2023 generation and demand line up already
        df["DEMAND_MW"] = demand_trace["demand_mw"].values
        return df

    df["Time-ending"] = df["Time-ending"] + pd.DateOffset(years=year - 2023)     # move dates to 2030 or 2040
    df["DEMAND_MW"] = _match(df, demand_trace, "demand_mw", year)

    # Solar and wind: output per MW from the AEMO traces, stored as if it came from the 2023 fleet,
    # so run_dispatch's scaling (user MW ÷ 2023 MW) gives trace × user MW
    if solar_wind_trace is not None:
        df["Solar_MW"] = _match(df, solar_wind_trace, "solar_cf", year) * BASELINE_CAPACITY[2023]["Solar"]
        df["Wind_MW"] = _match(df, solar_wind_trace, "wind_cf", year) * BASELINE_CAPACITY[2023]["Wind"]
    return df

#---------------------------------------------------------------------------------------------------------------
# Coal minimum: lowest output the fleet can run at reliably (MW)
#---------------------------------------------------------------------------------------------------------------

def calculate_coal_minimum(coal_capacity_mw, year):
    n_units = coal_capacity_mw / COAL_AVG_UNIT_MW
    return n_units * COAL_MIN_STABLE_PER_UNIT[year]

#---------------------------------------------------------------------------------------------------------------
# Deep storage (pumped hydro) energy (MWh), filled in this order:
#   Snowy 2.0 (from 2030): ~163 h
#   ISP new deep storage (the rest of the year's baseline, 2040): ~12 h
#   pumped hydro added by the user: 24 h
#---------------------------------------------------------------------------------------------------------------

def pumped_hydro_storage(pumped_mw, year):
    snowy_mw = min(pumped_mw, SNOWY_2["mw"]) if year >= 2030 else 0       # Snowy 2.0 is only available from 2030
    isp_deep_mw = min(pumped_mw, BASELINE_CAPACITY[year]["PumpedHydro"]) - snowy_mw
    added_mw = pumped_mw - snowy_mw - isp_deep_mw

    return (snowy_mw * SNOWY_2["hours"] + isp_deep_mw * ISP_DEEP_STORAGE_DURATION_H
            + added_mw * PUMPED_HYDRO_NEW_DURATION_H)

#---------------------------------------------------------------------------------------------------------------
# Dispatch: meets demand in each half-hour using the merit order
#---------------------------------------------------------------------------------------------------------------

def run_dispatch(df, capacity_additions, source_toggles, battery_capacity_mwh, year, nuclear_mw=0):
    n = len(df)
    demand = df["DEMAND_MW"].values

    def _user_mw(source, key):      # capacity chosen by the user (0 if the source is switched off)
        if not source_toggles.get(key, True):
            return 0
        return max(0, BASELINE_CAPACITY[year].get(source, 0) + capacity_additions.get(key, 0))

    def _profile_multiplier(source, key):       # user capacity ÷ 2023 capacity, to scale the 2023 profile
        return _user_mw(source, key) / BASELINE_CAPACITY[2023][source]

#-----------------------------------------------
# Solar, wind and existing hydro: 2023 output scaled to the chosen capacity
#-----------------------------------------------
    solar_dispatch = df["Solar_MW"].values * _profile_multiplier("Solar", "solar")
    wind_dispatch = df["Wind_MW"].values * _profile_multiplier("Wind", "wind")
    hydro_dispatch = df["Hydro_MW"].values * _profile_multiplier("Hydro", "hydro")

#-----------------------------------------------
# Nuclear (2040 only): runs flat at 90% of capacity
#-----------------------------------------------
    nuclear_dispatch = np.full(n, nuclear_mw * 0.90)

#-----------------------------------------------
# Coal: maximum, minimum and ramp limits
#-----------------------------------------------
    coal_fleet_mw = _user_mw("BlackCoal", "coal")

    if year == 2023:
        coal_max = df["BlackCoal_MW"].values * _profile_multiplier("BlackCoal", "coal")    # real 2023 outages
    else:
        coal_max = np.full(n, coal_fleet_mw * COAL_AVAILABILITY)       # fleet capacity × availability (outages)

    coal_min_floor = calculate_coal_minimum(coal_fleet_mw, year)        # minimum stable level
    coal_ramp = coal_fleet_mw / COAL_AVG_UNIT_MW * COAL_RAMP_MW_PER_MIN[year] * 30   # max change per half-hour

#-----------------------------------------------
# Battery: power (MW) and storage (MWh)
#-----------------------------------------------
    battery_power = battery_capacity_mwh / BATTERY_DURATION_H[year]
    battery_stored = battery_capacity_mwh * 0.5         # starts half full

#-----------------------------------------------
# Deep storage (pumped hydro): power (MW) and storage (MWh)
#-----------------------------------------------
    pumped_mw = _user_mw("PumpedHydro", "pumped_hydro")
    pumped_mwh = pumped_hydro_storage(pumped_mw, year)
    pumped_stored = pumped_mwh * 0.5                    # starts half full

#-----------------------------------------------
# Gas: maximum output and ramp limit (MW)
#-----------------------------------------------
    gas_max = _user_mw("Gas", "gas")
    gas_ramp = gas_max * GAS_RAMP_SHARE_PER_MIN[year] * 30     # max increase per half-hour

#-----------------------------------------------
# Deep storage look-ahead: water to keep for shortfalls forecast over the next 7 days (MWh)
# Shortfall = demand that must-run, coal at its maximum and gas at its maximum can't cover
#-----------------------------------------------
    firm_gap = np.maximum(0, demand - solar_dispatch - wind_dispatch - hydro_dispatch - nuclear_dispatch
                          - coal_max - gas_max) * INTERVAL_HOURS
    gap_total = np.concatenate([[0.0], np.cumsum(firm_gap)])        # running total, so any window is one subtraction
    window_end = np.minimum(np.arange(n) + 1 + PUMPED_HYDRO_LOOKAHEAD_DAYS * 48, n)
    pumped_keep = gap_total[window_end] - gap_total[np.arange(n) + 1]  # shortfall over the next 7 days

#-----------------------------------------------------------------------
# Storage helpers: discharge, charge, and where stored energy came from
#-----------------------------------------------------------------------
    def _discharge(stored_mwh, power_mw, needed_mw):
        out_mw = min(needed_mw, stored_mwh / INTERVAL_HOURS, power_mw)     # limited by need, energy stored and power
        return out_mw, stored_mwh - out_mw * INTERVAL_HOURS                 # output and new storage level

    def _charge(stored_mwh, capacity_mwh, power_mw, efficiency, surplus_mw):
        in_mw = min(surplus_mw, (capacity_mwh - stored_mwh) / INTERVAL_HOURS, power_mw)   # limited by surplus, space and power
        return in_mw, stored_mwh + in_mw * efficiency * INTERVAL_HOURS       # round-trip losses applied on charging

    def _mix(old_share, old_mwh, new_mwh, added_share):
        # Share of stored energy from one source (coal or nuclear) after charging:
        # the energy added has added_share from that source and mixes with what was already stored
        added_mwh = new_mwh - old_mwh
        return (old_share * old_mwh + added_share * added_mwh) / new_mwh if new_mwh > 0 else 0

#------------------------------------------------------------------------
# Results, filled in each half-hour (MW, storage levels in MWh)
#------------------------------------------------------------------------
    coal_dispatch = np.zeros(n)
    battery_dispatch = np.zeros(n)      # positive = discharging, negative = charging
    pumped_dispatch = np.zeros(n)       # positive = generating, negative = pumping
    gas_dispatch = np.zeros(n)
    shortfall = np.zeros(n)
    curtailment = np.zeros(n)
    battery_soc = np.zeros(n)           # battery storage level
    pumped_soc = np.zeros(n)            # pumped hydro storage level

    # Storage output that was charged from coal or nuclear (MW)
    storage_from_coal = np.zeros(n)
    storage_from_nuclear = np.zeros(n)

    # Share of the energy in each store from coal and nuclear (starting energy assumed renewable)
    battery_coal_share, battery_nuclear_share = 0.0, 0.0
    pumped_coal_share, pumped_nuclear_share = 0.0, 0.0

#-----------------------------------------------
# Merit order, one half-hour at a time
#-----------------------------------------------
    for i in range(n):

# Coal limits this half-hour
        coal_lower = coal_min_floor             # minimum stable level
        coal_upper = coal_max[i]                # maximum available

        if i > 0:       # ramp limits from last half-hour's output
            coal_lower = max(coal_lower, coal_dispatch[i - 1] - coal_ramp)     # ramp-down limit
            coal_upper = min(coal_upper, coal_dispatch[i - 1] + coal_ramp)     # ramp-up limit

        coal_lower = min(coal_lower, coal_max[i])      # the lower limit can't be above the maximum
        coal_upper = max(coal_upper, coal_lower)       # the upper limit can't be below the lower limit

# 1. Must-run: solar, wind, existing hydro, nuclear and coal at its minimum
        coal_dispatch[i] = coal_lower
        must_run = solar_dispatch[i] + wind_dispatch[i] + hydro_dispatch[i] + nuclear_dispatch[i] + coal_lower
        remaining = demand[i] - must_run        # demand still to be met

# 2. Surplus: refill deep storage first (kept full for long shortfalls), then the battery; anything left is curtailed
        if remaining <= 0:
            surplus = -remaining

            # Surplus is assumed to have the same mix as must-run generation this half-hour
            coal_share = coal_lower / must_run if must_run > 0 else 0
            nuclear_share = nuclear_dispatch[i] / must_run if must_run > 0 else 0

            pumped_before = pumped_stored
            pump, pumped_stored = _charge(pumped_stored, pumped_mwh, pumped_mw,
                                          PUMPED_HYDRO_EFFICIENCY, surplus)
            pumped_dispatch[i] = -pump
            surplus -= pump
            pumped_coal_share = _mix(pumped_coal_share, pumped_before, pumped_stored, coal_share)
            pumped_nuclear_share = _mix(pumped_nuclear_share, pumped_before, pumped_stored, nuclear_share)

            battery_before = battery_stored
            charge, battery_stored = _charge(battery_stored, battery_capacity_mwh, battery_power,
                                             BATTERY_EFFICIENCY, surplus)
            battery_dispatch[i] = -charge
            surplus -= charge
            battery_coal_share = _mix(battery_coal_share, battery_before, battery_stored, coal_share)
            battery_nuclear_share = _mix(battery_nuclear_share, battery_before, battery_stored, nuclear_share)

            curtailment[i] = surplus        # surplus that couldn't be stored

        else:
# 3. Battery: cheapest storage to run (smallest losses)
            battery_dispatch[i], battery_stored = _discharge(battery_stored, battery_power, remaining)
            remaining -= battery_dispatch[i]
            storage_from_coal[i] += battery_dispatch[i] * battery_coal_share
            storage_from_nuclear[i] += battery_dispatch[i] * battery_nuclear_share

# 4. Deep storage: only the water above the 7-day need
            if remaining > 0:
                kept = min(pumped_stored, pumped_keep[i])           # water kept for the week ahead
                pumped_dispatch[i], usable = _discharge(pumped_stored - kept, pumped_mw, remaining)
                pumped_stored = usable + kept
                remaining -= pumped_dispatch[i]
                storage_from_coal[i] += pumped_dispatch[i] * pumped_coal_share
                storage_from_nuclear[i] += pumped_dispatch[i] * pumped_nuclear_share

# 5. Coal above its minimum
            if remaining > 0:
                extra_coal = min(remaining, max(0, coal_upper - coal_dispatch[i]))
                coal_dispatch[i] += extra_coal
                remaining -= extra_coal

# 6. Gas, up to its maximum and no faster than its ramp-up limit
            if remaining > 0:
                gas_upper = gas_max if i == 0 else min(gas_max, gas_dispatch[i - 1] + gas_ramp)
                gas_dispatch[i] = min(remaining, gas_upper)
                remaining -= gas_dispatch[i]

# 7. Deep storage reserve: the water kept for the week ahead, used only to prevent a shortfall
            if remaining > 0:
                extra, pumped_stored = _discharge(pumped_stored, pumped_mw - pumped_dispatch[i], remaining)
                pumped_dispatch[i] += extra
                remaining -= extra
                storage_from_coal[i] += extra * pumped_coal_share
                storage_from_nuclear[i] += extra * pumped_nuclear_share

# 8. Anything left is unserved energy
            if remaining > 0:
                shortfall[i] = remaining

# 9. Record storage levels
        battery_soc[i] = battery_stored
        pumped_soc[i] = pumped_stored

# 10. Results for every half-hour
    return pd.DataFrame({
        "Time-ending": df["Time-ending"].values,
        "Demand": demand,
        "Solar_dispatch": solar_dispatch,
        "Wind_dispatch": wind_dispatch,
        "Hydro_dispatch": hydro_dispatch,
        "Battery_dispatch": battery_dispatch,
        "PumpedHydro_dispatch": pumped_dispatch,
        "Gas_dispatch": gas_dispatch,
        "Coal_dispatch": coal_dispatch,
        "Nuclear_dispatch": nuclear_dispatch,
        "Shortfall": shortfall,
        "Curtailment": curtailment,
        "Battery_SOC": battery_soc,
        "PumpedHydro_SOC": pumped_soc,
        "Storage_from_coal": storage_from_coal,
        "Storage_from_nuclear": storage_from_nuclear,
    }, index=df.index)

#---------------------------------------------------------------------------------------------------------------
# Results summary: energy, reliability, renewable share, cost and emissions
#---------------------------------------------------------------------------------------------------------------

def calculate_metrics(results, emissions, capacities_mw, year, storage_hours):

    period_hours = len(results) * INTERVAL_HOURS
    total_demand_mwh = results["Demand"].sum() * INTERVAL_HOURS

    #-----------------------------------------------
    # Energy generated by each source (MWh)
    #-----------------------------------------------
    columns = {
        "Solar": "Solar_dispatch",
        "Wind": "Wind_dispatch",
        "Hydro": "Hydro_dispatch",
        "Battery": "Battery_dispatch",
        "PumpedHydro": "PumpedHydro_dispatch",
        "Gas": "Gas_dispatch",
        "BlackCoal": "Coal_dispatch",
        "Nuclear": "Nuclear_dispatch",
    }

    gen_mwh = {}    # one total (MWh) per source

    for source, column in columns.items():
        output = results[column]
        if source in ("Battery", "PumpedHydro"):
            output = output.clip(lower=0)       # storage: count discharging only, not charging
        gen_mwh[source] = output.sum() * INTERVAL_HOURS

    #-----------------------------------------------
    # Reliability
    #-----------------------------------------------
    unserved_mwh = results["Shortfall"].sum() * INTERVAL_HOURS          # demand not met (MWh)
    curtailed_mwh = results["Curtailment"].sum() * INTERVAL_HOURS       # surplus wasted (MWh)
    pct_unserved = unserved_mwh / total_demand_mwh * 100                # demand not met (%)
    served_mwh = total_demand_mwh - unserved_mwh                        # demand met (MWh)

    #-----------------------------------------------
    # Renewable and clean share (% of demand)
    #-----------------------------------------------
    storage_coal_mwh = results["Storage_from_coal"].sum() * INTERVAL_HOURS         # not clean, not renewable
    storage_nuclear_mwh = results["Storage_from_nuclear"].sum() * INTERVAL_HOURS   # clean, not renewable

    # Clean = demand met by everything except coal, gas and storage charged from coal
    clean_mwh = served_mwh - gen_mwh["BlackCoal"] - gen_mwh["Gas"] - storage_coal_mwh

    # Renewable = clean, minus nuclear and storage charged from nuclear
    renewable_mwh = clean_mwh - gen_mwh["Nuclear"] - storage_nuclear_mwh

    pct_renewable = renewable_mwh / total_demand_mwh * 100
    pct_clean = clean_mwh / total_demand_mwh * 100

    #-----------------------------------------------
    # Costs (calculated in costs.py)
    #-----------------------------------------------
    costs = calculate_costs(gen_mwh, capacities_mw, year, storage_hours, period_hours)

    total_cost = sum(c["total"] for c in costs.values())                  # $
    avg_cost = total_cost / served_mwh if served_mwh > 0 else 0           # $/MWh served

    #-----------------------------------------------
    # Emissions (only coal and gas are above zero)
    #-----------------------------------------------
    total_em_kg = sum(mwh * emissions.get(source, 0) for source, mwh in gen_mwh.items())
    total_em_mt = total_em_kg / 1e9                                       # million tonnes CO2-e
    em_intensity = total_em_kg / served_mwh if served_mwh > 0 else 0      # kg CO2-e per MWh served

    #-----------------------------------------------
    # Metrics passed to the app
    #-----------------------------------------------
    return {
        "pct_renewable": pct_renewable,
        "pct_clean": pct_clean,
        "unserved_mwh": unserved_mwh,
        "pct_unserved": pct_unserved,
        "avg_cost_mwh": avg_cost,
        "total_cost": total_cost,
        "costs": costs,
        "curtailed_mwh": curtailed_mwh,
        "total_demand_mwh": total_demand_mwh,
        "total_emissions_mt": total_em_mt,
        "emissions_intensity": em_intensity,
        "gen_mwh": gen_mwh,
    }
