import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from dp_capability.plotting.capability_plot import plot_envelope, plot_envelopes

HEADINGS = np.arange(0, 360, 10)
VALUES = np.arange(36) % 12


def test_envelope_is_closed():
    # 36 headings give 37 points: the first one again, at 360 deg.
    fig, ax = plot_envelope(HEADINGS, VALUES)
    angles, radii = ax.lines[0].get_data()
    assert len(angles) == 37
    assert angles[-1] == pytest.approx(angles[0] + 2 * np.pi)
    assert radii[-1] == radii[0]
    plt.close(fig)


def test_north_up_and_clockwise():
    # [2.8.2]: 0 deg (head-on) at the top, 90 deg (from starboard) on the right.
    fig, ax = plot_envelope(HEADINGS, VALUES)
    assert ax.get_theta_offset() == pytest.approx(np.pi / 2)
    assert ax.get_theta_direction() == -1
    plt.close(fig)


def test_r_max_sets_the_radial_axis():
    fig, ax = plot_envelope(HEADINGS, VALUES, title="DP capability number", r_max=11)
    assert ax.get_ylim() == pytest.approx((0, 11))
    assert ax.get_title() == "DP capability number"
    plt.close(fig)


def test_rejects_values_that_do_not_match_the_headings():
    with pytest.raises(ValueError):
        plot_envelope(HEADINGS, VALUES[:-1])


def test_envelopes_draw_one_closed_line_per_curve_with_a_legend():
    # Figure A-1 style: intact and the combined worst case single failure.
    fig, ax = plot_envelopes(HEADINGS, {"Intact": VALUES, "WCSF": VALUES // 2}, r_max=11)
    assert len(ax.lines) == 2
    for line in ax.lines:
        angles, radii = line.get_data()
        assert len(angles) == 37
        assert radii[-1] == radii[0]
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["Intact", "WCSF"]
    assert ax.get_theta_direction() == -1
    assert ax.get_ylim() == pytest.approx((0, 11))
    plt.close(fig)


def test_envelopes_reject_a_curve_that_does_not_match_the_headings():
    with pytest.raises(ValueError):
        plot_envelopes(HEADINGS, {"Intact": VALUES, "WCSF": VALUES[:-1]})
