import matplotlib.pyplot as plt

from dp_capability import config
from dp_capability.models.capability import (
    capability_notation,
    capability_numbers_level1,
    failure_numbers_level1,
    information_elements_level1,
    limiting_wind_speed_level1,
    worst_case_numbers,
)
from dp_capability.plotting.capability_plot import plot_envelopes
from dp_capability.standard import ENVIRONMENT_TABLE

if __name__ == "__main__":
    # A.3.6: the intact vessel first, then each redundancy group.
    intact = capability_numbers_level1(
        config.HULL, config.THRUSTERS, config.HEADINGS_DEG, power_sources=config.POWER_SOURCES,
    )
    failures = failure_numbers_level1(
        config.HULL, config.THRUSTERS, config.HEADINGS_DEG, config.REDUNDANCY_GROUPS,
        power_sources=config.POWER_SOURCES,
    )
    worst = worst_case_numbers(failures.values())
    notation = capability_notation(*information_elements_level1(config.HEADINGS_DEG, intact, worst))
    print(notation)

    # [2.4.2], [2.4.7], A.3.1: intact and the combined worst case single
    # failure (Figure A-1), in DP capability numbers and in m/s, and every
    # redundancy group (Figure A-2).
    plot_envelopes(
        config.HEADINGS_DEG, {"Intact": intact, "WCSF (lowest of all groups)": worst},
        title=f"{notation} - DP capability number",
        r_max=ENVIRONMENT_TABLE[-1].bf,
    )
    plot_envelopes(
        config.HEADINGS_DEG,
        {"Intact": limiting_wind_speed_level1(intact), "WCSF (lowest of all groups)": limiting_wind_speed_level1(worst)},
        title=f"{notation} - limiting wind speed [m/s]",
        r_max=ENVIRONMENT_TABLE[-1].wind_speed,
    )
    plot_envelopes(
        config.HEADINGS_DEG, {f"Loss of {name}": numbers for name, numbers in failures.items()},
        title="Worst case single failure - DP capability number",
        r_max=ENVIRONMENT_TABLE[-1].bf,
    )
    plt.show()
