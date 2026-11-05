# NatureCheckpoint Wiki

NatureCheckpoint is a network of small IoT checkpoints in green spaces in Bilbao. Visitors tap their phone at a checkpoint to collect a digital stamp, and monthly stamps unlock a (simulated) reward. Each checkpoint also measures local environmental conditions, rates them as *good / fair / poor for a walk* and shows the rating on an LED.

The MVP demonstrates **one demo park with two checkpoints**.

> **Status:** Sprint 1 (3 Nov → 17 Nov 2026). Pages describe the planned design. Sections marked **TBD** are completed as the linked issues are done.

## Pages

| Page | Content |
|---|---|
| [Architecture](Architecture) | Components, data flows, communication, data model |
| [Hardware and Wiring](Hardware-and-Wiring) | Sensors, actuators, NFC, Grove ports and connections |
| [Sensor Node](Sensor-Node) | Code on the Raspberry Pi: sampling, walk rating, LED, services |
| [Backend and API](Backend-and-API) | REST endpoints, MQTT topics, check-in and reward rules |
| [Data and Dashboards](Data-and-Dashboards) | InfluxDB, Grafana, analytics, map, external data |
| [Setup Guide](Setup-Guide) | How to reproduce the system from scratch |
| [Third-Party Tools](Third-Party-Tools) | Libraries, services and open datasets used |
| [Privacy and Ethics](Privacy-and-Ethics) | Data stored, data not stored, safety notes |
| [Project Management](Project-Management) | Scrum process, sprints, board, Git workflow |

## Quick links

- [Repository README](https://github.com/julianzangl/NatureCheckpoint#readme)
- [Project board](https://github.com/users/julianzangl/projects/2)
- [IoT Challenge proposal (PDF)](https://github.com/julianzangl/NatureCheckpoint/blob/main/docs/IoT_Challenge_Chahil_Sylkaj_Zangl.pdf)

## Team

Hischam Chahil ([@MA-Hischam](https://github.com/MA-Hischam)) · Florian Sylkaj ([@fsylkaj](https://github.com/fsylkaj)) · Julian Zangl ([@julianzangl](https://github.com/julianzangl))
