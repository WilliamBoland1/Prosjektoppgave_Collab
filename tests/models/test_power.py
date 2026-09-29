import dataclasses

import numpy as np
import pytest

from dp_capability.models.power import battery_power_kw, supply_matrix, thruster_power_kw, usable_power_kw
from dp_capability.models.thrust import nominal_thrust
from dp_capability.vessel import PowerSource, Thruster


@pytest.fixture
def thruster():
    # Round default data: P_B = 1000 kW on SWBD 1; tests override what they need.
    def make(**overrides):
        fields = dict(name="T", kind="azimuth", diameter=2.0, power_kw=1000.0, x=0.0, y=0.0, z=2.0,
                      power_supply=(("SWBD 1", 1.0),))
        fields.update(overrides)
        return Thruster(**fields)

    return make


@pytest.mark.parametrize("fraction, power", [
    (0.0, 0.0),
    (1.0, 1000.0),  # the full nominal thrust uses P_B
    (0.25, 125.0),  # 0.25^1.5 = 0.125
    (0.5, 353.5534),  # 0.5^1.5 = 0.353553
    (0.81, 729.0),  # 0.9^3 = 0.729
])
def test_thruster_power_is_p_b_times_fraction_to_1_5(thruster, fraction, power):
    assert thruster_power_kw(thruster(), fraction) == pytest.approx(power, abs=1e-3)


@pytest.mark.parametrize("fraction", [0.1, 0.25, 0.5, 0.9])
def test_thruster_power_turns_the_nominal_thrust_formula_around(thruster, fraction):
    # [3.9.2]: T = eta_1 * eta_2 * (D * P_B * eta_M)^(2/3). At P_B * r^1.5 the
    # nominal thrust is (r^1.5)^(2/3) = r times the thrust at P_B.
    full = thruster()
    part = dataclasses.replace(full, power_kw=float(thruster_power_kw(full, fraction)))
    assert nominal_thrust(part) == pytest.approx(fraction * nominal_thrust(full))


def test_thruster_power_is_vectorised(thruster):
    assert thruster_power_kw(thruster(), np.zeros((2, 3))).shape == (2, 3)


def test_battery_power_from_the_guidance_note():
    # [3.12.2] guidance note 1: 1000 kWh used from 80% to 20% gives 600 kWh,
    # i.e. 1200 kW for 30 minutes, if the discharge rate allows it...
    assert battery_power_kw(1000.0, 2000.0) == pytest.approx(1200.0)
    # ... and otherwise the maximum discharge rate at 20% state of charge.
    assert battery_power_kw(1000.0, 800.0) == pytest.approx(800.0)


def test_switchboard_reserves_ten_percent():
    # [3.12.3]: 10% of 3600 kW for hotel and other consumers, 3240 kW for thrusters.
    assert usable_power_kw(PowerSource("SWBD 1", 3600.0)) == pytest.approx(3240.0)


def test_prime_mover_reserves_nothing():
    # Driving a propeller directly: no electrical power, nothing reserved.
    assert usable_power_kw(PowerSource("PM1", 3000.0, electrical=False)) == pytest.approx(3000.0)


def test_supply_matrix_is_table_a_5(thruster):
    # Like Table A-5: THR 1 on SWBD 1, THR 2 split 50/50, THR 3 on the prime mover.
    sources = (PowerSource("SWBD 1", 1000.0), PowerSource("SWBD 2", 1000.0), PowerSource("PM1", 500.0, electrical=False))
    thrusters = [
        thruster(),
        thruster(power_supply=(("SWBD 1", 0.5), ("SWBD 2", 0.5))),
        thruster(power_supply=(("PM1", 1.0),)),
    ]
    np.testing.assert_allclose(supply_matrix(thrusters, sources), [[1.0, 0.5, 0.0], [0.0, 0.5, 0.0], [0.0, 0.0, 1.0]])


@pytest.mark.parametrize("supply, message", [
    ((), "no power_supply"),
    ((("SWBD 9", 1.0),), "unknown power source"),
    ((("SWBD 1", 0.6),), "sum to"),
    ((("SWBD 1", 1.5), ("SWBD 1", -0.5)), "negative"),
])
def test_supply_matrix_rejects_an_incomplete_table_a_5(thruster, supply, message):
    with pytest.raises(ValueError, match=message):
        supply_matrix([thruster(power_supply=supply)], (PowerSource("SWBD 1", 1000.0),))


def test_supply_matrix_rejects_two_sources_with_one_name(thruster):
    with pytest.raises(ValueError, match="different names"):
        supply_matrix([thruster()], (PowerSource("SWBD 1", 1000.0), PowerSource("SWBD 1", 500.0)))
