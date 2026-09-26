# Zyxel GS1200v3 PoE

Home Assistant custom integration for the Zyxel GS1200-8HPv3 managed PoE switch.

> **Alpha 0.1.26:** this is the simple baseline with separate PoE and Ethernet controls. It does not include the additional diagnostic sensors or experimental controls from later development builds.

## Features

- Toggle PoE power on ports 1–4.
- Enable or disable Ethernet administratively on ports 1–8. This disconnects devices attached to a disabled port.
- Read PoE power consumption on ports 1–4.
- Connect to the switch locally over HTTP or HTTPS.

PoE and Ethernet are separate controls. Turning off PoE does not disable the Ethernet link.

VLANs, link aggregation, mirroring, QoS, IGMP snooping, port statistics, speed/duplex, storm control, loop prevention, and most management settings are not implemented in this release.

## Installation

### HACS custom repository

Add `https://github.com/marc0mz/zyxel-gs1200v3` in **HACS → Integrations → ⋮ → Custom repositories**, choose **Integration**, download the latest release, and restart Home Assistant.

### Manual

Copy `custom_components/zyxel_gs1200v3` into Home Assistant's `config/custom_components/` directory, restart Home Assistant, then add **Zyxel GS1200v3 PoE** from **Settings → Devices & services**.

Enter the switch address and administrator password. The host field starts blank so each user supplies their own switch address. Home Assistant stores the password in its config entry; the integration does not write it to its logs.

## Supported hardware

Developed for Zyxel GS1200-8HPv3, firmware V1.00(ACPV.2)C0. Other hardware revisions have not been verified.

## Safety

Disabling Ethernet disconnects every device using that port. Verify the port before changing its Ethernet switch or creating automations.

## Contributing

Issues and pull requests are welcome. Please do not include switch passwords, Home Assistant tokens, or other credentials in issues, logs, or screenshots. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.

This project is licensed under the MIT License; see [`LICENSE`](LICENSE).

## Development

The scope and validation record are in [`docs/SWITCH_WEB_UI.md`](docs/SWITCH_WEB_UI.md) and [`TEST_LOG.md`](TEST_LOG.md). The blue `Z` tile is an original project monogram, not Zyxel's official logo.
