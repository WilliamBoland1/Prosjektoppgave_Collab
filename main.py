import matplotlib.pyplot as plt

from dp_capability import config
from dp_capability.models.capability import capability_numbers_level1, limiting_wind_speed_level1
from dp_capability.plotting.capability_plot import plot_envelope
from dp_capability.standard import ENVIRONMENT_TABLE

if __name__ == "__main__":
    numbers = capability_numbers_level1(config.HULL, config.THRUSTERS, config.HEADINGS_DEG)

    # [2.4.2]: one plot in DP capability numbers and one in limiting wind speed.
    plot_envelope(
        config.HEADINGS_DEG, numbers,
        title="DP capability level 1 - DP capability number",
        r_max=ENVIRONMENT_TABLE[-1].bf,
    )
    plot_envelope(
        config.HEADINGS_DEG, limiting_wind_speed_level1(numbers),
        title="DP capability level 1 - limiting wind speed [m/s]",
        r_max=ENVIRONMENT_TABLE[-1].wind_speed,
    )
    plt.show()
