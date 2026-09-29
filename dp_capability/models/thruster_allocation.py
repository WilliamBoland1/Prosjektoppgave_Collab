from dataclasses import dataclass
from itertools import product

import numpy as np
from scipy.optimize import linprog

from dp_capability.models.forbidden_zones import allowed_arcs, forbidden_zones_level1
from dp_capability.models.rudders import max_rudder_angle_deg, rudder_forces
from dp_capability.models.skeg_loss import skeg_loss_breakpoints, skeg_loss_factor
from dp_capability.models.thrust import effective_thrust
from dp_capability.standard import BETA_MISC

# Actuator kinds that can turn their thrust in any direction.
AZIMUTHING = ("azimuth", "pod", "cycloidal")
# LP tolerance, in units of utilisation: a load that needs up to 1 + TOLERANCE
# of the effective thrust still counts as balanced.
TOLERANCE = 1e-6
# Corner spacing [deg] of an azimuth's capacity polygon where the skeg loss
# factor changes. The chords lie inside the true curve, so the polygon stays
# conservative, by far less than the 1 - cos(5 deg) of the 36-gon.
RAMP_STEP_DEG = 1.0
# Rudder angle spacing [deg] of the corners of a shaft line's rudder fan. The
# [3.10.1] forces lie on a parabola, and the chords between corners inside it.
RUDDER_STEP_DEG = 1.0


@dataclass(frozen=True)
class Allocation:
    """Result of allocate_thrust() for one load. The arrays follow the order of the thrusters."""

    fx: np.ndarray  # surge force from each thruster [N]
    fy: np.ndarray  # sway force from each thruster [N]
    # The highest force any thruster needs, as a fraction of its effective
    # thrust (for azimuthing thrusters measured against their capacity
    # polygon, see allocate_thrust). inf when the thrusters cannot give the load at all.
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


def _inside(angle_deg, zones):
    """True if the direction lies strictly inside one of the zones [deg]."""
    for start, end in zones:
        if end - start >= 360.0 or 0.0 < (angle_deg - start) % 360.0 < end - start:
            return True
    return False


def _polygon_angles(arc, n_sides, skeg_breakpoints):
    """
    Corner angles [deg] of an azimuth's capacity polygon over one allowed arc
    (None: the full circle, returned without repeating 360): every
    360/n_sides deg from 0, the arc ends, the skeg breakpoints, and every
    RAMP_STEP_DEG where the skeg loss factor changes.
    """
    candidates = list(np.arange(n_sides) * 360.0 / n_sides)
    for angles, factors in skeg_breakpoints:
        candidates += list(angles)
        for k in range(len(angles) - 1):
            if factors[k] < 1 or factors[k + 1] < 1:
                candidates += list(np.arange(angles[k], angles[k + 1], RAMP_STEP_DEG))
    candidates = np.mod(candidates, 360.0)
    if arc is None:
        corners = candidates
    else:
        start, end = arc
        # Unwrap into the arc's range, which may run past 360 deg.
        shifted = start + np.mod(candidates - start, 360.0)
        corners = np.r_[start, shifted[shifted < end], end]
    corners = np.unique(np.round(corners, 9))
    if arc is None:
        corners = corners[corners < 360.0]
    return corners


def _convex_fans(angles, radii, closed):
    """
    Split a star-shaped polygon (corners at the given angles [deg] and radii,
    seen from the origin) into convex pieces: fans of consecutive corners
    that, together with the origin, form a convex polygon. A fan grows while
    each corner turns left and it spans at most 180 deg; a corner that turns
    right (e.g. the bottom of the skeg loss dip) starts a new one.

    Returns a list of (angles, radii, closed) per piece; closed is True only
    for a whole closed ring that is convex as it is.
    """
    theta = np.deg2rad(angles)
    points = np.column_stack([radii * np.cos(theta), radii * np.sin(theta)])
    scale = max(radii.max(), 1e-300)

    def turns_left(p0, p1, p2):
        e1, e2 = p1 - p0, p2 - p1
        return e1[0] * e2[1] - e1[1] * e2[0] >= -1e-9 * scale ** 2

    m = len(angles)
    if closed:
        reflex = [k for k in range(m) if not turns_left(points[k - 1], points[k], points[(k + 1) % m])]
        if not reflex:
            return [(angles, radii, True)]
        # Open the ring at a right-turning corner, which a fan boundary has
        # to pass through anyway.
        order = np.r_[np.arange(reflex[0], m), np.arange(reflex[0] + 1)]
        angles = np.r_[angles[reflex[0]:], angles[:reflex[0] + 1] + 360.0]
        radii, points = radii[order], points[order]
        m = len(angles)
    fans, i = [], 0
    while i < m - 1:
        j = i + 1
        while j + 1 < m and angles[j + 1] - angles[i] <= 180.0 + 1e-9 and turns_left(points[j - 1], points[j], points[j + 1]):
            j += 1
        fans.append((angles[i:j + 1], radii[i:j + 1], False))
        i = j
    return fans


def _fan_rows(angles, radii, closed):
    """
    Rows a . (fx, fy) <= limit of one convex piece: one per outer edge, with
    its unit outward normal and the distance of the edge from the origin
    (this limit scales with u), and for an open fan the two boundary rays
    (limit 0, fixed).
    """
    theta = np.deg2rad(angles)
    points = np.column_stack([radii * np.cos(theta), radii * np.sin(theta)])
    ends = np.roll(points, -1, axis=0) if closed else points[1:]
    starts = points if closed else points[:-1]
    edges = ends - starts
    length = np.hypot(edges[:, 0], edges[:, 1])
    keep = length > 1e-12 * max(radii.max(), 1e-300)
    normals = np.column_stack([edges[keep, 1], -edges[keep, 0]]) / length[keep, None]
    limits = np.maximum(np.einsum("ij,ij->i", normals, starts[keep]), 0.0)
    if closed:
        return normals, limits, np.ones(len(limits), dtype=bool)
    a, b = theta[0], theta[-1]
    # Left of the ray at the first corner and right of the ray at the last.
    rays = np.array([[np.sin(a), -np.cos(a)], [-np.sin(b), np.cos(b)]])
    scales = np.r_[np.ones(len(limits), dtype=bool), False, False]
    return np.vstack([normals, rays]), np.r_[limits, 0.0, 0.0], scales


def _no_force():
    """The piece of a thruster that can give no force at all."""
    directions = np.array([[1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])
    return (directions, np.zeros(4), np.ones(4, dtype=bool))


def _along_x(sign, limit):
    """The piece of a force along sign * x only, up to limit (times u)."""
    directions = np.array([[sign, 0.0], [-sign, 0.0], [0.0, 1.0], [0.0, -1.0]])
    return (directions, np.array([limit, 0.0, 0.0, 0.0]), np.array([True, False, False, False]))


def _rudder_pieces(thruster, forward, reverse, zones, skegs):
    """
    The pieces of a shaft line propeller with a rudder. With positive thrust,
    the [3.10.1] forces over the rudder angles -alpha_max..alpha_max, drawn
    as a fan with corners every RUDDER_STEP_DEG; with negative thrust, the
    rudder is neglected ([3.10.2]) and the force is along -x only. The
    propeller gives one or the other, so they are separate pieces.

    Forbidden zones and the skeg loss follow the propeller shaft (0 or
    180 deg), not the direction of the deflected force: [3.11.3] takes the
    thrust direction as the vector through the propeller shaft.
    """
    limit = max_rudder_angle_deg(thruster)  # also checks that it is a shaft line
    pieces = []
    if not _inside(0.0, zones):
        t = forward * float(skeg_loss_factor(thruster, skegs, 0.0))
        alpha = np.unique(np.r_[np.arange(-limit, limit, RUDDER_STEP_DEG), limit])
        f_surge, f_sway = rudder_forces(thruster, t, alpha)
        if len(alpha) > 1 and t > 0 and f_sway[-1] > 0:
            angles = np.rad2deg(np.arctan2(f_sway, f_surge))
            radii = np.hypot(f_surge, f_sway)
            pieces += [_fan_rows(*fan) for fan in _convex_fans(angles, radii, False)]
        else:
            # No rudder angle or no lift: the plain forward thrust.
            pieces.append(_along_x(1.0, t))
    if not _inside(180.0, zones):
        pieces.append(_along_x(-1.0, reverse * float(skeg_loss_factor(thruster, skegs, 180.0))))
    return pieces or [_no_force()]


def _thruster_pieces(thruster, beta_t, n_sides, zones, skegs):
    """
    The convex pieces one thruster's force can be chosen from, each as rows
    (directions, limits, scales): directions . f <= limits, times u where
    scales is True. An azimuth's capacity is the polygon with radius
    T * beta_skeg(angle) over its allowed directions, split into convex fans;
    a shaft line with a rudder has a rudder fan and reversed thrust (see
    _rudder_pieces); tunnel thrusters and other shaft line propellers have
    one piece.
    """
    beta_forward, beta_reverse = beta_t
    forward = effective_thrust(thruster, beta_t=beta_forward)
    reverse = effective_thrust(thruster, reverse=True, beta_t=beta_reverse)
    if thruster.rudder is not None:
        return _rudder_pieces(thruster, forward, reverse, zones, skegs)
    if thruster.kind in AZIMUTHING:
        arcs = allowed_arcs(zones)
        if not arcs:
            # Every direction forbidden: no force at all.
            return [_no_force()]
        breakpoints = [b for b in (skeg_loss_breakpoints(thruster, skeg) for skeg in skegs) if b is not None]
        pieces = []
        for arc in arcs:
            angles = _polygon_angles(arc, n_sides, breakpoints)
            radii = forward * skeg_loss_factor(thruster, skegs, angles)
            pieces += [_fan_rows(*fan) for fan in _convex_fans(angles, radii, arc is None)]
        return pieces
    if thruster.kind == "tunnel":
        directions = np.array([[0.0, 1.0], [0.0, -1.0]])
        angles = np.array([90.0, 270.0])
    else:  # shaft line propeller without a rudder
        directions = np.array([[1.0, 0.0], [-1.0, 0.0]])
        angles = np.array([0.0, 180.0])
    limits = np.array([forward, reverse]) * skeg_loss_factor(thruster, skegs, angles)
    # A direction inside a forbidden zone is not available at all.
    limits = np.where([_inside(a, zones) for a in angles], 0.0, limits)
    return [(directions, limits, np.ones(2, dtype=bool))]


def _size_rows(thruster, n_sides):
    """
    Rows that measure the size of a thruster's force for pass 2: t >= a . f
    for each row a. For azimuthing thrusters and shaft lines with a rudder a
    regular n_sides-gon of unit size, scaled so it equals |f| at its corners.
    """
    if thruster.kind in AZIMUTHING or thruster.rudder is not None:
        phi = (2 * np.arange(n_sides) + 1) * np.pi / n_sides
        return np.column_stack([np.cos(phi), np.sin(phi)]) / np.cos(np.pi / n_sides)
    if thruster.kind == "tunnel":
        return np.array([[0.0, 1.0], [0.0, -1.0]])
    return np.array([[1.0, 0.0], [-1.0, 0.0]])


def _solve(c, a_ub, b_ub, a_eq, b_eq, bounds):
    """linprog with HiGHS. Returns the solution, or None if the constraints cannot be met."""
    result = linprog(c, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if result.status == 2:
        return None
    if result.status != 0:
        raise RuntimeError(f"thrust allocation LP failed: {result.message}")
    return result.x


def _place(blocks, n):
    """Stack per-thruster rows (k x 2 over (fx_i, fy_i)) into rows over (fx_1..fx_n, fy_1..fy_n)."""
    rows = []
    for i, block in enumerate(blocks):
        full = np.zeros((len(block), 2 * n))
        full[:, i] = block[:, 0]
        full[:, n + i] = block[:, 1]
        rows.append(full)
    return np.vstack(rows)


@dataclass(frozen=True)
class _Problem:
    """One convex allocation problem: every thruster's force in one convex piece."""

    a_cap: np.ndarray  # capacity rows over the forces
    limits: np.ndarray  # in units of t_ref
    scales: np.ndarray  # True where the limit is multiplied by u
    a_size: np.ndarray  # size rows over the forces, for pass 2
    size_owner: np.ndarray  # thruster of each size row
    a_eq: np.ndarray
    b_eq: np.ndarray
    f_bounds: list
    t_ref: float


def _problem(thrusters, load, pieces, a_size, size_owner, t_ref):
    n = len(thrusters)
    a_eq = np.zeros((3, 2 * n))
    a_eq[0, :n] = 1.0
    a_eq[1, n:] = 1.0
    a_eq[2, :n] = [-t.y for t in thrusters]
    a_eq[2, n:] = [t.x for t in thrusters]
    # Tunnel thrusters give no surge force, shaft line propellers without a
    # rudder no sway force.
    f_bounds = [(0, 0) if t.kind == "tunnel" else (None, None) for t in thrusters]
    f_bounds += [(0, 0) if t.kind == "shaft_line" and t.rudder is None else (None, None) for t in thrusters]
    return _Problem(
        a_cap=_place([p[0] for p in pieces], n),
        # Forces in units of t_ref, so the LP numbers are of order 1. The
        # moment row then has the lever arms in m.
        limits=np.concatenate([p[1] for p in pieces]) / t_ref,
        scales=np.concatenate([p[2] for p in pieces]),
        a_size=a_size,
        size_owner=size_owner,
        a_eq=a_eq,
        b_eq=-load / t_ref,
        f_bounds=f_bounds,
        t_ref=t_ref,
    )


def _min_utilisation(p):
    """Pass 1, variables (f, u): the lowest u with every force inside u times its capacity. None if impossible."""
    m, n2 = p.a_cap.shape
    z = _solve(
        c=np.r_[np.zeros(n2), 1.0],
        a_ub=np.column_stack([p.a_cap, -np.where(p.scales, p.limits, 0.0)]),
        b_ub=np.where(p.scales, 0.0, p.limits),
        a_eq=np.column_stack([p.a_eq, np.zeros(3)]),
        b_eq=p.b_eq,
        bounds=p.f_bounds + [(0, None)],
    )
    return None if z is None else max(z[-1], 0.0)


def _least_total_thrust(p, utilisation):
    """Pass 2, variables (f, t): at that u, the lowest total thrust sum(t_i), with t_i >= |f_i|."""
    m, n2 = p.a_cap.shape
    n = n2 // 2
    k = len(p.size_owner)
    size_t = np.zeros((k, n))
    size_t[np.arange(k), p.size_owner] = -1.0
    z = _solve(
        c=np.r_[np.zeros(n2), np.ones(n)],
        a_ub=np.vstack([
            np.column_stack([p.a_cap, np.zeros((m, n))]),
            np.column_stack([p.a_size, size_t]),
        ]),
        b_ub=np.r_[np.where(p.scales, (utilisation + TOLERANCE) * p.limits, p.limits), np.zeros(k)],
        a_eq=np.column_stack([p.a_eq, np.zeros((3, n))]),
        b_eq=p.b_eq,
        bounds=p.f_bounds + [(0, None)] * n,
    )
    if z is None:
        raise RuntimeError("thrust allocation LP failed: second pass found no solution")
    # Drop solver noise, so an idle thruster gets exactly zero force.
    f = np.where(np.abs(z[:n2]) < 1e-9, 0.0, z[:n2]) * p.t_ref
    return f[:n], f[n:]


def allocate_thrust(thrusters, load, n_sides=36, beta_t=None, forbidden_zones=True, skegs=()):
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
    effective thrust T, times the skeg loss factor of that direction
    ([3.11.5]). This capacity is drawn as a polygon inside the true curve,
    with corners every 360/n_sides deg (every 1 deg where the skeg loss
    changes), so it is conservative by at most 1 - cos(pi / n_sides). Tunnel
    thrusters push along y and shaft line propellers along x, with the
    reversed effective thrust in the negative direction. A shaft line with a
    rudder adds the [3.10.1] side force with positive thrust: its forward
    capacity is the fan of propeller + rudder forces over the rudder angles
    (corners every RUDDER_STEP_DEG, so again inside the true curve), while
    reversed thrust stays along -x ([3.10.2]).

    Forbidden zones ([3.11.2] user zones and [3.11.3] flushing sectors, see
    forbidden_zones_level1()) take directions away, and the skeg loss dents
    the polygon; both make it non-convex. The polygon is split into convex
    pieces, pass 1 is solved for every combination of pieces and the lowest
    u is kept; pass 2 is solved in the first combination that reaches it. A
    tunnel or shaft line direction inside a zone is not available; for a
    shaft line with a rudder the zones are checked on the shaft direction.

    Not vectorized: one call balances one heading.

    Parameters
    ----------
    thrusters : sequence of dp_capability.vessel.Thruster
        The working actuators (Table A-3). The flushing sectors are found
        among these.
    load : (fx, fy, mz)
        Environmental load for one heading, [N] and [Nm], e.g. from
        environmental_loads_level1() at a single direction.
    n_sides : int, optional
        Corners of the polygon for azimuthing thrusters. The default of 36
        puts corners every 10 deg, so pure surge and pure sway get the full T.
    beta_t : sequence of (float, float), optional
        Thrust loss factor beta_T [3.9.1] per thruster, as a (forward, reverse)
        pair, e.g. from thrust_loss_factor_level1(). None gives beta_misc for
        every thruster, i.e. no ventilation loss.
    forbidden_zones : bool, optional
        False ignores all forbidden zones, e.g. to see their effect. Level 1
        includes them.
    skegs : sequence of (float, float), optional
        Aft most point of each skeg or gondola (Hull.skegs) for the skeg loss
        of [3.11.5]. Empty: no skeg loss.

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
    if beta_t is None:
        beta_t = [(BETA_MISC, BETA_MISC)] * n
    if len(beta_t) != n:
        raise ValueError(f"beta_t needs one (forward, reverse) pair per thruster, got {len(beta_t)} for {n}")
    zones = forbidden_zones_level1(thrusters) if forbidden_zones else [[] for _ in thrusters]
    options = [
        _thruster_pieces(t, b, n_sides, z, skegs) for t, b, z in zip(thrusters, beta_t, zones)
    ]
    sizes = [_size_rows(t, n_sides) for t in thrusters]
    a_size = _place(sizes, n)
    size_owner = np.concatenate([[i] * len(s) for i, s in enumerate(sizes)])
    t_ref = max(piece[1].max() for pieces in options for piece in pieces) or 1.0

    best, best_u = None, np.inf
    for pieces in product(*options):
        p = _problem(thrusters, load, pieces, a_size, size_owner, t_ref)
        u = _min_utilisation(p)
        if u is not None and u < best_u:
            best, best_u = p, u
    if best is None:
        return Allocation(np.full(n, np.nan), np.full(n, np.nan), np.inf)
    fx, fy = _least_total_thrust(best, best_u)
    return Allocation(fx, fy, best_u)
