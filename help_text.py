from Config import EMISSIONS

#---------------------------------------------------------------------------------------------------------------
# Help tooltips for the key metrics in app.py
# Written for users with little knowledge of energy: plain language, no sources
#---------------------------------------------------------------------------------------------------------------

def renewable_share(show_clean):
    text = (
        "How much of the electricity used came from solar, wind and hydro. Batteries and pumped hydro "
        "only count when they were charged from these sources.\n\n"
        "Rooftop solar isn't included, because it is used in homes before it reaches the grid. "
        "This is why the number is lower than figures you may see in the news.\n\n"
        "A higher share means less pollution, but sun and wind aren't always there, "
        "so storage or backup is needed to fill the gaps."
    )
    if show_clean:     # only shown when nuclear is in the mix
        text += ("\n\nThe clean share also includes nuclear, which doesn't release CO₂ "
                 "but isn't counted as renewable.")
    return text


def avg_cost():
    return (
        "The cost of building and running all the power plants and storage in your mix, "
        "divided by the electricity they supply.\n\n"
        "Plants you build but rarely use still cost money, so building too much raises the cost. "
        "This isn't a household power bill, which also pays for poles, wires and retailers."
    )


def emissions_intensity(year):
    coal = EMISSIONS[year]["BlackCoal"]
    gas = EMISSIONS[year]["Gas"]
    return (
        "How much CO₂ is released, on average, for each unit (MWh) of electricity used.\n\n"
        f"Coal releases about {coal:.0f} kg per MWh and gas about {gas:.0f} kg per MWh. "
        "Solar, wind, hydro, storage and nuclear release none while running.\n\n"
        "Reaching net zero means getting this close to zero."
    )


def unserved_energy(pct_unserved):
    return (
        "Electricity people needed that the grid couldn't supply, which would mean blackouts.\n\n"
        f"Your mix couldn't supply {pct_unserved:.2f}% of demand. A reliable grid keeps this almost at zero.\n\n"
        "Adding storage, or sources that can run whenever needed like gas, should bring this down."
    )


def curtailment():
    return (
        "Electricity that was made but wasted, because demand was already met and storage was full.\n\n"
        "This is mostly solar and wind, but can include coal and nuclear, which can't turn down "
        "below a minimum level.\n\n"
        "Some waste is normal with lots of solar and wind. If a lot is wasted while there are "
        "also shortfalls at other times, more storage would help."
    )
