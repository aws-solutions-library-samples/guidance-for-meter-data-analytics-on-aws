+----------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
| name                 | type       | mandatory  | description                                                                 | example                                       |
+======================+============+============+=============================================================================+===============================================+
| service_location_id  | String     | X          | ID of a physical location                                                   | abc_1                                         |
| meter_id             | String     | X          | The ID of a physical meter                                                  | 123456                                        |
| reading_value        | Double     | X          | the value of the reading                                                    | 0                                             |
| reading_type         | String     | X          | Classification of the reading, can be energy, voltage, current and similar  | Energy|NegativeEnergy|Current|Demand|Voltage  |
| unit                 | String     |            | unit of measurement (uom)                                                   | V|kwh|A|...                                   |
| reading_date_time    | Timestamp  | X          | the time the reading was taken                                              | yyyy-MM-dd HH:mm:ss.SSS                       |
| date_str             | String     | X          | internal value for partionining the data (not clear if still needed)        | yyyyMMdd                                      |
| obis_code            | String     |            | Obis Code of the register                                                   |                                               |
| phase                | String     |            | Phase on which the meter is connected                                       |                                               |
+----------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
