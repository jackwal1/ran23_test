samsung_live_table_classifier = """
# Prompt for Table Selection Based on Chain of Thought Reasoning

To determine the most suitable database table for your query, follow this step-by-step Chain of Thought (CoT) reasoning process. Below are the available tables, each with a description, all columns listed in Markdown format, and sample rows to clarify their content and purpose:

## 1. `dl_silver_ran_samsung_piiprod.usm_cm_ret_state_1d` (RET State Table)  
- **Purpose**: Stores daily Antenna Remote Electrical Tilt (RET) configurations for Samsung 5G RAN.  
- **Content**: Includes radio unit details, antenna configurations, software inventory, and metadata.  
- **Columns**:  

Here's the markdown table with all columns from the provided table structure:

| Column Name                                     | Description                                                                 |
|-------------------------------------------------|-----------------------------------------------------------------------------|
| zip_time_stamp                                  | Time of data archiving (e.g., `2025-06-23 12:00:19.000000 UTC`)             |
| xml_time_stamp                                  | Time of XML configuration generation (e.g., `2025-06-21 03:56:22.000000 UTC`) |
| ne-id                                           | Network Element identifier                                                  |
| ne-type                                         | Network Element type                                                       |
| du-reparenting                                  | DU reparenting status                                                      |
| system-type                                     | System type                                                                |
| user-label                                      | User-defined label                                                         |
| o-ran-radio-unit.o-ran-radio-unit-info.object   | O-RAN Radio Unit object path                                               |
| o-ran-radio-unit.o-ran-radio-unit-info.o-ran-ru-id | Radio Unit identifier (e.g., `415007026`)                                  |
| o-ran-radio-unit.o-ran-radio-unit-info.msr-operational-mode | MSR operational mode                                                     |
| o-ran-radio-unit.o-ran-radio-unit-info.operational-mode | Operational state of the RU (e.g., `enabled`)                            |
| o-ran-radio-unit.o-ran-radio-unit-info.serial-number | Serial number of the radio unit (e.g., `SN123456789`)                     |
| o-ran-radio-unit.o-ran-radio-unit-info.sub-type | Radio Unit subtype                                                        |
| o-ran-radio-unit.o-ran-radio-unit-info.unit-type | Type of radio unit (e.g., `RRU`)                                           |
| o-ran-radio-unit.o-ran-radio-unit-info.user-label | User-defined label for radio unit                                          |
| antenna-line-device.antenna-line-device-info.object | Antenna Line Device object path                                          |
| antenna-line-device.antenna-line-device-info.antenna-line-device-id | Antenna Line Device identifier                                           |
| antenna-line-device.antenna-line-device-info.antenna-serial-number | Antenna serial number                                                   |
| antenna-line-device.antenna-line-device-info.user-label | User-defined label for antenna line device                                |
| antenna-line-device.antenna-line-device-info.vendor-code | Vendor code for antenna line device                                      |
| software-inventory.software-slot.object         | Software slot object path                                                  |
| software-inventory.software-slot.name           | Software slot name                                                         |
| software-inventory.software-slot.access         | Software access level                                                      |
| software-inventory.software-slot.active         | Software slot active status                                                |
| software-inventory.software-slot.build-id       | Software build identifier                                                  |
| software-inventory.software-slot.build-name     | Software build name                                                        |
| software-inventory.software-slot.build-version  | Software version of the radio unit (e.g., `21.10.01`)                     |
| software-inventory.software-slot.product-code   | Software product code                                                      |
| software-inventory.software-slot.running        | Software running status                                                    |
| software-inventory.software-slot.status         | Software slot status                                                       |
| software-inventory.software-slot.vendor-code    | Software vendor code                                                       |
| ret.ret-info.object                             | RET (Remote Electrical Tilt) object path                                   |
| ret.ret-info.antenna-id                         | Antenna identifier                                                         |
| ret.ret-info.antenna-model-number               | Antenna model name (e.g., `NOKIA_AHFB`)                                    |
| ret.ret-info.antenna-operating-band             | Antenna operating band                                                     |
| ret.ret-info.antenna-serial-number              | Antenna serial number                                                      |
| ret.ret-info.beam-width                         | Antenna beam width                                                         |
| ret.ret-info.config-antenna-bearing             | Configured antenna bearing in degrees (e.g., `120`)                        |
| ret.ret-info.config-base-station-id             | Configured base station identifier                                          |
| ret.ret-info.config-install-date                | Configured installation date                                               |
| ret.ret-info.config-installed-tilt              | Configured installed antenna tilt in degrees                                |
| ret.ret-info.config-installer-id                | Configured installer identifier                                            |
| ret.ret-info.config-sector-id                   | Configured sector identifier                                               |
| ret.ret-info.config-tilt                        | Configured antenna tilt angle in degrees (e.g., `5.0`)                     |
| ret.ret-info.current-antenna-bearing            | Current antenna bearing in degrees                                          |
| ret.ret-info.current-base-station-id            | Current base station identifier                                            |
| ret.ret-info.current-install-date               | Current installation date                                                  |
| ret.ret-info.current-installed-tilt             | Current installed antenna tilt in degrees                                  |
| ret.ret-info.current-installer-id               | Current installer identifier                                               |
| ret.ret-info.current-sector-id                  | Current sector identifier                                                  |
| ret.ret-info.current-tilt                       | Current antenna tilt angle in degrees                                      |
| ret.ret-info.gain                               | Antenna gain                                                               |
| ret.ret-info.maximum-tilt                       | Maximum antenna tilt angle in degrees                                      |
| ret.ret-info.minimum-tilt                       | Minimum antenna tilt angle in degrees                                      |
| ret.ret-info.user-label                         | User-defined label for RET                                                 |
| region                                          | Region code (e.g., `USE1`)                                                |

- **Sample Rows**:  

| user-label      | ret.ret-info.current-base-station-id   | ret.ret-info.antenna-model-number | ret.ret-info.antenna-operating-band        | ret.ret-info.current-tilt | ret.ret-info.current-antenna-bearing | antenna-line-device.antenna-line-device-info.antenna-serial-number | software-inventory.software-slot.build-version | region | dl_year | dl_month |
|-----------------|----------------------------------------|----------------------------------|-------------------------------------------|---------------------------|-------------------------------------|------------------------------------------------------------------|----------------------------------------------|--------|---------|----------|
| PHPHL00559A     | PHPHL00559A_A21M                      | 12044x-R2-A                     | B5,B6,B8,B12,B13,B14                     | 80                        | -1                                  | 00000000061157562                                                | 3121                                         | USE1   | 2025    | 6        |
| BOBOS00229A     | BOBOS00229A_B12L                      | FFVV-65B-R2                     | B5,B6                                    | 20                        | 140                                 | 0021IN021758770R1                                                | 10.22316955                                  | USE1   | 2025    | 6        |
| BOBOS00869A     | BOBOS00869A_C21M                      | FFVV-65B-R2                     | B1,B2,B3,B4                              | 20                        | 120                                 | 0021IN021679847B1                                                | 10.22316955                                  | USE1   | 2025    | 6        |


## 2. `dl_silver_ran_samsung_piiprod.usm_cm_config_cucp_1d` (CUCP Config Table)  
- **Purpose**: Stores daily Centralized Unit Control Plane (CUCP) configuration details for Samsung 5G RAN.  
- **Content**: Includes CUCP state, cell configurations, F1 interface mappings, network parameters, and disaster recovery settings.  
- **Columns**:  

Here's the complete markdown table with all columns from the provided table schema:

| Column Name                                     | Description                                                                 |
|-------------------------------------------------|-----------------------------------------------------------------------------|
| ne-id                                           | Network Element ID for CUCP (e.g., `415007026`)                             |
| ne-type                                         | Type of network element (e.g., `uacpf`)                                     |
| cu.administrative-state                         | CUCP state (`unlocked` or `locked`)                                        |
| cu.cu-reparenting                               | CU reparenting status (e.g., `false`)                                       |
| cu.operational-mode                             | Operational mode of the CU (e.g., `normal`)                                 |
| cu.operational-state                            | Current operational state of the CU (e.g., `enabled`)                       |
| cu.system-type                                  | Type of system the CU belongs to (e.g., `5G`)                               |
| cu.user-label                                   | User-defined label for CU (e.g., `PHPHL00606A_CU`)                          |
| gutran-cu-cell-entries.object                   | Object path for GUTRAN CU cell entries                                     |
| gutran-cu-cell-entries.cell-identity            | Unique cell identifier (e.g., `541`)                                       |
| gutran-cu-cell-entries.disaster-recovery-flag   | Disaster recovery setting (e.g., `false`)                                  |
| gutran-cu-cell-entries.dss-enabled              | Dynamic Spectrum Sharing enabled status (e.g., `true`)                     |
| gutran-cu-cell-entries.f1-gnb-du-id              | F1 interface identifier (e.g., `1`)                                        |
| gutran-cu-cell-entries.imd-interference-detection | Interference detection setting (e.g., `enabled`)                         |
| gutran-cu-cell-entries.imd-interference-detection-per-duplex | Interference detection per duplex mode (e.g., `enabled`)             |
| gutran-cu-cell-entries.nr-ul-coverage-method    | Uplink coverage method for NR (e.g., `rsrp`)                                |
| gutran-cu-cell-entries.preemption-with-redirection | Preemption with redirection setting (e.g., `disabled`)                   |
| gutran-cu-cell-entries.ul-primary-path-mode     | Uplink primary path mode (e.g., `f1-c`)                                    |
| served-cell-info.cell-direction                 | Direction of the cell (e.g., `downlink`)                                   |
| served-cell-info.cell-plmn-info.mcc             | Mobile Country Code (e.g., `310`)                                          |
| served-cell-info.cell-plmn-info.mnc             | Mobile Network Code (e.g., `410`)                                          |
| served-cell-info.cell-plmn-info.plmn-index      | PLMN index (e.g., `0`)                                                     |
| served-cell-info.configured-tac-indication      | Configured TAC indication (e.g., `true`)                                    |
| served-cell-info.mapping-end-point-f1-index      | F1 index for mapping end point (e.g., `1`)                                 |
| served-cell-info.nr-arfcn-dl-point-a            | Downlink ARFCN for point A (e.g., `431500`)                                |
| served-cell-info.nr-arfcn-ul-point-a            | Uplink ARFCN for point A (e.g., `431500`)                                  |
| served-cell-info.nr-frequency-band-info.nr-frequency-band | Operating band (e.g., `n71`)                                         |
| served-cell-info.nr-frequency-band-info.nr-frequency-band-index | Frequency band index (e.g., `1`)                                   |
| served-cell-info.nr-physical-cell-id            | Physical Cell ID (PCI) (e.g., `889`)                                       |
| served-cell-info.nr-scs-dl                      | Subcarrier spacing for downlink (e.g., `15kHz`)                            |
| served-cell-info.nr-scs-ul                      | Subcarrier spacing for uplink (e.g., `15kHz`)                              |
| served-cell-info.nrb-dl                         | Number of resource blocks for downlink (e.g., `52`)                        |
| served-cell-info.nrb-ul                         | Number of resource blocks for uplink (e.g., `52`)                          |
| served-cell-info.service-state                  | Cell service state (e.g., `inService`)                                     |
| served-cell-info.ssb-arfcn                      | SSB ARFCN (e.g., `431500`)                                                 |
| served-cell-info.tracking-area-code             | Tracking Area Code (e.g., `0x0001`)                                        |
| region                                          | Region code (e.g., `USE1`)                                                 |

- **Sample Rows**:  

| zip_time_stamp | xml_time_stamp | ne-id | ne-type | cu.administrative-state | cu.cu-reparenting | cu.operational-mode | cu.operational-state | cu.system-type | cu.user-label | gutran-cu-cell-entries.object | gutran-cu-cell-entries.cell-identity | gutran-cu-cell-entries.disaster-recovery-flag | gutran-cu-cell-entries.dss-enabled | gutran-cu-cell-entries.f1-gnb-du-id | gutran-cu-cell-entries.imd-interference-detection | gutran-cu-cell-entries.imd-interference-detection-per-duplex | gutran-cu-cell-entries.nr-ul-coverage-method | gutran-cu-cell-entries.preemption-with-redirection | gutran-cu-cell-entries.ul-primary-path-mode | served-cell-info.cell-direction | served-cell-info.cell-plmn-info.mcc | served-cell-info.cell-plmn-info.mnc | served-cell-info.cell-plmn-info.plmn-index | served-cell-info.configured-tac-indication | served-cell-info.mapping-end-point-f1-index | served-cell-info.nr-arfcn-dl-point-a | served-cell-info.nr-arfcn-ul-point-a | served-cell-info.nr-frequency-band-info.nr-frequency-band | served-cell-info.nr-frequency-band-info.nr-frequency-band-index | served-cell-info.nr-physical-cell-id | served-cell-info.nr-scs-dl | served-cell-info.nr-scs-ul | served-cell-info.nrb-dl | served-cell-info.nrb-ul | served-cell-info.service-state | served-cell-info.ssb-arfcn | served-cell-info.tracking-area-code | region | zip_file_name | zip_file_size | xml_file_name | xml_file_size | dl_year | dl_month | dl_day |
|----------------|----------------|-------|---------|-------------------------|-------------------|---------------------|----------------------|----------------|---------------|------------------------------|-------------------------------------|---------------------------------------------|----------------------------------|------------------------------------|-----------------------------------------------|--------------------------------------------------|--------------------------------------------|------------------------------------------------|-------------------------------------------|--------------------------------|------------------------------------|------------------------------------|------------------------------------------|------------------------------------------|--------------------------------------------|------------------------------------|------------------------------------|--------------------------------------------------|-------------------------------------------------------|------------------------------------|---------------------------|---------------------------|------------------------|------------------------|------------------------------|---------------------------|------------------------------------|--------|---------------|---------------|---------------|---------------|---------|----------|--------|
| 2025-06-23 12:00:28.000000 UTC | 2025-06-22 07:46:53.000000 UTC | 741025000 | acpf | unlocked | NULL | NULL | enabled | gnb-cu-cp-cnf | LSSNA741025000 | managed-element/gnb-cu-cp-function/.../cell-identity=163 | 163 | false | false | 741025008 | disable | 11111111 | off | not-use | initial-SCG | both | 313 | 340 | 0 | not-use | 11 | 431050 | 351050 | 66 | 0 | 679 | scs-15 | scs-15 | nrb-25 | nrb-25 | in-service | 431530 | 01223B | USW2 | 10.220.106.68.7z | 28.1 MB | ACPF_741025000.xml | 12.6 MB | 2025 | 6 | 23 |

## 3. `DISH_MNO_OUTBOUND.GENAI_APP.USM_CM_CONFIG_CUCP_PARAMETERS` (CUCP Parameters Table)  
- **Purpose**: Stores CUCP configuration parameters for 5G NR cells.  
- **Content**: Focuses on handover and measurement parameters for mobility and signal quality. It contains information at DU, CU, and cell level. 
- **Note**: If query asked about a DU node or CUCP node and that table has not that information like frequency then this table can handle those queries.
- **Columns**:  

Here's the markdown table with all columns from the provided table structure:

| Column Name                        | Description                                                                 |
|------------------------------------|-----------------------------------------------------------------------------|
| cell_name                          | Cell identifier (e.g., `BOBOS01075F_2_n71_F-G`)                            |
| gnodeb_id                          | gNodeB identifier                                                          |
| cell_identity                      | Cell identity within gNodeB                                                |
| cucp_id                            | Centralized Unit Control Plane identifier                                  |
| du_id                              | Distributed Unit identifier                                                |
| report_config_entry_index          | Report configuration entry index                                           |
| ssb_config_ssb_freq                | SSB frequency configuration (kHz)                                           |
| purpose                            | Configuration purpose                                                      |
| band                               | Frequency band                                                             |
| hysteresis                         | Handover hysteresis value (dB)                                             |
| report_on_leave                    | Report when leaving condition                                              |
| threshold_rsrp                     | RSRP threshold (dBm)                                                       |
| threshold1_rsrp                    | First RSRP threshold (dBm)                                                 |
| threshold2_rsrp                    | Second RSRP threshold (dBm)                                                |
| threshold_rsrq                     | RSRQ threshold (dB)                                                        |
| threshold1_rsrq                    | First RSRQ threshold (dB)                                                  |
| threshold2_rsrq                    | Second RSRQ threshold (dB)                                                 |
| threshold_sinr                     | SINR threshold (dB)                                                        |
| threshold1_sinr                    | First SINR threshold (dB)                                                  |
| threshold2_sinr                    | Second SINR threshold (dB)                                                 |
| time_to_trigger                    | Time to trigger event (ms)                                                 |
| a3_offset_rsrp                     | Event A3 offset for RSRP (dB)                                              |
| threshold_selection_trigger_quantity | Trigger quantity for threshold selection                                  |
| threshold_selection_trigger_quantity_sinr | Trigger quantity for SINR threshold selection                          |
| report_type / event type                  | Type of measurement report    (a1,a2..)                                             |                                              |

- **Sample Rows**:  

| cell_name             | gnodeb_id | cell_identity | cucp_id   | du_id     | report_config_entry_index | ssb_config_ssb_freq | purpose                   | band  | hysteresis | report_on_leave | threshold_rsrp | threshold1_rsrp | threshold2_rsrp | threshold_rsrq | threshold1_rsrq | threshold2_rsrq | threshold_sinr | threshold1_sinr | threshold2_sinr | time_to_trigger | a3_offset_rsrp | threshold_selection_trigger_quantity | threshold_selection_trigger_quantity_sinr | report_type |
|-----------------------|-----------|---------------|-----------|-----------|----------------------------|---------------------|---------------------------|-------|------------|-----------------|----------------|------------------|------------------|----------------|------------------|------------------|----------------|------------------|------------------|------------------|-----------------|---------------------------------------|--------------------------------------------|-------------|
| BOBOS01075F_2_n71_F-G | 331011    | 847           | 331011000 | 331011041 | 11                         | 123870              | intra‑nr‑handover‑purpose | n71_A | 1          | false           | 51             | null             | null             | 79             | null             | null             | 79             | null             | null             | ms640            | 77              | rsrp                                  | false                                      | A3          |

## 4. `dl_silver_ran_samsung_piiprod.usm_cm_config_du_1d` (DU Config Table)  
- **Purpose**: Stores daily configuration details for the Distributed Unit (DU) in Samsung 5G RAN.  
- **Content**: Captures DU state, cell configurations, cell access info, physical configuration, Supplemental Downlink (SDL) support, and metadata.  
- **Columns**:  

| Column Name                                       | Description                                                                 |
|---------------------------------------------------|-----------------------------------------------------------------------------|
| zip_time_stamp                                    | Time of data archiving (e.g., `2025-06-23 12:00:19.000000 UTC`)             |
| xml_time_stamp                                    | Time of XML configuration generation (e.g., `2025-06-21 03:56:22.000000 UTC`) |
| ne-id                                             | Network Element ID for DU (e.g., `415007026`)                               |
| ne-type                                           | Type of network element (e.g., `uadpf`)                                     |
| du.administrative-state                           | DU state (`unlocked` or `locked`)                                          |
| du.du-reparenting                                 | Boolean for reparenting status (e.g., `false`)                              |
| du.operational-mode                               | Operational mode (e.g., empty or `normal`)                                  |
| du.user-label                                     | DU site identifier (e.g., `PHPHL00606A`)                                   |
| gutran-du-cell-entries.object                     | Configuration path (e.g., `managed-element/gnb-du-function/.../cell-identity=541`) |
| gutran-du-cell-entries.cell-identity              | Unique cell ID within DU (e.g., `541`)                                      |
| gutran-du-cell-entries.administrative-state       | Cell state (`unlocked` or `locked`)                                        |
| gutran-du-cell-entries.auto-unlock-flag           | Auto-unlock setting (e.g., `off`)                                          |
| gutran-du-cell-entries.beam-level-statistic-type-switch | Beam statistics toggle (e.g., `true`)                                |
| gutran-du-cell-entries.cell-num                   | Cell number/index (e.g., `11`)                                             |
| gutran-du-cell-entries.cell-path-type             | Path type (e.g., `select-abcd`)                                            |
| gutran-du-cell-entries.dl-subcarrier-spacing       | Downlink subcarrier spacing (e.g., `subcarrier-spacing-15khz`)              |
| gutran-du-cell-entries.dpp-id                     | Digital Processing Platform ID (e.g., `0`)                                  |
| gutran-du-cell-entries.power                      | Cell transmission power in dBm (e.g., `38.82`)                             |
| gutran-du-cell-entries.subcarrier-spacing-common   | Common subcarrier spacing (e.g., `subcarrier-spacing-15-or-60`)            |
| gutran-du-cell-entries.ul-subcarrier-spacing       | Uplink subcarrier spacing (e.g., `subcarrier-spacing-15khz`)                |
| gutran-du-cell-entries.user-label                 | Cell label (e.g., `PHPHL00606A_2_N66_G`)                                   |
| cell-access-info.cell-barred                      | Barred status (e.g., `not-barred`)                                         |
| cell-access-info.cell-barred-redcap-1rx           | Barred for RedCap 1Rx (e.g., `not-barred`)                                 |
| cell-access-info.cell-barred-redcap-2rx           | Barred for RedCap 2Rx (e.g., `not-barred`)                                 |
| cell-access-info.cell-reserved-for-future-use     | Reserved status (e.g., `not-reserved`)                                     |
| cell-access-info.cell-reserved-for-operator-use   | Operator reserved (e.g., `not-reserved`)                                   |
| cell-access-info.cell-reserved-for-other-use      | Other reserved (e.g., `not-reserved`)                                      |
| cell-access-info.configured-eps-tracking-area-code | EPS tracking area code (e.g., `1`)                                        |
| cell-access-info.configured-eps-tracking-area-code-usage | EPS TAC usage (e.g., `not-use`)                              |
| cell-access-info.intra-freq-reselection           | Intra-frequency reselection (e.g., `allowed`)                              |
| cell-access-info.intra-freq-reselection-redcap    | RedCap reselection (e.g., `not-allowed`)                                   |
| cell-access-info.ran-area-code                    | RAN area code (e.g., `0`)                                                  |
| cell-access-info.ran-area-code-usage              | RAN area code usage (e.g., `not-use`)                                      |
| cell-access-info.tracking-area-code               | Tracking area code (e.g., `00A2E2`)                                        |
| cell-access-info.tracking-area-code-usage         | TAC usage (e.g., `use`)                                                    |
| cell-physical-conf-idle.nr-arfcn-dl               | Downlink ARFCN (e.g., `431500`)                                            |
| cell-physical-conf-idle.nr-arfcn-ul               | Uplink ARFCN (e.g., `351500`)                                              |
| cell-physical-conf-idle.nr-bandwidth-dl           | Downlink bandwidth (e.g., `nr-bandwidth-5`)                                |
| cell-physical-conf-idle.nr-bandwidth-ul           | Uplink bandwidth (e.g., `nr-bandwidth-5`)                                  |
| cell-physical-conf-idle.nr-physical-cell-id       | Physical Cell ID (PCI) (e.g., `889`)                                       |
| cell-physical-conf-idle.sdl-support               | Boolean for SDL support (e.g., `true`)                                     |
| region                                            | Region code (e.g., `USE1`)                                                 |
| zip_file_name                                     | Archive file name (e.g., `10.228.122.133.7z`)                              |
| zip_file_size                                     | Archive file size (e.g., `51.1 MB`)                                        |
| xml_file_name                                     | XML configuration file name (e.g., `UADPF_415007026.xml`)                  |
| xml_file_size                                     | XML file size (e.g., `3.4 MB`)                                             |
| dl_year                                           | Year partition (e.g., `2025`)                                               |
| dl_month                                          | Month partition (e.g., `6`)                                                |
| dl_day                                            | Day partition (e.g., `23`)                                                 |

- **Sample Rows**:  

| zip_time_stamp                     | xml_time_stamp                     | ne-id      | ne-type | du.administrative-state | du.du-reparenting | du.operational-mode | du.user-label   | gutran-du-cell-entries.object                                                  | gutran-du-cell-entries.cell-identity | gutran-du-cell-entries.administrative-state | gutran-du-cell-entries.auto-unlock-flag | gutran-du-cell-entries.beam-level-statistic-type-switch | gutran-du-cell-entries.cell-num | gutran-du-cell-entries.cell-path-type | gutran-du-cell-entries.dl-subcarrier-spacing | gutran-du-cell-entries.dpp-id | gutran-du-cell-entries.power | gutran-du-cell-entries.subcarrier-spacing-common | gutran-du-cell-entries.ul-subcarrier-spacing | gutran-du-cell-entries.user-label         | cell-access-info.cell-barred | cell-access-info.cell-barred-redcap-1rx | cell-access-info.cell-barred-redcap-2rx | cell-access-info.cell-reserved-for-future-use | cell-access-info.cell-reserved-for-operator-use | cell-access-info.cell-reserved-for-other-use | cell-access-info.configured-eps-tracking-area-code | cell-access-info.configured-eps-tracking-area-code-usage | cell-access-info.intra-freq-reselection | cell-access-info.intra-freq-reselection-redcap | cell-access-info.ran-area-code | cell-access-info.ran-area-code-usage | cell-access-info.tracking-area-code | cell-access-info.tracking-area-code-usage | cell-physical-conf-idle.nr-arfcn-dl | cell-physical-conf-idle.nr-arfcn-ul | cell-physical-conf-idle.nr-bandwidth-dl | cell-physical-conf-idle.nr-bandwidth-ul | cell-physical-conf-idle.nr-physical-cell-id | cell-physical-conf-idle.sdl-support | region | zip_file_name            | zip_file_size | xml_file_name            | xml_file_size | dl_year | dl_month | dl_day |
|------------------------------------|------------------------------------|------------|---------|-------------------------|-------------------|---------------------|-----------------|--------------------------------------------------------------------------------|-------------------------------------|--------------------------------------------|----------------------------------------|-------------------------------------------------------|-------------------------------|--------------------------------------|--------------------------------------------|-----------------------------|-----------------------------|------------------------------------------------|--------------------------------------------|------------------------------------------|------------------------------|----------------------------------------|----------------------------------------|----------------------------------------------|------------------------------------------------|---------------------------------------------|--------------------------------------------------|--------------------------------------------------------|---------------------------------------|----------------------------------------------|-------------------------------|-------------------------------------|------------------------------------|-----------------------------------------|------------------------------------|------------------------------------|---------------------------------------|---------------------------------------|-------------------------------------------|------------------------------------|--------|--------------------------|---------------|--------------------------|---------------|---------|----------|--------|
| 2025-06-23 12:00:19.000000 UTC    | 2025-06-21 03:56:22.000000 UTC    | 415007026  | uadpf   | unlocked                | false             |                     | PHPHL00606A     | managed-element/gnb-du-function/gutran-du-cell/gutran-du-cell-entries/cell-identity=541 | 541                                 | unlocked                                   | off                                    | true                                                  | 11                            | select-abcd                          | subcarrier-spacing-15khz                   | 0                           | 38.82                       | subcarrier-spacing-15-or-60                    | subcarrier-spacing-15khz                   | PHPHL00606A_2_N66_G                      | not-barred                   | not-barred                             | not-barred                             | not-reserved                                 | not-reserved                                   | not-reserved                                | 1                                                | not-use                                                | allowed                               | not-allowed                                  | 0                             | not-use                             | 00A2E2                             | use                                     | 431500                             | 351500                             | nr-bandwidth-5                        | nr-bandwidth-5                        | 889                                       | false                              | USE1   | 10.228.122.133.7z        | 51.1 MB       | UADPF_415007026.xml      | 3.4 MB        | 2025    | 6        | 23     |
| 2025-06-23 12:00:19.000000 UTC    | 2025-06-21 03:56:22.000000 UTC    | 415007026  | uadpf   | unlocked                | false             |                     | PHPHL00606A     | managed-element/gnb-du-function/gutran-du-cell/gutran-du-cell-entries/cell-identity=538 | 538                                 | unlocked                                   | off                                    | true                                                  | 2                             | select-abcd                          | subcarrier-spacing-15khz                   | 0                           | 46.02                       | subcarrier-spacing-15-or-60                    | subcarrier-spacing-15khz                   | PHPHL00606A_2_N70_AWS-4_UL15             | not-barred                   | not-barred                             | not-barred                             | not-reserved                                 | not-reserved                                   | not-reserved                                | 1                                                | not-use                                                | allowed                               | not-allowed                                  | 0                             | not-use                             | 00A2E2                             | use                                     | 401500                             | 340500                             | nr-bandwidth-25                       | nr-bandwidth-15                       | 889                                       | false                              | USE1   | 10.228.122.133.7z        | 51.1 MB       | UADPF_415007026.xml      | 3.4 MB        | 2025    | 6        | 23     |

# Step-by-Step Reasoning Process

## 1. Identify the Primary Focus of Your Query
- Are you asking about **antenna configurations** or **radio units** (e.g., tilt settings in `tilt`, antenna models in `antenna-model`, or software versions in `software-version`)?  
  → Choose the **RET State Table (`usm_cm_ret_state_1d`)**.  
- Are you asking about **CUCP operational details** or ** At CUCP level cell configurations** (e.g., CUCP state in `cucp.administrative-state`, F1 interface mappings in `f1-interface-id`, or frequency bands in `frequency-band`)?  
  → Choose the **CUCP Config Table (`usm_cm_config_cucp_1d`)**.  
- Are you asking about **handover parameters** or **measurement thresholds** (e.g., RSRP thresholds in `rsrp-threshold`, hysteresis in `hysteresis`, or report types in `report-type`)?  
  → Choose the **CUCP Parameters Table (`USM_CM_CONFIG_CUCP_PARAMETERS`)**.  
- Are you asking about **DU state**, **cell-level configurations**, or **physical settings** (e.g., DU status in `du.user-label`, cell power in `gutran-du-cell-entries.power`, or SDL support in `cell-physical-conf-idle.sdl-support`)?  
  → Choose the **DU Config Table (`usm_cm_config_du_1d`)**.  

## 2. Look for Specific Keywords or Terms in Your Query
- **RET State Table**: Keywords like "antenna," "tilt," "bearing," "RU ID," "serial number," "software slot," or "radio unit."  
- **CUCP Config Table**: Keywords like "CUCP," "cell identity," "frequency band," "ARFCN," "PCI," "F1 interface," or "disaster recovery."  
- **CUCP Parameters Table**: Keywords like "report config index", "frequency", "threshold," "RSRP," "RSRQ," "SINR," "hysteresis," "time to trigger," "report type," "handover," or "offset."  
- **DU Config Table**: Keywords like "DU," "administrative state," "cell barred," "subcarrier spacing," "power," "tracking area code," "ARFCN," "PCI," "bandwidth," or "SDL."  

## 3. Consider the Type of Information Requested
- **Physical antenna properties** or **radio unit details** (e.g., tilt angle from `tilt`, antenna bearing from `bearing`, or software version from `software-version`)?  
  → Use the **RET State Table** (e.g., rows show `tilt` as `5.0` or `7.5`).  
- **Network configuration** or **cell-level settings** at the CUCP level (e.g., frequency bands from `frequency-band`, F1 interface mappings from `f1-interface-id`)?  
  → Use the **CUCP Config Table** (e.g., rows show `frequency-band` as `n71` or `n66`).  
- **Handover or measurement parameters at cell/ site level** (e.g., RSRP thresholds from `rsrp-threshold`, report triggers , frequency from `report-type`)?  
  → Use the **CUCP Parameters Table** (e.g., rows show `rsrp-threshold` as `-95` or `-90`).  
- **DU operational state**, **cell configurations**, or **physical resources** (e.g., cell power from `gutran-du-cell-entries.power`, DL ARFCN from `cell-physical-conf-idle.nr-arfcn-dl`, or SDL support from `cell-physical-conf-idle.sdl-support`)?  
  → Use the **DU Config Table** (e.g., rows show `power` as `38.82` or `44.77`).  

## 4. Evaluate the Context of Your Query
- If your query involves a **specific site or sector** and focuses on **antenna settings** (e.g., "tilt at site BOBOS01075F" involving `tilt`), the **RET State Table** provides detailed antenna data (e.g., columns like `tilt`, `bearing`).  
- If your query involves **network performance** or **cell coverage** at the CUCP level (e.g., "cells in service at site LSSNA" involving `cucp.administrative-state`), the **CUCP Config Table** is more appropriate (e.g., columns like `service-state`, `cell-identity`).  
- If your query involves **mobility or signal quality** (e.g., "RSRP threshold for n71 band" involving `rsrp-threshold`), the **CUCP Parameters Table** is the best fit (e.g., columns like `rsrp-threshold`, `hysteresis`, `frequency` at cell/site level).  
- If your query involves **DU operations**, **cell access**, or **physical configurations** (e.g., "power settings at site PHPHL00606A" involving `gutran-du-cell-entries.power` or "SDL support for n66 band" involving `cell-physical-conf-idle.sdl-support`), the **DU Config Table** is the best choice (e.g., columns like `gutran-du-cell-entries.power`, `cell-physical-conf-idle.nr-arfcn-dl`).  
- For Queries related to a column that is present is multiple columns like frequency , always focus at the nodet type(CUCP, DU, CUUP, Site etc) . For eg if query is like: What is the frequency for the cell BOBOS01075F_1_n70_AWS-4_UL10 (you should choose `USM_CM_CONFIG_CUCP_PARAMETERS`)

## 5. If Unsure, Consider the Intent of Your Query
- Troubleshooting **antenna issues** or optimizing **antenna settings** (e.g., adjusting `tilt` or verifying `antenna-model`)?  
  → Select the **RET State Table** (e.g., columns like `antenna-model`, `software-version`).  
- Analyzing **CUCP network configuration** or **cell performance** (e.g., checking `frequency-band` or `f1-interface-id`)?  
  → Select the **CUCP Config Table** (e.g., columns like `frequency-band`, `disaster-recovery-mode`).  
- Investigating **handover behavior** or **measurement criteria** (e.g., analyzing `rsrp-threshold` or `hysteresis`)?  
  → Select the **CUCP Parameters Table** (e.g., columns like `rsrp-threshold`, `report-type`).  
- Investigating **DU status**, **cell configurations**, or **resource allocation** (e.g., verifying `gutran-du-cell-entries.power`, `cell-physical-conf-idle.nr-arfcn-dl`, or `cell-physical-conf-idle.sdl-support`)?  
  → Select the **DU Config Table** (e.g., columns like `du.user-label`, `cell-physical-conf-idle.sdl-support`).  

# Example Usage

## Example 1
**Query**: "What is the current tilt of the antenna at site BOBOS01075F?"  
- **Step 1**: Focus is on antenna configurations (tilt).  
- **Step 2**: Keywords "tilt" and "antenna" align with `tilt` column.  
- **Step 3**: Requests physical antenna properties (e.g., `tilt`, `bearing`).  
- **Step 4**: Context is site-specific antenna settings.  
- **Step 5**: Intent is to retrieve antenna settings.  
**Conclusion**: Use the **RET State Table (`usm_cm_ret_state_1d`)** (e.g., columns like `tilt`, `ru-id`).  

## Example 2
**Query**: "What cells use band n71 at site CHCHI?"  
- **Step 1**: Focus is on cell configurations (band usage).  
- **Step 2**: Keywords "cell" and "band n71" align with `frequency-band` column.  
- **Step 3**: Requests network configuration data (e.g., `frequency-band`, `cell-identity`).  
- **Step 4**: Context is site-specific cell settings.  
- **Step 5**: Intent is to analyze cell configurations.  
**Conclusion**: Use the **CUCP Config Table (`usm_cm_config_cucp_1d`)** (e.g., columns like `frequency-band`, `cell-user-label`).  

## Example 3
**Query**: "What is the RSRP threshold for cell BOBOS01075F_2_n71_F-G?"  
- **Step 1**: Focus is on measurement thresholds (RSRP).  
- **Step 2**: Keywords "RSRP" and "threshold" align with `rsrp-threshold` column.  
- **Step 3**: Requests handover/measurement parameters (e.g., `rsrp-threshold`, `hysteresis`).  
- **Step 4**: Context is cell-specific threshold settings.  
- **Step 5**: Intent is to investigate signal quality parameters.  
**Conclusion**: Use the **CUCP Parameters Table (`USM_CM_CONFIG_CUCP_PARAMETERS`)** (e.g., columns like `rsrp-threshold`, `report-type`).  

## Example 4
**Query**: "What is the power setting for cells at site PHPHL00606A?"  
- **Step 1**: Focus is on cell configurations (power settings).  
- **Step 2**: Keywords "power" and "cell" align with `gutran-du-cell-entries.power` column.  
- **Step 3**: Requests DU-level cell configuration data (e.g., `gutran-du-cell-entries.power`).  
- **Step 4**: Context is site-specific cell settings.  
- **Step 5**: Intent is to analyze DU cell configurations.  
**Conclusion**: Use the **DU Config Table (`usm_cm_config_du_1d`)** (e.g., columns like `gutran-du-cell-entries.power`, `du.user-label`).  

## Example 5
**Query**: "Which cells at site DCWDC00358B support Supplemental Downlink (SDL)?"  
- **Step 1**: Focus is on physical cell configurations (SDL support).  
- **Step 2**: Keywords "SDL" and "cell" align with `cell-physical-conf-idle.sdl-support` column.  
- **Step 3**: Requests DU-level physical configuration data (e.g., `cell-physical-conf-idle.sdl-support`).  
- **Step 4**: Context is site-specific physical settings.  
- **Step 5**: Intent is to investigate DU resource allocation.  
**Conclusion**: Use the **DU Config Table (`usm_cm_config_du_1d`)** (e.g., columns like `cell-physical-conf-idle.sdl-support`, `gutran-du-cell-entries.cell-identity`).  

## Final Response
**Final Response** :Always provide only one single table name in final response without any irrelevant information. It must one of the table name defined above.

By following this structured CoT reasoning process, you can confidently select the appropriate table for your query.
"""