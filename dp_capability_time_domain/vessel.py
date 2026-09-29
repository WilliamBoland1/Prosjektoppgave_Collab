"""
Data containers for the vessel input to the DP capability calculations.

All positions are in the DNV-ST-0111 [2.8.2] body frame: x forward, y to
port, z up, origin at Lpp/2 on the centreline at the keel (see
dp_capability/standard.py). The actual values for a vessel live in config.py.
"""
from dataclasses import dataclass
from enum import StrEnum


class VesselType(StrEnum):
    """Vessel types in Blendermann (1994) Table 1, one per row of
    BLENDERMANN_COEFFICIENTS in models/windloads.py."""

    CAR_CARRIER = "car_carrier"
    CARGO_VESSEL_LOADED = "cargo_vessel_loaded"
    CARGO_VESSEL_CONTAINER_ON_DECK = "cargo_vessel_container_on_deck"
    CONTAINER_SHIP_LOADED = "container_ship_loaded"
    DESTROYER = "destroyer"
    DIVING_SUPPORT_VESSEL = "diving_support_vessel"
    DRILLING_VESSEL = "drilling_vessel"
    FERRY = "ferry"
    FISHING_VESSEL = "fishing_vessel"
    LNG_TANKER = "lng_tanker"
    OFFSHORE_SUPPLY_VESSEL = "offshore_supply_vessel"
    PASSENGER_LINER = "passenger_liner"
    RESEARCH_VESSEL = "research_vessel"
    SPEED_BOAT = "speed_boat"
    TANKER_LOADED = "tanker_loaded"
    TANKER_BALLAST = "tanker_ballast"
    TENDER = "tender"


@dataclass(frozen=True)
class Hull:
    """Hull data as listed in DNV-ST-0111 Table A-2. SI units."""
    vessel_type: VesselType  # row of Blendermann Table 1, e.g. VesselType.DIVING_SUPPORT_VESSEL
    loa: float  # length over all [m]
    lpp: float  # length between perpendiculars [m]
    draft: float  # summer load line draft [m]
    breadth: float  # maximum breadth at the waterline, B [m]
    los: float  # distance between the foremost and aftmost points under water, Los [m]
    x_los: float  # longitudinal position of Los/2 [m]
    bow_angle: float  # bow angle, see [3.7] and Figure 3-2 [rad]
    aw_laft: float  # waterplane area behind Lpp/2, A_WLaft [m^2]
    af_wind: float  # frontal projected area above water, A_F,wind [m^2]
    al_wind: float  # longitudinal projected area above water, A_L,wind [m^2]
    xl_air: float  # longitudinal position of the area centre of al_wind [m]
    s_h: float  # height of the lateral-plane centroid above the waterline, s_H [m]
    af_current: float  # frontal projected area below water, A_F,current [m^2]
    al_current: float  # longitudinal projected area below water, A_L,current [m^2]
    xl_current: float  # longitudinal position of the area centre of al_current [m]
    skegs: tuple[tuple[float, float], ...] = ()  # (x, y) of the aftmost point of each skeg/gondola [m]

    def __post_init__(self):
        # Type hints are not checked at runtime, so a plain string would
        # otherwise only fail deep inside the wind load calculation.
        if not isinstance(self.vessel_type, VesselType):
            raise TypeError(f"vessel_type must be a VesselType, got {self.vessel_type!r}")


@dataclass(frozen=True)
class Thruster:
    """
    Actuator data as listed in DNV-ST-0111 Table A-3. SI units, except the
    power, which is in kW like the standard's nominal thrust formula [3.9.2].
    """

    name: str  # identification, e.g. "BT1"
    kind: str  # "azimuth", "pod", "shaft_line", "tunnel", "cycloidal" or "water_jet"
    # Propeller diameter D [m]. [3.9.2] defines it for special actuators: the
    # blade tip circle for permanent magnet tunnel thrusters, the largest
    # propeller for contra-rotating units and pods with a propeller at each
    # end, and sqrt(blade length * blade pivot circle diameter) for cycloidals.
    diameter: float
    # P_B: MCR brake power available in DP mode/bollard pull, with power and
    # torque limits taken into account [kW], see [3.9.2] guidance note 3.
    power_kw: float
    # Position [m] as defined in [3.8.3], e.g. the volume centre of a tunnel
    # or the intersection of propeller shaft and azimuthing axis.
    x: float
    y: float
    z: float
    pitch: str = "FPP"  # fixed ("FPP") or controllable ("CPP") pitch propeller
    ducted: bool = False
    permanent_magnet: bool = False
    contra_rotating: bool = False
    tunnel_inlet: str | None = None  # "broken", "rounded" or "other", Table 3-2; tunnels only
