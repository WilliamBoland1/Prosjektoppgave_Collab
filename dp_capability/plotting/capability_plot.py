import matplotlib.pyplot as plt
import numpy as np


def plot_envelope(headings_deg, values, title=None, r_max=None):
    """
    Polar capability plot, DNV-ST-0111 [2.4.1]: one value per heading, e.g.
    the DP capability number or the limiting wind speed [m/s] ([2.4.2]).

    Headings are drawn like the environment directions of [2.8.2]: 0 deg
    (head-on) at the top, increasing clockwise, so 90 deg (from starboard)
    is on the right. The last point is joined to the first to close the
    envelope; between points the line is linear, which [2.4.6] allows for
    visualization.

    Parameters
    ----------
    headings_deg : array-like
        Environment directions [deg], in increasing order, not repeating 0 at
        360.
    values : array-like
        Value per heading, drawn as the radius.
    title : str, optional
    r_max : float, optional
        Outer edge of the radial axis. The centre is always 0.

    Returns
    -------
    fig, ax
    """
    fig, ax = _polar_axes()
    ax.plot(*_closed(headings_deg, values))
    _finish(ax, title, r_max)
    return fig, ax


def plot_envelopes(headings_deg, curves, title=None, r_max=None):
    """
    Several capability envelopes in one polar plot, with a legend, like
    Figures A-1 (intact and combined worst case single failure) and A-2
    (each redundancy group) of DNV-ST-0111. Axes as in plot_envelope().

    Parameters
    ----------
    headings_deg : array-like
        Environment directions [deg], as for plot_envelope().
    curves : dict of str to array-like
        Legend label -> value per heading, drawn in this order.
    title : str, optional
    r_max : float, optional

    Returns
    -------
    fig, ax
    """
    fig, ax = _polar_axes()
    for label, values in curves.items():
        ax.plot(*_closed(headings_deg, values), label=label)
    ax.legend(loc="lower left", bbox_to_anchor=(0.9, 0.9))
    _finish(ax, title, r_max)
    return fig, ax


def _polar_axes():
    """Polar axes with 0 deg at the top and angles increasing clockwise."""
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"})
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    return fig, ax


def _finish(ax, title, r_max):
    """Radial axis from 0 (to r_max, or as autoscaled) and the title, after plotting."""
    ax.set_ylim(0, r_max)
    if title is not None:
        ax.set_title(title)


def _closed(headings_deg, values):
    """Angles [rad] and radii with the first point repeated at the end."""
    headings = np.asarray(headings_deg, dtype=float)
    values = np.asarray(values, dtype=float)
    if headings.shape != values.shape or headings.ndim != 1:
        raise ValueError(f"need one value per heading, got shapes {headings.shape} and {values.shape}")
    return np.deg2rad(np.r_[headings, headings[0] + 360.0]), np.r_[values, values[0]]
