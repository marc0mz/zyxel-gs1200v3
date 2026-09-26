# GS1200-8HPv3 web UI coverage map

Scope verified by reading the switch's authenticated web pages on firmware V1.00(ACPV.2)C0. The inspection read pages and form schemas only; it did not submit configuration writes.

| Web UI area | What the switch exposes | Integration state |
|---|---|---|
| System (`zSystem.html`) | Model/name, firmware, loop status, uptime, MAC/IP/subnet/gateway, per-port link/PVID/VLAN and TX/RX/error counters; clear counters | Baseline only exposes PoE power readings. Other system and port diagnostics are omitted. |
| Port (`zPort.html`) | Ethernet admin state, speed/duplex, flow control, PoE state; broadcast storm control; loop prevention; advanced isolation/uplink and ingress/egress bandwidth | Ethernet admin state controls on ports 1–8 and PoE controls on ports 1–4 are implemented. Ethernet writes were tested offline but not toggled on the live switch. Speed/duplex, flow control, storm control, loop prevention, and advanced settings remain out of scope for this baseline. |
| VLAN (`zVLAN_1Q_List.html`) | 802.1Q VLAN create/edit/delete, tagged/untagged membership, PVID | Not yet implemented. |
| Link Aggregation (`zLink_Aggregation.html`) | Three fixed port groups, static/LACP mode, MAC hashing algorithm | Not yet implemented. |
| Mirroring (`zMirroring.html`) | Enable, ingress/egress/both direction, monitor and mirrored ports | Not yet implemented. |
| QoS (`zPort_Based_Qos.html`, `zQos1p.html`) | Port-based or 802.1p mode and queue weights | Not yet implemented. |
| IGMP Snooping (`zIGMP_Snooping.html`) | Snooping, unknown-multicast handling, static router port | Not yet implemented. |
| Management (`zManagement.html`) | Network addressing/DHCP, HTTP/HTTPS and timeout, management VID, EEE, LED ECO, backup/restore, SNMP, password, firmware update, reboot/reset | Not yet implemented. Network-disruptive or credential/firmware operations will need explicit safeguards and will not run automatically. |

The switch presents these areas through ordinary web forms. Every added write must preserve unrelated switch settings and read its result back before Home Assistant reports success. Ethernet disable and PoE disable are different operations; only PoE on port 4 has been live toggled in the prior candidate test.
