# NovaScotia-burn-restriction-tracker
(https://dongpuli.github.io)
## Features

- Daily official Nova Scotia BurnSafe restriction status
- County-level burn restriction display for all 18 Nova Scotia counties
- Interactive county map
- Official Fire Weather Forecast integration
- Station-level FWI data aggregation by county
- Fire Weather Index components:
  - FFMC
  - DMC
  - DC
  - ISI
  - BUI
  - FWI
- Historical BurnSafe restriction archive
- Experimental 7-day burn risk outlook
- Forecast performance tracking
- Automatic off-season archive mode outside March 15–October 15

## Official Fire Weather Data

Version 1.1.0 adds official Nova Scotia Fire Weather Forecast data.

The system collects station-level Fire Weather Index data from the Nova Scotia government Fire Weather Forecast XML feed and aggregates mapped weather stations to county-level fire weather records.

The collected variables include:

- Temperature
- Relative humidity
- Wind speed
- Wind direction
- 24-hour rainfall
- FFMC
- DMC
- DC
- ISI
- BUI
- FWI

County-level fire weather values are currently aggregated using a conservative max-risk approach. For relative humidity, the lowest station humidity is used.

This feature is experimental and the station-to-county mapping may be refined over time.

## Forecasting and Outlooks

This project now separates two concepts:

1. **Official Fire Weather Forecast**
   - Based on Nova Scotia government FWI station data.
   - Aggregated to county level.
   - Used as the main official fire-weather reference.

2. **Experimental 7-day Risk Outlook**
   - Based on weather forecast trends.
   - Not official.
   - Intended only as a planning-oriented preview.

Official BurnSafe restrictions remain the authoritative source for burning decisions.