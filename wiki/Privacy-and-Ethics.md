# Privacy and Ethics

## What is stored

| Data | Why | Where |
|---|---|---|
| Random pseudonymous visitor ID | Count stamps per visitor | SQLite, cookie/token on the phone |
| Station + timestamp of each check-in | Stamp and reward rules | SQLite |
| Voucher code | Reward | SQLite |
| Environmental readings | Walk rating, dashboards | InfluxDB |
| Pi health data | Maintenance | InfluxDB |

## What is never stored

- Name, email or phone number
- GPS location or continuous tracking
- Camera images
- Audio. The sound sensor stores only a level.
- Advertising or behavioural profiles

A pseudonymous ID combined with station and time can still count as personal data. **Pseudonymous is not anonymous.**

What we do about it:

- Store only what the rules need.
- Hide small groups in public statistics.
- Define a retention period: **TBD** ([#34](https://github.com/julianzangl/NatureCheckpoint/issues/34)).

## Safety and inclusion

- The walk rating and the LED give **general information**. They are not medical advice, and they do not guarantee that air or UV levels are safe.
- Rewards never depend on speed or physical performance.
- Access to green spaces never depends on owning a smartphone. Using the system is optional.
- Severe weather or a closure overrides any prompt to go outside.

## Security notes

- **NFC tags:** static NFC tags in the MVP can be copied. This is documented as a known limitation. Production would use NTAG 424 DNA tags, which authenticate every read.
- **Secrets:** API keys, tokens and passwords live only in `.env` and are never committed.

## Environmental footprint

- The MVP uses mains power and runs indoors or at a supervised demo.
- A real deployment should use:
  - repairable modules
  - low transmit frequency
  - minimal LED use
  - proper e-waste handling
