# Hildebrand Glow (Bright App) Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/McDon22/hildebrand-glow-ha)](https://github.com/McDon22/hildebrand-glow-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Home Assistant custom integration for UK SMETS2 smart meters using the Hildebrand Glow / Bright app API.

## Features

- **Easy Setup**: Configure through the Home Assistant UI - no YAML required
- **12 Sensors**: Electricity and gas consumption, tariff rates, API costs, and calculated daily costs with standing charges
- **Tariff Configuration**: Set your own electricity and gas rates including standing charges
- **Energy Dashboard Compatible**: Works with Home Assistant's Energy Dashboard
- **Auto Updates**: Data refreshes every 5 minutes
- **Accurate Historical Usage**: Imports finalized Glowmarkt half-hourly data
  into integration-owned Home Assistant statistics without altering existing
  Recorder statistics

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
3. Home Assistant 2024.1.0 or newer

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/McDon22/hildebrand-glow-ha` as an **Integration**
4. Search for "Hildebrand Glow" and click **Download**
5. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub](https://github.com/McDon22/hildebrand-glow-ha/releases)
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
   - Gas rate (£/kWh)
   - Gas standing charge (£/day)

### Updating Tariff Rates

To update your tariff rates without reconfiguring:
1. Go to **Settings → Devices & Services**
2. Find the Hildebrand Glow integration
3. Click **Configure**
4. Update your rates

## Energy Dashboard Setup

To use with the Energy Dashboard:

1. Go to **Settings → Dashboards → Energy**
2. Add **Electricity grid consumption**: `sensor.smart_meter_electricity_consumption`
3. Under **Cost tracking**, select **Use an entity with current price**, then choose **Electricity Unit Rate**
4. Add **Gas consumption**: `sensor.smart_meter_gas_consumption`
5. Under **Cost tracking**, select **Use an entity with current price**, then choose **Gas Unit Rate**

Do not select **Electricity Cost (API)**, **Gas Cost (API)**, **Electricity Daily Cost**, **Gas Daily Cost**, **Total Daily Energy Cost**, or **Daily Standing Charges** as Energy Dashboard total-cost inputs. These entities reset each day and are not lifetime accumulated cost sensors.

### Historical statistics preview

Version 1.2.0 creates the following external statistics independently of the
existing sensor history:

- `Hildebrand Glow Electricity Consumption`
- `Hildebrand Glow Gas Consumption`

They are built from the real timestamped 30-minute Glowmarkt readings and are
intended to replace daily-resetting or synthetic consumption entities in the
Energy Dashboard after their values have been verified.

The first synchronization imports up to 90 days in seven-day request windows.
Subsequent synchronizations revisit the most recent seven days so delayed or
corrected Glowmarkt readings can be updated. Only complete UK-local days older
than the finalization delay are imported. Zero-use days are retained, while a
day with missing intervals stops the importer until Glowmarkt fills the gap.

This preview imports consumption only. Continue using the existing Energy
Dashboard configuration until the imported figures have been compared against
Bright. Cumulative cost statistics, dated tariff periods, and standing-charge
accounting will be added separately after consumption has been validated.

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
