# API Documentation

## Consumption API

Returns the consumption for a single meter in a given time window.

Request:
```bash
https://<API_ENDPOINT>/consumption/{meter_id}?reading_date_from={yyyyMMdd}&reading_date_to={yyyyMMdd}
```
Result:
```json
[
    {
        "meter_id": "81cac15d-01d5-3d51-8bde-0f7a383585ae",
        "reading_value": 11.787,
        "reading_date_time": "2022-09-08T19:00:00",
        "reading_type": "kw"
    },
    {
        "meter_id": "81cac15d-01d5-3d51-8bde-0f7a383585ae",
        "reading_value": 6.95,
        "reading_date_time": "2022-09-08T19:15:00",
        "reading_type": "kw"
    }
]
```

## Voltage API

Returns the voltage data for a single meter in a given time window.

Request:
```bash
https://<API_ENDPOINT>/voltage/{meter_id}?reading_date_from={yyyyMMdd}&reading_date_to={yyyyMMdd}
```
Result:
```json
[
      {
        "meter_id": "81cac15d-01d5-3d51-8bde-0f7a383585ae",
        "reading_value": 0.239,
        "reading_date_time": "2022-09-08T23:00:00",
        "reading_type": "vltg"
      },
      {
        "meter_id": "81cac15d-01d5-3d51-8bde-0f7a383585ae",
        "reading_value": 0.205,
        "reading_date_time": "2022-09-08T23:15:00",
        "reading_type": "vltg"
      }
]
```

## Forecast API

Returns the consumption forecast for a given meter for the next three days (hourly)

Request:
```bash
https://<API_ENDPOINT>/forecast/{meter_id}?forecast_start=YYYYMMddHHmmss
```
Result:
```json
[
      {
        "date_time": "2022-07-15 15:00:00",
        "consumption": 22.9699630737
      },
      {
        "date_time": "2022-07-15 16:00:00",
        "consumption": 22.5186061859
      }
]
```

## Anomaly API 

Returns the anomalies for a given meter and year.

Request:
```bash
https://<API_ENDPOINT>/anomaly/{meter_id}?year={yyyy}
```
Result:
```json
[
      {
        "anomaly_date": "2023-01-11",
        "meter_id": "81cac15d-01d5-3d51-8bde-0f7a383585ae",
        "consumption": 510.302,
        "anomaly_importance": 0.22383863
      }
]
```