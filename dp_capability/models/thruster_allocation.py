from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from dp_capability.models.thrust import effective_thrust

# Actuator kinds that can turn their thrust in any direction.
AZIMUTHING = ("azimuth", "pod", "cycloidal")
# LP tolerance, in units of utilisation: a load that needs up to 1 + TOLERANCE
# of the effective thrust still counts as balanced.
TOLERANCE = 1e-6


@dataclass(frozen=True)
class Allocation:
    """Result of allocate_thrust() for one load. The arrays follow the order of the thrusters."""

    fx: np.ndarray  # surge force from each thruster [N]
    fy: np.ndarray  # sway force from each thruster [N]
    # The highest force any thruster needs, as a fraction of its effective
    # thrust (for azimuthing thrusters measured against the inscribed polygon,
    # see allocate_thrust). inf when the thrusters cannot give the load at all.
    utilisation: float

    @property
    def feasible(self):
        """True if the thrusters balance the load within their effective thrust."""
        return self.utilisation <= 1 + TOLERANCE

    @property
    def angle_deg(self):
        """
        Thrust direction of each thruster [deg], as defined in [3.8.2]: 0 deg
        pushes forward, increasing counter-clockwise, so 90 deg pushes to port.
        nan for a thruster that gives no force.
        """
        angle = np.mod(np.rad2deg(np.arctan2(self.fy, self.fx)), 360.0)
        return np.where((self.fx != 0) | (self.fy != 0), angle, np.nan)


def _capacity_rows(thrusters, n_sides):
    """
    The forces each thruster can give, as rows a . (fx_1..fx_n, fy_1..fy_n) <= limit
    with unit vectors a. Also returns, per row, the thruster it belongs to and
    the factor that turns a . f into the size of that thruster's force.
    """
    n = len(thrusters)
    rows, limits, owner, size_factor = [], [], [], []
    for i, thruster in enumerate(thrusters):
        forward = effective_thrust(thruster)
        reverse = effective_thrust(thruster, reverse=True)
        if thruster.kind in AZIMUTHING:
            # Regular polygon inscribed in the circle |f| <= T, with corners
            # every 360/n_sides deg from 0 deg. Side k faces the angle
            # (2k + 1) * pi / n_sides, at T * cos(pi / n_sides) from the centre.
            phi = (2 * np.arange(n_sides) + 1) * np.pi / n_sides
            directions = np.column_stack([np.cos(phi), np.sin(phi)])
            limit = np.full(n_sides, forward * np.cos(np.pi / n_sides))
            factor = 1 / np.cos(np.pi / n_sides)
        elif thruster.kind == "tunnel":
            directions = np.array([[0.0, 1.0], [0.0, -1.0]])
            limit = np.array([forward, reverse])
            factor = 1.0
        else:  # shaft line propeller; rudders are not included yet
            directions = np.array([[1.0, 0.0], [-1.0, 0.0]])
            limit = np.array([forward, reverse])
            factor = 1.0
        block = np.zeros((len(limit), 2 * n))
        block[:, i] = directions[:, 0]
        block[:, n + i] = directions[:, 1]
        rows.append(block)
        limits.append(limit)
        owner += [i] * len(limit)
        size_factor += [factor] * len(limit)
    return np.vstack(rows), np.concatenate(limits), np.array(owner), np.array(size_factor)


def _solve(c, a_ub, b_ub, a_eq, b_eq, bounds):
    """linprog with HiGHS. Returns the solution, or None if the constraints cannot be met."""
    result = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if result.status == 2:
        return None
    if result.status != 0:
        raise RuntimeError(f"thrust allocation LP failed: {result.message}")
    return result.x


def allocate_thrust(thrusters, load, n_sides=36):
    """
    Thruster forces that balance one environmental load, DNV-ST-0111 [2.4.4]
    and [3.11.1]. Forces and moment balance at the same time:

        sum fx_i                    = -Fx
        sum fy_i                    = -Fy
        sum (x_i * fy_i - y_i * fx_i) = -Mz

    [3.11.1] does not prescribe how the forces are found (see its guidance
    note), so the method is our choice. Two linear programs:
    1. Minimise the utilisation u: the highest force any thruster needs, as a
       fraction of its effective thrust [3.9.1]. The load is balanced if u <= 1.
    2. Keep u and minimise the total thrust, so that thrusters with room to
       spare do not push against each other.

    Azimuths, pods and cycloidals push in any direction with their forward
    effective thrust T. The circle |f| <= T is replaced by an inscribed
    polygon, which is conservative by at most 1 - cos(pi / n_sides). Tunnel
    thrusters push along y and shaft line propellers along x, with the
    reversed effective thrust in the negative direction.

    Not vectorized: one call balances one heading.

    Parameters
    ----------
    thrusters : sequence of dp_capability.vessel.Thruster
        The active actuators (Table A-3).
    load : (fx, fy, mz)
        Environmental load for one heading, [N] and [Nm], e.g. from
        environmental_loads_level1() at a single direction.
    n_sides : int, optional
        Sides of the polygon for azimuthing thrusters. The default of 36 puts
        corners every 10 deg, so pure surge and pure sway get the full T.

    Returns
    -------
    Allocation
        Force from each thruster and the utilisation. Forces are nan and the
        utilisation inf when the thrusters cannot give the load in any amount
        (e.g. tunnels only against a surge load).
    """
    load = np.asarray(load, dtype=float)
    if load.shape != (3,):
        raise ValueError(f"load must be (fx, fy, mz) for one heading, got shape {load.shape}")
    n = len(thrusters)
    a_cap, limits, owner, size_factor = _capacity_rows(thrusters, n_sides)
    m = len(limits)

    # Forces in units of the largest limit, so the LP numbers are of order 1.
    # The moment row then has the lever arms in m.
    t_ref = limits.max()
    limits = limits / t_ref
    a_eq = np.zeros((3, 2 * n))
    a_eq[0, :n] = 1.0
    a_eq[1, n:] = 1.0
    a_eq[2, :n] = [-t.y for t in thrusters]
    a_eq[2, n:] = [t.x for t in thrusters]
    b_eq = -load / t_ref
    # Tunnel thrusters give no surge force, shaft line propellers no sway force.
    f_bounds = [(0, 0) if t.kind == "tunnel" else (None, None) for t in thrusters]
    f_bounds += [(0, 0) if t.kind == "shaft_line" else (None, None) for t in thrusters]

    # Pass 1, variables (f, u): the lowest u with every force inside u times
    # its thruster's capacity.
    z = _solve(
        c=np.r_[np.zeros(2 * n), 1.0],
        a_ub=np.column_stack([a_cap, -limits]),
        b_ub=np.zeros(m),
        a_eq=np.column_stack([a_eq, np.zeros(3)]),
        b_eq=b_eq,
        bounds=f_bounds + [(0, None)],
    )
    if z is None:
        return Allocation(np.full(n, np.nan), np.full(n, np.nan), np.inf)
    utilisation = max(z[-1], 0.0)

    # Pass 2, variables (f, t): at that u, the lowest total thrust sum(t_i),
    # with t_i at least the size of thruster i's force.
    size_rows = np.zeros((m, n))
    size_rows[np.arange(m), owner] = -1.0
    z = _solve(
        c=np.r_[np.zeros(2 * n), np.ones(n)],
        a_ub=np.vstack([
            np.column_stack([a_cap, np.zeros((m, n))]),
            np.column_stack([a_cap * size_factor[:, None], size_rows]),
        ]),
        b_ub=np.r_[(utilisation + TOLERANCE) * limits, np.zeros(m)],
        a_eq=np.column_stack([a_eq, np.zeros((3, n))]),
        b_eq=b_eq,
        bounds=f_bounds + [(0, None)] * n,
    )
    if z is None:
        raise RuntimeError("thrust allocation LP failed: second pass found no solution")
    # Drop solver noise, so an idle thruster gets exactly zero force.
    f = np.where(np.abs(z[:2 * n]) < 1e-9, 0.0, z[:2 * n]) * t_ref
    return Allocation(f[:n], f[n:], utilisation)
