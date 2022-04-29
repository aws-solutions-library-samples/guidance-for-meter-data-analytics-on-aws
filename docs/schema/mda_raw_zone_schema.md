+--------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
| name               | type       | mandatory  | description                                                                 | example                                       |
+====================+============+============+=============================================================================+===============================================+
| meter_id           | String     | X          | The ID of a physical meter                                                  | 123456                                        |
| reading_value      | Double     | X          | the value of the reading                                                    | 0                                             |
| reading_type       | String     | X          | Classification of the reading, can be energy, voltage, current and similar  | Energy|NegativeEnergy|Current|Demand|Voltage  |
| unit               | String     |            | unit of measurement (uom)                                                    | V|kwh|A|...                                   |
| reading_date_time  | Timestamp  | X          | the time the reading was taken                                              | yyyy-MM-dd HH:mm:ss.SSS                       |
| obis_code          | String     |            | Obis Code of the register                                                   |                                               |
| phase              | String     |            | Phase on which the meter is connected                                       |                                               |
|                    |            |            |                                                                             |                                               |
|                    |            |            |                                                                             |                                               |
+--------------------+------------+------------+-----------------------------------------------------------------------------+-----------------------------------------------+
