import numpy as np

from dp_capability.standard import RHO_AIR, fold_direction

AIR_DENSITY = 1.23  # kg/m^3, value used in Blendermann (1994)

# Blendermann (1994), Table 1: reference wind load parameters per vessel type.
#   cd_t         - coefficient of lateral resistance, at eps = 90 deg (beam wind)
#   cd_lAF_bow   - coefficient of longitudinal resistance w.r.t. frontal area, eps = 0 deg (bow wind)
#   cd_lAF_stern - coefficient of longitudinal resistance w.r.t. frontal area, eps = 180 deg (stern wind)
#   delta        - cross-force parameter
#   kappa        - rolling-moment factor
# Rows given as two values in the paper (e.g. loaded/in ballast) are split into
# two separate vessel types below. "drilling_vessel" is given as a range in the
# paper (0.70-1.00 / 0.75-1.10); the midpoint of each range is used here.
BLENDERMANN_COEFFICIENTS = {
    "car_carrier": {"cd_t": 0.95, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.60, "delta": 0.80, "kappa": 1.2},
    "cargo_vessel_loaded": {"cd_t": 0.85, "cd_lAF_bow": 0.65, "cd_lAF_stern": 0.55, "delta": 0.40, "kappa": 1.7},
    "cargo_vessel_container_on_deck": {"cd_t": 0.85, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.50, "delta": 0.40, "kappa": 1.4},
    "container_ship_loaded": {"cd_t": 0.90, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.55, "delta": 0.40, "kappa": 1.4},
    "destroyer": {"cd_t": 0.85, "cd_lAF_bow": 0.60, "cd_lAF_stern": 0.65, "delta": 0.65, "kappa": 1.1},
    "diving_support_vessel": {"cd_t": 0.90, "cd_lAF_bow": 0.60, "cd_lAF_stern": 0.80, "delta": 0.55, "kappa": 1.7},
    "drilling_vessel": {"cd_t": 1.00, "cd_lAF_bow": 0.85, "cd_lAF_stern": 0.925, "delta": 0.10, "kappa": 1.7},
    "ferry": {"cd_t": 0.90, "cd_lAF_bow": 0.45, "cd_lAF_stern": 0.50, "delta": 0.80, "kappa": 1.1},
    "fishing_vessel": {"cd_t": 0.95, "cd_lAF_bow": 0.70, "cd_lAF_stern": 0.70, "delta": 0.40, "kappa": 1.1},
    "lng_tanker": {"cd_t": 0.70, "cd_lAF_bow": 0.60, "cd_lAF_stern": 0.65, "delta": 0.50, "kappa": 1.1},
    "offshore_supply_vessel": {"cd_t": 0.90, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.80, "delta": 0.55, "kappa": 1.2},
    "passenger_liner": {"cd_t": 0.90, "cd_lAF_bow": 0.40, "cd_lAF_stern": 0.40, "delta": 0.80, "kappa": 1.2},
    "research_vessel": {"cd_t": 0.85, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.65, "delta": 0.60, "kappa": 1.4},
    "speed_boat": {"cd_t": 0.90, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.60, "delta": 0.60, "kappa": 1.1},
    "tanker_loaded": {"cd_t": 0.70, "cd_lAF_bow": 0.90, "cd_lAF_stern": 0.55, "delta": 0.40, "kappa": 3.1},
    "tanker_ballast": {"cd_t": 0.70, "cd_lAF_bow": 0.75, "cd_lAF_stern": 0.55, "delta": 0.40, "kappa": 2.2},
    "tender": {"cd_t": 0.85, "cd_lAF_bow": 0.55, "cd_lAF_stern": 0.55, "delta": 0.65, "kappa": 1.1},
}


def _blendermann_coefficients(vessel_type, loa, area_lateral, area_frontal, s_L, s_H, relative_angle_deg):
    """
    Estimate the non-dimensional wind load coefficients CX, CY, CN, CK using
    Blendermann's (1994) semi-empirical loading functions (Eqs. 13-16).

    relative_angle_deg is the angle of attack of the apparent wind: 0 deg = wind
    from the bow, 180 deg = wind from the stern, 0-360 deg overall. The vessel
    is assumed symmetric about its centreline, so angles above 180 deg (port
    side) reuse the starboard-side (0-180 deg) magnitude with CY, CN and CK
    sign-flipped.

    Internal fallback used by blendermann_wind_coefficients() when the vessel
    has no measured wind_coefficients of its own.
    """
    coeffs = BLENDERMANN_COEFFICIENTS[vessel_type]
    cd_t = coeffs["cd_t"]
    delta = coeffs["delta"]
    kappa = coeffs["kappa"]

    angle = np.asarray(relative_angle_deg, dtype=float)
    is_port_side = angle > 180
    folded_angle = np.where(is_port_side, 360 - angle, angle)
    eps = np.deg2rad(folded_angle)

    # CD_lAF differs between bow wind (eps=0) and stern wind (eps=180) because
    # ships are not fore-aft symmetric; pick the value for whichever end the
    # (folded) angle is closest to.
    is_bow_side = folded_angle <= 90
    cd_lAF = np.where(is_bow_side, coeffs["cd_lAF_bow"], coeffs["cd_lAF_stern"])
    # Table 1 gives CD_lAF on a frontal-area basis; Eqs. 13-14 need it on the
    # same lateral-area basis as cd_t (see the note below Eq. 16 in the paper).
    cd_l = cd_lAF * area_frontal / area_lateral

    denom = 1 - (delta / 2) * (1 - cd_l / cd_t) * np.sin(2 * eps) ** 2

    cx_af = -cd_lAF * np.cos(eps) / denom
    cy = cd_t * np.sin(eps) / denom
    cy = np.where(is_port_side, -cy, cy)

    h_m = area_lateral / loa
    # s_L: longitudinal distance of the lateral-plane centroid from midships
    # [m], positive toward the bow. It shifts the yawing-moment lever arm,
    # so an asymmetric side profile (e.g. more area forward) yields a
    # non-zero yawing moment even in beam wind.
    cn = (s_L / loa - 0.18 * (eps - np.pi / 2)) * cy
    # s_H: height of the lateral-plane centroid above the waterline [m]. It
    # sets the rolling-moment lever arm together with kappa - the higher the
    # centroid sits (more superstructure/higher up), the larger the rolling
    # moment for a given side force.
    ck = kappa * (s_H / h_m) * cy

    return cx_af, cy, cn, ck


def blendermann_wind_coefficients(vessel_type, loa, area_lateral, area_frontal, s_L, s_H, relative_angle_deg, air_density=AIR_DENSITY):
    """
    Convert Blendermann's non-dimensional CX/CY/CN/CK into coefficients that
    give force/moment directly when multiplied by wind_speed**2, i.e. area and
    dynamic pressure (q = 0.5 * air_density * wind_speed**2) are folded into
    the coefficient itself - the same form wind tunnel test coefficients are
    usually reported in.

    Returns cx, cy, cn, ck such that, for a given apparent wind_speed [m/s]:
        X = cx * wind_speed**2   [N]
        Y = cy * wind_speed**2   [N]
        N = cn * wind_speed**2   [Nm]
        K = ck * wind_speed**2   [Nm]

    Parameters
    ----------
    vessel_type : str
        Key into BLENDERMANN_COEFFICIENTS (e.g. "diving_support_vessel"),
        selecting which row of Blendermann's Table 1 to use.
    loa : float
        Length overall of the vessel, Loa [m].
    area_lateral : float
        Lateral-plane (side) projected area above the waterline, A_L [m^2].
    area_frontal : float
        Frontal projected area above the waterline, A_F [m^2].
    s_L : float
        Longitudinal distance of the lateral-plane centroid from midships
        (the main section), positive toward the bow [m].
    s_H : float
        Height of the lateral-plane centroid above the waterline [m].
    relative_angle_deg : float or array-like
        Angle of attack of the apparent wind, epsilon: 0 deg = wind from the
        bow, 180 deg = wind from the stern, 0-360 deg overall (the vessel is
        assumed symmetric port/starboard, so angles above 180 deg are folded
        back and sign-flipped internally). Can be a single value or a numpy
        array, e.g. to evaluate all headings of an envelope plot at once.
    air_density : float, optional
        Air density, rho [kg/m^3]. Defaults to AIR_DENSITY = 1.23 kg/m^3, the
        value used in Blendermann (1994).
    """
    cx_af, cy_nd, cn_nd, ck_nd = _blendermann_coefficients(
        vessel_type, loa, area_lateral, area_frontal, s_L, s_H, relative_angle_deg
    )

    q_per_v2 = 0.5 * air_density  # dynamic pressure per unit wind_speed**2
    h_m = area_lateral / loa

    cx = cx_af * q_per_v2 * area_frontal
    cy = cy_nd * q_per_v2 * area_lateral
    cn = cn_nd * q_per_v2 * area_lateral * loa
    ck = ck_nd * q_per_v2 * area_lateral * h_m

    return cx, cy, cn, ck


def wind_loads_level1(hull, wind_speed, direction_deg):
    """
    Wind forces and yaw moment for DP capability level 1, DNV-ST-0111 [3.5].

    Uses the standard's body frame and sign convention (x forward, y to port,
    yaw positive counter-clockwise, see dp_capability/standard.py). Note that
    this differs from Blendermann's frame used above, where y points to
    starboard.

    Parameters
    ----------
    hull : dp_capability.vessel.Hull
        Vessel hull data; uses af_wind, al_wind, xl_air and lpp.
    wind_speed : float or array-like
        Mean wind speed 10 m above sea level [m/s].
    direction_deg : float or array-like
        Direction the wind is coming from, clockwise: 0 deg = head-on,
        90 deg = from starboard. Values outside 0-360 deg are wrapped. Can be
        a numpy array, e.g. to evaluate all headings of an envelope at once.

    Returns
    -------
    fx, fy, mz
        Surge force [N], sway force [N] and yaw moment [Nm].
    """
    direction = np.deg2rad(np.mod(direction_deg, 360.0))
    q = 0.5 * RHO_AIR * np.asarray(wind_speed, dtype=float) ** 2

    fx = q * hull.af_wind * (-0.7 * np.cos(direction))
    fy = q * hull.al_wind * (0.9 * np.sin(direction))
    # The centre of pressure moves from 0.3*Lpp forward of xl_air in head wind
    # to 0.3*Lpp aft of it in stern wind, the same on both sides of the vessel.
    mz = fy * (hull.xl_air + 0.3 * (1 - 2 * fold_direction(direction) / np.pi) * hull.lpp)

    return fx, fy, mz




