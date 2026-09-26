# Validation: alpha baseline 0.1.25

Target: Zyxel GS1200-8HPv3, firmware V1.00(ACPV.2)C0.

## Verified on the switch

- Authenticated login and readback of PoE state and power for ports 1–4.
- PoE disable and re-enable on port 4, with switch readback confirming each state.
- The Home Assistant integration loaded successfully in the user's installation before the diagnostic entities were added.

## Offline checks

- Ethernet enable/disable request payload for port 4 preserves the other Ethernet bits, PoE bitmap, speed, and flow-control settings.
- No live Ethernet state was changed; the payload test is not a live switch test.

## Not included or not verified

- The 0.1.25 Ethernet write control has not been toggled on the live switch.
- Full Home Assistant startup could not be run on the development PC because it runs Windows without an available WSL or Docker runtime. The user tested the copied integration in a real Home Assistant instance.
- HACS Action and Hassfest workflows have not yet run on GitHub.
- No VLAN, LAG, mirroring, QoS, IGMP, or advanced management features are in this baseline.
