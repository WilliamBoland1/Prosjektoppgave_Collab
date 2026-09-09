import matplotlib.pyplot as plt
import numpy as np

COLUMN_INDEX = {
    "wind": 1,
    "current": 2,
    "wave": 3,
}

TITLES = {
    "wind": "Wind envelope - Limiting wind speed in Beaufort scale",
    "current": "Current envelope - Limiting current speed",
    "wave": "Wave envelope - Limiting significant wave height",
}


def plot_envelope(data, envelope_type="wind", title=None):
    """
    data: list of [angle_deg, windspeed, current, wave_height, thrust]
    envelope_type: "wind", "current" or "wave" - which column to plot as the radius
    """
    if envelope_type not in COLUMN_INDEX:
        raise ValueError(f"envelope_type must be one of {list(COLUMN_INDEX)}, got {envelope_type!r}")

    column = COLUMN_INDEX[envelope_type]
    angles_deg = np.array([row[0] for row in data])
    values = np.array([row[column] for row in data])

    angles_rad = np.deg2rad(angles_deg)

    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    ax.plot(angles_rad, values)

    ax.set_title(title or TITLES[envelope_type])

    return fig, ax


