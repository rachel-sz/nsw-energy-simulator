from Config import (BASELINE_CAPACITY, BATTERY_DURATION_H, CAPEX, COAL_FUEL, DISCOUNT_RATE, ECONOMIC_LIFE,
                    EXISTING_WITHIN_LIFE_MW, FIXED_OPEX, GAS_FUEL, NEW_FIXED_OPEX, NEW_VARIABLE_OPEX,
                    NUCLEAR_FUEL, VARIABLE_OPEX)

HOURS_PER_YEAR = 8760

#---------------------------------------------------------------------------------------------------------------
# Capital recovery factor: turns a build cost into an equal yearly payment
#---------------------------------------------------------------------------------------------------------------

def crf(rate, years):
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)

#---------------------------------------------------------------------------------------------------------------
# Storage costs for a given number of storage hours
# Costs are given for set durations
# Values beyond the longest use the longest (Snowy 2.0, ~163 h, is costed as 48 h)
#---------------------------------------------------------------------------------------------------------------

def _by_duration(table, hours):
    durations = sorted(table)
    hours = min(max(hours, durations[0]), durations[-1])    # keep within the range of the data

    for lo, hi in zip(durations, durations[1:]):
        if lo <= hours <= hi:
            return table[lo] + (table[hi] - table[lo]) * (hours - lo) / (hi - lo)   # straight line between the two

    return table[durations[-1]]     # only used if the table has a single duration

#---------------------------------------------------------------------------------------------------------------
# Cost of each source over the simulated period: capital, fixed O&M and variable O&M + fuel
#---------------------------------------------------------------------------------------------------------------

def calculate_costs(gen_mwh, capacities_mw, year, storage_hours, period_hours):

    period_share = period_hours / HOURS_PER_YEAR          # share of a year being simulated
    battery_duration_h = storage_hours["Battery"]
    gas_fuel_price, gas_heat_rate = GAS_FUEL[year]
    coal_fuel_price, coal_heat_rate = COAL_FUEL[year]

    #-----------------------------------------------
    # Capital cost ($/kW)
    #-----------------------------------------------
    # New capacity (added after 2023): scenario-year cost
    capex_new = {
        "Solar": CAPEX[year].get("Solar"),
        "Wind": CAPEX[year].get("Wind"),
        "Gas": CAPEX[year].get("Gas"),
        "BlackCoal": CAPEX[2023]["BlackCoal"],      # No new entrant CAPEX for coal
        "Battery": _by_duration(CAPEX[year]["Battery"], battery_duration_h),
        "PumpedHydro": _by_duration(CAPEX[year]["PumpedHydro"], storage_hours.get("PumpedHydro", 0)),
        "Nuclear": CAPEX[year].get("Nuclear"),
    }
    # 2023 capacity still being paid off: 2023 cost
    capex_existing = {
        "Solar": CAPEX[2023]["Solar"],
        "Wind": CAPEX[2023]["Wind"],
        "Gas": CAPEX[2023]["Gas"],
        "Battery": _by_duration(CAPEX[2023]["Battery"], BATTERY_DURATION_H[2023]),
    }

    #-----------------------------------------------
    # Fixed O&M ($/kW/year)
    #-----------------------------------------------
    # 2023 capacity
    fixed_opex = {
        "Solar": FIXED_OPEX[year]["Solar"],
        "Wind": FIXED_OPEX[year]["Wind"],
        "Hydro": FIXED_OPEX[year]["Hydro"],
        "PumpedHydro": FIXED_OPEX[year]["Hydro"],
        "Gas": FIXED_OPEX[year]["Gas"],
        "BlackCoal": FIXED_OPEX[year]["BlackCoal"],
        "Battery": _by_duration(FIXED_OPEX[year]["Battery"], battery_duration_h),
        "Nuclear": FIXED_OPEX[year].get("Nuclear", 0),
    }
    # New capacity (new entrant values; sources not listed use the values above)
    fixed_opex_new = {
        "Solar": NEW_FIXED_OPEX[year]["Solar"],
        "Wind": NEW_FIXED_OPEX[year]["Wind"],
        "PumpedHydro": NEW_FIXED_OPEX[year]["PumpedHydro"],
        "Gas": NEW_FIXED_OPEX[year]["Gas"],
        "Battery": _by_duration(NEW_FIXED_OPEX[year]["Battery"], battery_duration_h),
    }

    #-----------------------------------------------
    # Variable O&M + fuel ($/MWh)
    #-----------------------------------------------
    # Gas variable O&M: existing and new entrant values, weighted by MW
    gas_mw = capacities_mw.get("Gas", 0)
    gas_new_share = max(0, gas_mw - BASELINE_CAPACITY[2023]["Gas"]) / gas_mw if gas_mw > 0 else 0
    gas_variable_om = ((1 - gas_new_share) * VARIABLE_OPEX[year]["Gas"]
                       + gas_new_share * NEW_VARIABLE_OPEX[year]["Gas"])

    variable_per_mwh = {
        "Gas": gas_variable_om + gas_fuel_price * gas_heat_rate,
        "BlackCoal": VARIABLE_OPEX[year]["BlackCoal"] + coal_fuel_price * coal_heat_rate,
        "Nuclear": VARIABLE_OPEX[year].get("Nuclear", 0) + NUCLEAR_FUEL[0] * NUCLEAR_FUEL[1],
    }

    #-----------------------------------------------
    # Total cost of each source ($)
    #-----------------------------------------------
    costs = {}

    for source, mw in capacities_mw.items():
       
        mwh = gen_mwh.get(source, 0)

        new_mw = max(0, mw - BASELINE_CAPACITY[2023].get(source, 0))   # added after 2023
        
        existing_mw = mw - new_mw   # 2023 capacity
        
        within_life_mw = min(mw, EXISTING_WITHIN_LIFE_MW[year].get(source, 0))  # 2023 capacity still being paid off

        # Capital: yearly payment on new capacity and on 2023 capacity still being paid off
        capital = 0.0
        
        if new_mw > 0 and capex_new.get(source):
            
            capital += new_mw * capex_new[source] * 1000 * crf(DISCOUNT_RATE, ECONOMIC_LIFE[source])
            
        if within_life_mw > 0:
            
            capital += within_life_mw * capex_existing[source] * 1000 * crf(DISCOUNT_RATE, ECONOMIC_LIFE[source])
        
        capital *= period_share

        # Fixed O&M: 2023 capacity at existing values, new capacity at new entrant values
        new_rate = fixed_opex_new.get(source, fixed_opex.get(source, 0))    # no new entrant value: use existing
        
        fixed = (existing_mw * fixed_opex.get(source, 0) + new_mw * new_rate) * 1000 * period_share

        # Variable O&M + fuel: per MWh generated
        variable = max(mwh, 0) * variable_per_mwh.get(source, 0)

        costs[source] = {
            "capital": capital,
            "fixed": fixed,
            "variable": variable,
            "total": capital + fixed + variable,
            "mwh": mwh,
            # Not shown in the app; kept for the results chapter
            "capacity_mw": mw,
            "capacity_factor": mwh / (mw * period_hours) if mw > 0 else 0,
        }

    return costs
