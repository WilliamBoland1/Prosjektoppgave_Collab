import math

import numpy as np
import pytest

from dp_capability.standard import ENVIRONMENT_TABLE, environment, fold_direction


def test_environment_calm():
    env = environment(0)
    assert (env.wind_speed, env.hs, env.current_speed) == (0.0, 0.0, 0.0)
    assert math.isnan(env.tp)


def test_environment_matches_table_2_1():
    env = environment(6)
    assert env.description == "Strong breeze"
    assert (env.wind_speed, env.hs, env.tp, env.current_speed) == (13.8, 3.1, 8.5, 0.75)

    env = environment(11)
    assert (env.wind_speed, env.hs, env.tp, env.current_speed) == (32.6, 12.1, 12.0, 0.75)


@pytest.mark.parametrize("bf", [-1, 12, 3.5])
def test_environment_outside_table_raises(bf):
    with pytest.raises(ValueError):
        environment(bf)


def test_table_rows_are_ordered_by_bf():
    assert [env.bf for env in ENVIRONMENT_TABLE] == list(range(12))
    wind = [env.wind_speed for env in ENVIRONMENT_TABLE]
    assert all(a < b for a, b in zip(wind, wind[1:]))


def test_fold_direction_mirrors_port_onto_starboard():
    folded = fold_direction(np.deg2rad([0, 90, 180, 270, 360]))
    np.testing.assert_allclose(folded, np.deg2rad([0, 90, 180, 90, 0]), atol=1e-12)
