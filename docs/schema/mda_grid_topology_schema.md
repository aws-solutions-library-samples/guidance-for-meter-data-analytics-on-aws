+----------------------+------------+------------+--------------------------------------------------------------------------+----------------------+
| name                 | type       | mandatory  | description                                                              | example              |
+======================+============+============+==========================================================================+======================+
| control_node_id      | Numeric    | X          |                                                                          |                      |
| control_zone_id      | Numeric    | X          |                                                                          |                      |
| transformer_id       | Numeric    | X          |                                                                          |                      |
| service_location_id  | String     | X          | The service location ID describes the physical location id of the meter  | abc_1                |
| start_date_time      | Timestamp  | X          | Date time from which on the topology information should be used (UTC)    | 2022/01/01 00:00:00  |
|                      |            |            |                                                                          |                      |
+----------------------+------------+------------+--------------------------------------------------------------------------+----------------------+

Control Node Information: Control Node is like a substation

Control Zone Information: Control Zone is the voltage regulation zone that a meter/transformer belongs to. It is the immediately upline (or first upline) voltage regulation device for the meter under consideration.

Transformer Information: Transformer ID. This could be an OH or UG transformer.


Example
control_node_id | control_zone_id   | transformer_id | service_location_id | start_date_time
SpaceNeedle     | LTC_SpaceNeedle_1 | Tx1            | S01                 | 2022/01/01 00:00:00 
SpaceNeedle     | LTC_SpaceNeedle_1 | Tx1            | S02                 | 2022/01/01 00:00:00
SpaceNeedle     | LTC_SpaceNeedle_1 | Tx2            | S03                 | 2022/01/01 00:00:00
SpaceNeedle     | Reg_SpaceNeedle_1 | Tx3            | S04                 | 2022/01/01 00:00:00
SpaceNeedle     | Reg_SpaceNeedle_1 | Tx3            | S05                 | 2022/01/01 00:00:00