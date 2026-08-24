# Hildebrand Glow (Bright App) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/rob5052/hildebrand-glow-ha)](https://github.com/rob5052/hildebrand-glow-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration for UK SMETS2 smart meters using the Hildebrand Glow / Bright app API.

## Features

- **Easy Setup**: Configure through the Home Assistant UI - no YAML required
- **12 Sensors**: Electricity and gas consumption, tariff rates, API costs, and calculated daily costs with standing charges
- **Dated Tariff Configuration**: Set unit rates, standing charges, and their effective dates
- **Energy Dashboard Compatible**: Works with Home Assistant's Energy Dashboard
- **Auto Updates**: Data refreshes every 5 minutes
- **Accurate Historical Usage**: Imports finalized Glowmarkt half-hourly data
  into integration-owned Home Assistant statistics without altering existing
  Recorder statistics
- **Current Dashboard Usage**: Refreshes provisional readings for today and the
  preceding two days every 30 minutes, then replaces them as Glowmarkt finalizes
  the data

## Sensors Created

| Sensor | Description |
|--------|-------------|
| Electricity Consumption | Daily electricity usage (kWh) |
| Gas Consumption | Daily gas usage (kWh) |
| Electricity Cost (API) | Daily-resetting cost from Glowmarkt API (GBP) |
| Gas Cost (API) | Daily-resetting cost from Glowmarkt API (GBP) |
| Electricity Daily Cost | Daily-resetting calculated cost: (usage × rate) + standing charge (GBP) |
| Gas Daily Cost | Daily-resetting calculated cost: (usage × rate) + standing charge (GBP) |
| Total Daily Energy Cost | Daily-resetting combined electricity + gas costs (GBP) |
| Daily Standing Charges | Daily-resetting total standing charges (GBP) |
| Electricity Unit Rate | Configured electricity unit rate (GBP/kWh) |
| Gas Unit Rate | Configured gas unit rate (GBP/kWh) |
| Electricity Standing Charge | Configured electricity standing charge (GBP/day) |
| Gas Standing Charge | Configured gas standing charge (GBP/day) |

## Prerequisites

1. A UK SMETS2 smart meter
2. A [Hildebrand Bright app](https://www.hildebrand.co.uk/bright/) account linked to your smart meter
3. Home Assistant 2025.12.0 or newer (tested on Home Assistant 2026.8.3)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/rob5052/hildebrand-glow-ha` as an **Integration**
4. Search for "Hildebrand Glow" and click **Download**
5. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/rob5052/hildebrand-glow-ha/releases)
2. Extract and copy the `custom_components/hildebrand_glow` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Hildebrand Glow"**
4. Enter your Bright app credentials (email and password)
5. Configure your tariff rates:
   - Electricity rate (£/kWh)
   - Electricity standing charge (£/day)
   - Electricity tariff effective date (YYYY-MM-DD)
   - Gas rate (£/kWh)
   - Gas standing charge (£/day)
   - Gas tariff effective date (YYYY-MM-DD)

### Updating Tariff Rates

To update your tariff rates without reconfiguring:
1. Go to **Settings → Devices & Services**
2. Find the Hildebrand Glow integration
3. Click **Configure**
4. Update your rates and enter the date on which each tariff became effective

When a later tariff replaces an existing dated tariff, the integration retains
the previous period for historical cost calculations.

## Energy Dashboard Setup

To use with the Energy Dashboard:

1. Go to **Settings → Dashboards → Energy**
2. Add **Electricity grid consumption**: `Hildebrand Glow Electricity Consumption`
3. Under **Cost tracking**, select the total-cost option and choose **Hildebrand Glow Electricity Cost**
4. Add **Gas consumption**: `Hildebrand Glow Gas Consumption`
5. Under **Cost tracking**, select the total-cost option and choose **Hildebrand Glow Gas Cost**

The cumulative cost statistics use the dated tariff applicable to each UK-local
day and include exactly one standing charge per day. They do not add synthetic
energy consumption.

Do not select **Electricity Cost (API)**, **Gas Cost (API)**, **Electricity Daily Cost**, **Gas Daily Cost**, **Total Daily Energy Cost**, or **Daily Standing Charges** as Energy Dashboard total-cost inputs. These entities reset each day and are not lifetime accumulated cost sensors.

### Historical energy statistics

Version 1.4.0 and later create the following external statistics independently of the
existing sensor history:

- `Hildebrand Glow Electricity Consumption`
- `Hildebrand Glow Gas Consumption`
- `Hildebrand Glow Electricity Cost`
- `Hildebrand Glow Gas Cost`

They are built from the real timestamped 30-minute Glowmarkt readings and are
intended to replace daily-resetting or synthetic consumption entities in the
Energy Dashboard after their values have been verified.

The first synchronization imports up to 90 days in seven-day request windows.
Subsequent synchronizations revisit the most recent seven days so delayed or
corrected Glowmarkt readings can be updated. Only complete UK-local days older
than the finalization delay are imported. Zero-use days are retained, while a
day with missing intervals stops the importer until Glowmarkt fills the gap.

Today and the preceding two UK-local days are also refreshed every 30 minutes
from the half-hour readings currently available in Glowmarkt. These recent
figures are provisional and may initially be low or move slightly as delayed
readings arrive. They are overwritten by the finalized import automatically;
no predicted or synthetic consumption is added.

Cost statistics are only created for dates covered by a configured tariff
effective date. Unit cost is calculated from the real hourly consumption and
the applicable rate; the daily standing charge is added to the first hour of
each complete UK-local day.

## Data Availability

**Important**: Smart meter data from the Glowmarkt API typically has a 24-48 hour delay. The sensors show the most recent available data, which may not be real-time.

For near real-time data, consider using a Glow CAD/IHD device with local MQTT.

## Troubleshooting

### No resources found
- Ensure your Bright app account is properly linked to your smart meter
- Check that you can see data in the Bright mobile app

### Invalid credentials
- Verify your email and password work in the Bright mobile app
- Passwords are case-sensitive

### Sensors showing unavailable
- Check your internet connection
- The Glowmarkt API may be temporarily unavailable
- Check Home Assistant logs for specific error messages

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Hildebrand Technology](https://www.hildebrand.co.uk/) for the Glowmarkt API
- The Home Assistant community
- [McDon22/hildebrand-glow-ha](https://github.com/McDon22/hildebrand-glow-ha)
  as the upstream project on which this fork is based

## Development attribution

The tariff entities, Home Assistant statistics integration, historical and
provisional consumption imports, dated cumulative cost calculations, standing
charge handling, tests, debugging, and documentation introduced in version
1.4.0 were designed and implemented by OpenAI ChatGPT/Codex in collaboration
with Rob Oliver. The implementation was tested against Rob's Home Assistant and
Hildebrand Bright data before release.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
