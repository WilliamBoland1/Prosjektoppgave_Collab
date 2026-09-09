import matplotlib.pyplot as plt

from dp_capability.plotting.capability_plot import plot_envelope

# angle_deg, windspeed, current, significant_wave_height, thrust
sample_data = [
    [0, 9, 1.5, 2.0, 70],
    [30, 8, 1.4, 1.9, 68],
    [60, 6, 1.2, 1.6, 60],
    [90, 4, 1.0, 1.3, 50],
    [120, 6, 1.2, 1.6, 60],
    [150, 8, 1.4, 1.9, 68],
    [180, 9, 1.5, 2.0, 70],
    [210, 8, 1.4, 1.9, 68],
    [240, 6, 1.2, 1.6, 60],
    [270, 4, 1.0, 1.3, 50],
    [300, 6, 1.2, 1.6, 60],
    [330, 8, 1.4, 1.9, 68],
    [360, 9, 1.5, 2.0, 70],  # closes the loop back to angle 0
]

if __name__ == "__main__":
    fig, ax = plot_envelope(sample_data, envelope_type="wave")
    plt.show()
