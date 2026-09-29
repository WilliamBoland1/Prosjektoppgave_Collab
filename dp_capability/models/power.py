import numpy as np

from dp_capability.standard import (
    BATTERY_MIN_HOURS,
    BATTERY_SOC_HIGH,
    BATTERY_SOC_LOW,
    POWER_RESERVE_FRACTION,
)


def thruster_power_kw(thruster, thrust_fraction):
    """
    Brake power a thruster uses at a fraction of its nominal thrust, from
    DNV-ST-0111 [3.9.2] turned around:

        T_Nominal = eta_1 * eta_2 * (D * P_B * eta_M)^(2/3)
        =>  P = P_B * r^(3/2),   r = T / T_Nominal

    so the full nominal thrust uses exactly P_B. The standard gives no
    part-load relation of its own; this one was agreed with William
    (HANDOVER.md, decisions). r is the thrust before losses as a fraction of
    the nominal thrust in that direction, i.e. of the effective capacity
    after beta_T and beta_skeg.

    Parameters
    ----------
    thruster : dp_capability.vessel.Thruster
    thrust_fraction : float or array-like
        r, 0 for no thrust and 1 for the full nominal thrust.

    Returns
    -------
    numpy.ndarray
        Power [kW], the shape of thrust_fraction.
    """
    return thruster.power_kw * np.asarray(thrust_fraction, dtype=float) ** 1.5


def battery_power_kw(energy_kwh, max_discharge_kw):
    """
    Battery power to use in the calculations, DNV-ST-0111 [3.12.2]: the energy
    between 80% and 20% state of charge (at beginning of life) spread over
    30 minutes, but no more than the maximum discharge rate at 20% state of
    charge. Reductions from battery control or safety functions are left to
    the inputs.

    Parameters
    ----------
    energy_kwh : float
        Nominal maximum energy at beginning of life [kWh].
    max_discharge_kw : float
        Maximum discharge rate at 20% state of charge [kW].

    Returns
    -------
    float
        Power [kW].
    """
    usable_kwh = (BATTERY_SOC_HIGH - BATTERY_SOC_LOW) * energy_kwh
    return min(usable_kwh / BATTERY_MIN_HOURS, max_discharge_kw)


def usable_power_kw(source):
    """
    Power a source can give the thrusters, DNV-ST-0111 [3.12.3]-[3.12.4]:
    90% of a switchboard's available power, since 10% is reserved for hotel
    and other consumers (electrical losses included). A prime mover driving
    a propeller directly reserves nothing.
    """
    return source.available_kw * (1 - POWER_RESERVE_FRACTION) if source.electrical else source.available_kw


def supply_matrix(thrusters, sources):
    """
    Share of each thruster's power taken from each source, the content of
    DNV-ST-0111 Table A-5.

    Parameters
    ----------
    thrusters : sequence of dp_capability.vessel.Thruster
        Each with power_supply = ((source name, share), ...), shares summing to 1.
    sources : sequence of dp_capability.vessel.PowerSource

    Returns
    -------
    numpy.ndarray
        Shares, shape (sources, thrusters).
    """
    index = {s.name: j for j, s in enumerate(sources)}
    if len(index) != len(sources):
        raise ValueError("power sources must have different names")
    shares = np.zeros((len(sources), len(thrusters)))
    for i, t in enumerate(thrusters):
        if not t.power_supply:
            raise ValueError(f"{t.name}: no power_supply, but the run has power sources")
        for name, share in t.power_supply:
            if name not in index:
                raise ValueError(f"{t.name}: unknown power source {name!r}")
            if share < 0:
                raise ValueError(f"{t.name}: negative share {share} of {name!r}")
            shares[index[name], i] += share
        if not np.isclose(shares[:, i].sum(), 1.0):
            raise ValueError(f"{t.name}: power supply shares sum to {shares[:, i].sum()}, not 1")
    return shares
