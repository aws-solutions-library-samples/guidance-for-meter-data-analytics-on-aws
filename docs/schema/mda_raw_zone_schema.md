+--------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
| name               | type       | mandatory  | description                                                                 | example                                       |
+====================+============+============+=============================================================================+===============================================+
| meter_id           | String     | X          | The ID of a physical meter                                                  | 123456                                        |
| reading_value      | Double     | X          | The value of the reading                                                    | 0                                             |
| reading_type       | String     | X          | Classification of the reading, can be energy, voltage, current and similar  | Energy|NegativeEnergy|Current|Demand|Voltage  |
| unit               | String     |            | Unit of measurement (uom)                                                   | V|kwh|A|...                                   |
| reading_date_time  | Timestamp  | X          | The time the reading was taken                                              | yyyy-MM-dd HH:mm:ss.SSS                       |
| obis_code          | String     |            | Obis Code of the register                                                   |                                               |
| phase              | String     |            | Phase on which the meter is connected                                       |                                               |
| reading_source     | String     |            | The source of the reading if record came from HES or batch readings         | HES | B                                       |
|                    |            |            |                                                                             |                                               |
|                    |            |            |                                                                             |                                               |
+--------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
