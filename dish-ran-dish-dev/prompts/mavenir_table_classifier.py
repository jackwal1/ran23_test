mcms_table_classifier = """
# Prompt for Table Selection Based on Chain of Thought Reasoning

To determine the most suitable database table for your query, follow this step-by-step Chain of Thought (CoT) reasoning process. Below are the available tables, each with a description, all columns listed in Markdown format with detailed descriptions, and sample rows to clarify their content and purpose. Only one table can be selected per query based on its primary focus.

## 1. `mcms_cm_ret_state_12hr` (RET State Table)
- **Purpose**: Stores Antenna Remote Electrical Tilt (RET) configuration states, updated every 12 hours.
- **Content**: Includes antenna configurations, radio unit details, sector assignments, and metadata for 5G network management.
- **Columns**:

| Column Name                          | Description                                                                 |
|--------------------------------------|-----------------------------------------------------------------------------|
| timestamp                            | Timestamp of the RET state record (e.g., `2025-08-03 00:00:00 UTC`)          |
| ald-port-id                          | ALD port identifier (e.g., `1`)                                             |
| ald-port-name                        | ALD port name (e.g., `PORT1`)                                              |
| antenna-fields.antenna-model-number  | Antenna model name (e.g., `FFVV-65B-R2`)                                    |
| antenna-fields.antenna-serial-number | Unique serial number of the antenna (e.g., `MX086652122139259`)             |
| antenna-fields.frequency-band        | Operating frequency band (e.g., `mid-band`, `C-band`)                       |
| antenna-fields.max-tilt              | Maximum supported tilt angle in degrees (e.g., `10.0`)                      |
| antenna-fields.min-tilt              | Minimum supported tilt angle in degrees (e.g., `0.0`)                       |
| antenna-fields.tilt-value            | Current antenna tilt angle in degrees (e.g., `5.0`)                         |
| du-id                                | Distributed Unit identifier (e.g., `DU1`)                                   |
| info.alarms-status                   | Status of alarms (e.g., `active`, `cleared`)                                |
| info.antenna-unit-number             | Antenna unit number (e.g., `1`)                                             |
| info.device-type                     | Type of device (e.g., `RET`)                                                |
| info.hardware-version                 | Hardware version of the device (e.g., `HW1.0`)                              |
| info.hdlc-address                    | HDLC address (e.g., `1`)                                                    |
| info.product-number                   | Product number (e.g., `PRD12345`)                                           |
| info.software-version                | Software version of the radio unit (e.g., `v4.2.1`)                         |
| info.unique-id                       | Unique identifier (e.g., `UID12345`)                                        |
| info.vendor-code                     | Vendor code (e.g., `VENDOR1`)                                               |
| operator-fields.antenna-bearing      | Antenna bearing in degrees (e.g., `120`)                                    |
| operator-fields.base-station-id      | Base station identifier (e.g., `BS123`)                                     |
| operator-fields.installation-date    | Date of antenna installation (e.g., `2024-06-15`)                           |
| operator-fields.installer-id         | Identifier of the installer (e.g., `INST123`)                               |
| operator-fields.mechanical-tilt      | Mechanical tilt angle in degrees (e.g., `2.0`)                              |
| operator-fields.sector-id            | Sector identifier, named or numeric (e.g., `ALPHA` or `1`)                  |
| recent-command-status                | Status of the most recent command (e.g., `success`, `failed`)               |
| ru-id                                | Radio Unit identifier (e.g., `RU1`)                                         |
| ru-ip-address                        | IP address of the Radio Unit (e.g., `10.0.0.1`)                             |
| ru-label                             | Site identifier for the radio unit (e.g., `CVCLE00435A`)                    |
| cluster                              | Cluster name (e.g., `USE1_CLUSTER`)                                         |

- **Sample Rows**:

| timestamp | ald-port-id | ald-port-name | antenna-model-number | antenna-serial-number | frequency-band | max-tilt | min-tilt | tilt-value | du-id | alarms-status | antenna-unit-number | device-type | hardware-version | hdlc-address | product-number | software-version | unique-id | vendor-code | antenna-bearing | base-station-id | installation-date | installer-id | mechanical-tilt | sector-id | recent-command-status | ru-id | ru-ip-address | ru-label | cluster |
|-----------|-------------|---------------|---------------------|----------------------|----------------|----------|----------|------------|-------|---------------|-------------------|-------------|------------------|--------------|----------------|------------------|-----------|-------------|-----------------|-----------------|-------------------|--------------|-----------------|-----------|----------------------|--------|---------------|----------|---------|
| 2025-06-24 00:00:00.000000 UTC | 0 | Ald-Port-0 | FFVV-65B-R2 | 21CN103914976 | [6,5] | 14.000000 | 2.000000 | 9.000000 | 515006012 | - | 1 | Single-Antenna RET | 00.00.00.00 | 1 | COMMRET2S | 000.051.047 | CP0021CN103914976R1 | CP | 120.000000 | ATBHM00451A | 111721 | WD | 0.000000 | ATBHM00451A_BETA_11L | SUCCESS | 515045122 | 10.39.51.29 | ATBHM00451A_MB_2 | mv-ndc-eks-cluster-prod-use1n003p1-04 |
| 2025-06-24 00:00:00.000000 UTC | 0 | Ald-Port-0 | MX0866521402AB1 | MX086652122139259 | [4,3,2,1,9,10,25,33,34,35,36,37,39] | 12.000000 | 2.000000 | 4.000000 | 113017001 | - | 1 | Single-Antenna RET | HW_R2000_A | 1 | R2000 JMARETSYS | FW_V1.0.4 | CC21390866522302-B1 | CC | 240.000000 | IND00435A--G21M | 012022 | RN | 0.000000 | Gamma | SUCCESS | 113043523 | 10

## 2. `mcms_cm_topology_state_cucp_12hr` (CUCP Topology State Table)
- **Purpose**: Stores Centralized Unit Control Plane (CUCP) topology states, updated every 12 hours.
- **Content**: Includes CUCP operational status, alarms, cell configurations, and network interface details.
- **Columns**:

| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| timestamp          | Timestamp of the topology state record (e.g., `2025-08-03 00:00:00 UTC`)    |
| admin_state        | Administrative state of the CUCP (e.g., `unlocked`, `locked`)               |
| alarm_count        | Number of active alarms associated with the CUCP (e.g., `2`)                |
| alarm_severity     | Highest severity of active alarms (e.g., `minor`, `critical`)               |
| cnfname            | Configuration name for the CUCP (e.g., `CUCP_Config1`)                     |
| gnbid              | gNodeB identifier (e.g., `12345`)                                           |
| gnblength          | Length of the gNodeB identifier (e.g., `5`)                                 |
| cucp_id            | CUCP identifier (e.g., `1`)                                                |
| linkstatus         | Status of network link (e.g., `up`, `down`)                                |
| name               | Unique identifier for the CUCP (e.g., `JKRLA627035000`)                     |
| operational_state  | Operational state of the CUCP (e.g., `enabled`, `degraded`, `disabled`)     |
| swversion          | Software version of the CUCP (e.g., `v2.1.3`)                              |
| type               | Type of the CUCP (e.g., `O-CUCP`)                                          |
| cluster            | Cluster to which the CUCP belongs (e.g., `USE1_CLUSTER`)                   |

- **Sample Rows**:

| timestamp | admin_state | alarm_count | alarm_severity | cnfname | gnbid | gnblength | cucp_id | linkstatus | name | operational_state | swversion | type | cluster | file_name | file_size | dl_year | dl_month | dl_day | dl_hour |
|-----------|-------------|-------------|----------------|---------|-------|-----------|---------|------------|------|-------------------|-----------|------|---------|-----------|-----------|---------|----------|--------|---------|
| 2025-06-23 00:00:00.000000 UTC | unlocked | 0 | NULL | CVCMH123003000 | 123003 | 24 | 123003000 | [] | mvnr-col-CMH-b1\|me-mtcil1\|123003000 | enabled | 5.0.816.44.V53 | CUCP | mv-ndc-eks-cluster-prod-use2n002p1-07 | mv-ndc-eks-cluster-prod-use2n002p1-07_topology_202506230.json | 4.8 MB | 2025 | 6 | 23 | 0 |
| 2025-06-23 00:00:00.000000 UTC | unlocked | 48 | SEVE_MAJOR | STSTL275019000 | 275019 | 24 | 275019000 | [] | mvnr-kan-stl-mtcil3\|me-mtcil3\|275019000 | enabled | 5.0.816.44.V49 | CUCP | mv-ndc-eks-cluster-prod-use2n002p1-03 | mv-ndc-eks-cluster-prod-use2n002p1-03_topology_202506230.json | 3.6 MB | 2025 | 6 | 23 | 0 |

## 3. `mcms_cm_topology_state_cuup_12hr` (CUUP Topology State Table)
- **Purpose**: Stores Centralized Unit User Plane (CUUP) topology states, updated every 12 hours.
- **Content**: Includes CUUP operational status, alarms, throughput, and network interface details.
- **Columns**:

| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| timestamp          | Timestamp of the topology state record (e.g., `2025-08-03 00:00:00 UTC`)    |
| admin_state        | Administrative state of the CUUP (e.g., `unlocked`, `locked`)               |
| alarm_count        | Number of active alarms associated with the CUUP (e.g., `0`)                |
| alarm_severity     | Highest severity of active alarms (e.g., `none`, `minor`)                  |
| cucp_id            | Centralized Unit Control Plane identifier (e.g., `1`)                       |
| cuup_id            | Centralized Unit User Plane identifier (e.g., `1`)                          |
| linkstatus         | Status of the network link (e.g., `up`, `down`)                             |
| name               | Unique identifier for the CUUP (e.g., `JKRLA627035001`)                     |
| operational_state  | Operational state of the CUUP (e.g., `enabled`, `degraded`, `disabled`)     |
| swversion          | Software version of the CUUP (e.g., `v2.1.3`)                              |
| type               | Type of the CUUP (e.g., `O-CUUP`)                                          |
| cluster            | Cluster to which the CUUP belongs (e.g., `USE1_CLUSTER`)                   |

- **Sample Rows**:

| timestamp | admin_state | alarm_count | alarm_severity | cucp_id | cuup_id | linkstatus | name | operational_state | swversion | type | cluster | file_name | file_size | dl_year | dl_month | dl_day | dl_hour |
|-----------|-------------|-------------|----------------|---------|---------|------------|------|-------------------|-----------|------|---------|-----------|-----------|---------|----------|--------|---------|
| 2025-06-23 00:00:00.000000 UTC | unlocked | 0 | NULL | 123003000 | 123003001 | [] | mvnr-col-CMH-b1\|me-mtcil1\|123003001 | enabled | 5.0.816.44.V53 | CUUP | mv-ndc-eks-cluster-prod-use2n002p1-07 | mv-ndc-eks-cluster-prod-use2n002p1-07_topology_202506230.json | 4.8 MB | 2025 | 6 | 23 | 0 |
| 2025-06-23 00:00:00.000000 UTC | UNLOCKED | 48 | SEVE_MAJOR | 275019000 | 275019001 | [] | mvnr-kan-stl-mtcil3\|me-mtcil3\|275019001 | enabled | 5.0.816.44.V49 | CUUP | mv-ndc-eks-cluster-prod-use2n002p1-03 | mv-ndc-eks-cluster-prod-use2n002p1-03_topology_202506230.json | 3.6 MB | 2025 | 6 | 23 | 0 |

## 4. `mcms_cm_topology_state_du_12hr` (DU Topology State Table)
- **Purpose**: Stores Distributed Unit (DU) topology states, updated every 12 hours.
- **Content**: Includes DU operational status, alarms, cell configurations, and interface details.
- **Columns**:

| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| timestamp          | Timestamp of the topology state record (e.g., `2025-08-03 00:00:00 UTC`)    |
| admin_state        | Administrative state of the DU (e.g., `unlocked`, `locked`)                 |
| alarm_count        | Number of active alarms associated with the DU (e.g., `1`)                  |
| alarm_severity     | Highest severity of active alarms (e.g., `minor`, `critical`)                |
| cnfname            | Configuration name of the DU (e.g., `DU_Config1`)                          |
| cucp_id            | Centralized Unit Control Plane identifier (e.g., `1`)                       |
| du_id              | Distributed Unit identifier (e.g., `1`)                                     |
| linkstatus         | Status of the DU connection links (e.g., `up`, `down`)                      |
| name               | Unique identifier for the DU (e.g., `DU-CVCLE00435A`)                       |
| operational_state  | Operational state of the DU (e.g., `enabled`, `disabled`, `degraded`)       |
| swversion          | Software version of the DU (e.g., `v3.0.1`)                                |
| type               | Type of the DU (e.g., `O-DU`)                                              |
| cluster            | Cluster to which the DU belongs (e.g., `USE1_CLUSTER`)                     |

- **Sample Rows**:

| timestamp | admin_state | alarm_count | alarm_severity | cnfname | cucp_id | du_id | linkstatus | name | operational_state | swversion | type | cluster | file_name | file_size | dl_year | dl_month | dl_day | dl_hour |
|-----------|-------------|-------------|----------------|---------|---------|-------|------------|------|-------------------|-----------|------|---------|-----------|-----------|---------|----------|--------|---------|
| 2025-06-25 00:00:00.000000 UTC | unlocked | 0 | NULL | JKMSY625007002 | 625007000 | 625007002 | [{{UP,,Netconf,625003522,RU}},{{UP,,Netconf,625003511,RU}},{{UP,,Netconf,625003521,RU}},{{UP,,Netconf,625003523,RU}},{{UP,,Netconf,625003513,RU}},{{UP,,Netconf,625003512,RU}},{{UP,10.227.25.25,F1-C,IP:10.227.25.25,CU-CP}}] | mvnr-at-jk04-opc\|me-mtcil1\|625007002 | enabled | 5.0.816.44.V49 | DU | mv-ndc-eks-cluster-prod-use2n002p1-04 | mv-ndc-eks-cluster-prod-use2n002p1-04_topology_202506250.json | 4.8 MB | 2025 | 6 | 25 | 0 |
| 2025-06-25 00:00:00.000000 UTC | UNLOCKED | 48 | SEVE_MAJOR | SDLAS851017001 | 851017000 | 851017001 | [{{UP,10.223.196.57,F1-C,IP:10.223.196.57,CU-CP}},{{UP,,Netconf,851002211,RU}},{{UP,,Netconf,851002212,RU}},{{UP,,Netconf,851002213,RU}},{{UP,,Netconf,851002221,RU}},{{UP,,Netconf,851002222,RU}},{{UP,,Netconf,851002223,RU}}] | mvnr-ls-sd03-opc\|me-mtcil1\|851017001 | enabled | 5.0.816.44.V49 | DU | mv-ndc-eks-cluster-prod-usw2n001p1-03 | mv-ndc-eks-cluster-prod-usw2n001p1-03_topology_202506250.json | 3.6 MB | 2025 | 6 | 25 | 0 |

## 5. `mcms_cm_topology_state_rru_12hr` (RRU Topology State Table)
- **Purpose**: Stores Remote Radio Unit (RRU) topology states, updated every 12 hours.
- **Content**: Includes RRU operational status, alarms, site details, and interface connectivity.
- **Columns**:

| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| timestamp          | Timestamp of the topology state record (e.g., `2025-08-03 00:00:00 UTC`)    |
| admin_state        | Administrative state of the RRU (e.g., `unlocked`, `locked`)                |
| alarm_count        | Number of active alarms associated with the RRU (e.g., `0`)                 |
| alarm_severity     | Highest severity of active alarms (e.g., `none`, `major`)                    |
| cucp_id            | Centralized Unit Control Plane identifier (e.g., `1`)                       |
| du_id              | Distributed Unit identifier (e.g., `1`)                                     |
| eu_id              | Edge Unit identifier (e.g., `1`)                                            |
| rru_id             | Remote Radio Unit identifier (e.g., `415007026`)                            |
| linkstatus         | Status of the connection link (e.g., `up`, `down`)                          |
| name               | Name of the RRU (e.g., `RRU-CVCLE00435A`)                                   |
| operational_state  | Current operational state of the RRU (e.g., `enabled`, `degraded`, `disabled`) |
| ru_id              | Radio Unit identifier (e.g., `415007026`)                                   |
| swversion          | Software version of the RRU (e.g., `v4.2.1`)                               |
| type               | Type of the radio unit (e.g., `RRU`)                                        |
| cluster            | Cluster to which the RRU belongs (e.g., `USE1_CLUSTER`)                    |

- **Sample Rows**:

| timestamp | admin_state | alarm_count | alarm_severity | cucp_id | du_id | eu_id | rru_id | linkstatus | name | operational_state | ru_id | swversion | type | cluster | file_name | file_size | dl_year | dl_month | dl_day | dl_hour |
|-----------|-------------|-------------|----------------|---------|-------|-------|--------|------------|------|-------------------|-------|-----------|------|---------|-----------|-----------|---------|----------|--------|---------|
| 2025-06-23 12:00:00.000000 UTC | unlocked | 0 | NULL | 275019000 | 275019014 | -1 | 275011422 | [{{UP,,Netconf,275011422,admf}},{{UP,,ecpri,275019014,du}}] | STSTL00114A_MB_2-2MFJC09914V | enabled | 275011422 | 3123 | RRU | mv-ndc-eks-cluster-prod-use2n002p1-03 | mv-ndc-eks-cluster-prod-use2n002p1-03_topology_2025062312.json | 3.6 MB | 2025 | 6 | 23 | 12 |
| 2025-06-23 12:00:00.000000 UTC | UNLOCKED | 48 | SEVE_MAJOR | 831003000 | 831003007 | -1 | 831004112 | [{{UP,,Netconf,831004112,admf}},{{DOWN,,ecpri,831003007,du}}] | SCRNO00041B_LB_2-3LFJC21776M | degraded | 831004112 | 3123 | RRU | mv-ndc-eks-cluster-prod-usw2n001p1-02 | mv-ndc-eks-cluster-prod-usw2n001p1-02_topology_2025062312.json | 2.9 MB | 2025 | 6 | 23 | 12 |


## 6. `mcms_cm_config_combined_12hr` (Stores maxallowedscells, slotaggrbasepathlossindb,sctpnodelay at  DU, CUCP, GNB level)
- **Purpose**: Stores configuration data for Mavenir RAN network elements, including CUCP and DU configurations at both cell and element levels. Updated every 12 hours with configuration snapshots.
- **Content**: Includes maxAllowedScells parameter for cell capacity, slotAggrBasePathLossInDb for radio performance, and sctpNoDelay for network optimization across different levels of the network architecture.
- **Columns**:

| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|

- **Sample Rows**:
| Column Name        | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| cucp_id           | Unique CUCP identifier (e.g., 535011000)                                    |
| gnb_id            | Base station identifier (e.g., 535011)                                      |
| celllocalid       | Cell identifier within the base station                                      |
| du_id             | Unique DU identifier (e.g., 535017013)                                      |
| cellid            | Cell identifier within the DU                                               |
| maxallowedscells  | Maximum number of secondary cells allowed (typically 0, 2, or 3)            |
| slotaggrbasepathlossindb | Slot aggregation base path loss in dB (critical for radio performance, typically 120-136) |
| cellreservedoperatoruse | Cell reservation status ('reserved' or 'notReserved')                      |
| plmnidindex       | PLMN configuration (typically 1)                                            |
| plmnidentityinfoindex | PLMN identity info index (typically 1)                                  |
| ranac             | Routing Area Code (often -1 if not configured)                             |
| tacbitmap         | Tracking Area Code bitmap (typically 1)                                     |
| sctpconfig_id     | SCTP configuration identifier (typically 1 or 2)                            |
| sctpnodelay       | Boolean flag for SCTP node delay (true/false)                               |
| cluster          | Kubernetes cluster hosting the network element                             |

- **Sample Rows**:
- **Sample Rows**:
| cucp_id | gnb_id | celllocalid | du_id | maxallowedscells | slotaggrbasepathlossindb | cellreservedoperatoruse | plmnidindex | plmnidentityinfoindex | ranac | tacbitmap | sctpconfig_id | sctpnodelay | swversion | cluster |
|---------|--------|-------------|-------|------------------|-------------------------|------------------------|-------------|----------------------|-------|-----------|---------------|-------------|-----------|---------|
| 535011000 | 535011 | 70 | 535011004 | 2 | 136 | notReserved | 1 | 1 | -1 | 1 | 1 | true | 5.0.728.106 | mv-ndc-eks-cluster-prod-use1n003p1-01 |
| 561004006 | 561004 | 122 | 561004006 | 3 | 120 | reserved | 1 | 1 | -1 | 1 | 2 | false | 5.0.816.44.V49 | mv-ndc-eks-cluster-prod-use2n002p1-01 |

# Step-by-Step Reasoning Process

## 1. Identify the Primary Focus of Your Query
- Are you asking about **antenna configurations** or **radio units** (e.g., tilt settings in `tilt-value`, antenna models in `antenna-model-number`, or sector assignments in `sector-id`)?  
  → Choose the **RET State Table (`mcms_cm_ret_state_12hr`)**.  
- Are you asking about **CUCP operational details** or **cell configurations** (e.g., CUCP state in `operational_state`, F1 interface mappings in `f1-interface-id`, or frequency bands in `frequency-band`)?  
  → Choose the **CUCP Topology State Table (`mcms_cm_topology_state_cucp_12hr`)**.  
- Are you asking about **CUUP operational status** or **throughput** (e.g., CUUP state in `operational_state`, throughput in `throughput`)?  
  → Choose the **CUUP Topology State Table (`mcms_cm_topology_state_cuup_12hr`)**.  
- Are you asking about **DU state** or **cell configurations** (e.g., DU status in `operational_state`, ARFCN in `nr-arfcn-dl`)?  
  → Choose the **DU Topology State Table (`mcms_cm_topology_state_du_12hr`)**.  
- Are you asking about **RRU status** or **site connectivity** (e.g., RRU state in `operational_state`, eCPRI status in `ecpri_link_status`, or site details in `site-id`)?  
  → Choose the **RRU Topology State Table (`mcms_cm_topology_state_rru_12hr`)**.
- Are you asking about **configuration parameters** like **maxAllowedScells**, **slotAggrBasePathLossInDb**, or **sctpNoDelay**?  
  → Choose the **Mavenir RAN Configuration Table (`mcms_cm_config_combined_12hr`)**.
  
## 2. Look for Specific Keywords or Terms in Your Query
- **RET State Table**: Keywords like "antenna," "tilt," "sector," "frequency band," "serial number," "bearing," or "installation date."  
- **CUCP Topology State Table**: Keywords like "CUCP," "cell identity," "F1 interface," "operational state," "alarms," or "frequency band."  
- **CUUP Topology State Table**: Keywords like "CUUP," "throughput," "operational state," or "alarms."  
- **DU Topology State Table**: Keywords like "DU," "cell identity," "ARFCN," "operational state," or "F1-C interface."  
- **RRU Topology State Table**: Keywords like "RRU," "site," "eCPRI," "operational state," or "alarms."
- **Mavenir Combined Configuration Table**: Keywords like "maxAllowedScells," "slotAggrBasePathLossInDb," "sctpNoDelay," "GPL," "configuration," or "inconsistencies."

## 3. Consider the Type of Information Requested
- **Antenna properties** or **radio unit details** (e.g., tilt angle from `tilt-value`, antenna bearing from `antenna-bearing`, or sector from `sector-id`)?  
  → Use the **RET State Table** (e.g., rows show `tilt-value` as `5.0` or `7.5`).  
- **CUCP operational status** or **cell configurations** (e.g., operational state from `operational_state`, F1 interface from `f1-interface-id`)?  
  → Use the **CUCP Topology State Table** (e.g., rows show `operational_state` as `enabled` or `degraded`).  
- **CUUP operational status** or **throughput** (e.g., throughput from `throughput`, alarms from `alarm_count`)?  
  → Use the **CUUP Topology State Table** (e.g., rows show `throughput` as `500.0` or `450.0`).  
- **DU operational state** or **cell configurations** (e.g., ARFCN from `nr-arfcn-dl`, state from `operational_state`)?  
  → Use the **DU Topology State Table** (e.g., rows show `nr-arfcn-dl` as `431500` or `145000`).  
- **RRU status** or **site connectivity** (e.g., eCPRI status from `ecpri_link_status`, site from `site-id`)?  
  → Use the **RRU Topology State Table** (e.g., rows show `site-id` as `CVCLE00435A` or `KCMCI00032B`).

## 4. Evaluate the Context of Your Query
- If your query involves a **specific site or sector** and focuses on **antenna settings** (e.g., "tilt at site KCMCI00032B" involving `tilt-value`), the **RET State Table** provides detailed antenna data (e.g., columns like `tilt-value`, `sector-id`).  
- If your query involves **CUCP network status** or **cell configurations** (e.g., "cells at site NYNYC00123A" involving `cell-identity`), the **CUCP Topology State Table** is more appropriate (e.g., columns like `operational_state`, `cell-identity`).  
- If your query involves **CUUP performance** (e.g., "throughput for CUUP JKRLA627035001" involving `throughput`), the **CUUP Topology State Table** is the best fit (e.g., columns like `throughput`, `operational_state`).  
- If your query involves **DU operations** or **cell settings** (e.g., "ARFCN at site CVCLE00435A" involving `nr-arfcn-dl`), the **DU Topology State Table** is the best choice (e.g., columns like `nr-arfcn-dl`, `du-name`).  
- If your query involves **RRU status** or **site connectivity** (e.g., "RRU status at site STSTL00114A" involving `operational_state`), the **RRU Topology State Table** is the best choice (e.g., columns like `ecpri_link_status`, `site-id`).

## 5. If Unsure, Consider the Intent of Your Query
- Troubleshooting **antenna issues** or optimizing **antenna settings** (e.g., adjusting `tilt-value` or verifying `antenna-model-number`)?  
  → Select the **RET State Table** (e.g., columns like `tilt-value`, `antenna-model-number`).  
- Analyzing **CUCP network status** or **cell performance** (e.g., checking `operational_state` or `f1-interface-id`)?  
  → Select the **CUCP Topology State Table** (e.g., columns like `operational_state`, `cell-identity`).  
- Investigating **CUUP performance** (e.g., analyzing `throughput` or `alarm_count`)?  
  → Select the **CUUP Topology State Table** (e.g., columns like `throughput`, `alarm_severity`).  
- Investigating **DU status** or **cell configurations** (e.g., verifying `nr-arfcn-dl` or `operational_state`)?  
  → Select the **DU Topology State Table** (e.g., columns like `du-name`, `nr-arfcn-dl`).  
- Investigating **RRU status** or **site connectivity** (e.g., checking `ecpri_link_status` or `site-id`)?  
  → Select the **RRU Topology State Table** (e.g., columns like `operational_state`, `site-id`).

# Example Usage

## Example 1
**Query**: "What is the current tilt of the antenna at site KCMCI00032B?"  
- **Step 1**: Focus is on antenna configurations (tilt).  
- **Step 2**: Keywords "tilt" and "antenna" align with `tilt-value` column.  
- **Step 3**: Requests antenna properties (e.g., `tilt-value`, `ru-label`).  
- **Step 4**: Context is site-specific antenna settings.  
- **Step 5**: Intent is to retrieve antenna settings.  
**Conclusion**: Use the **RET State Table (`mcms_cm_ret_state_12hr`)** (e.g., columns like `tilt-value`, `ru-label`).  

## Example 2
**Query**: "What is the operational state of CUCP with name JKRLA627035000?"  
- **Step 1**: Focus is on CUCP operational status.  
- **Step 2**: Keywords "CUCP" and "operational state" align with `operational_state` column.  
- **Step 3**: Requests CUCP status data (e.g., `operational_state`, `alarm_count`).  
- **Step 4**: Context is CUCP-specific status.  
- **Step 5**: Intent is to analyze CUCP performance.  
**Conclusion**: Use the **CUCP Topology State Table (`mcms_cm_topology_state_cucp_12hr`)** (e.g., columns like `operational_state`, `cucp-name`).  

## Example 3
**Query**: "What is the throughput for CUUP at site NYNYC00123B?"  
- **Step 1**: Focus is on CUUP performance (throughput).  
- **Step 2**: Keywords "throughput" and "CUUP" align with `throughput` column.  
- **Step 3**: Requests CUUP performance data (e.g., `throughput`, `operational_state`).  
- **Step 4**: Context is CUUP-specific metrics.  
- **Step 5**: Intent is to investigate CUUP performance.  
**Conclusion**: Use the **CUUP Topology State Table (`mcms_cm_topology_state_cuup_12hr`)** (e.g., columns like `throughput`, `cuup-name`).  

## Example 4
**Query**: "What is the ARFCN for cells at site CVCLE00435A?"  
- **Step 1**: Focus is on DU cell configurations (ARFCN).  
- **Step 2**: Keywords "ARFCN" and "cell" align with `nr-arfcn-dl` column.  
- **Step 3**: Requests DU cell configuration data (e.g., `nr-arfcn-dl`, `cell-identity`).  
- **Step 4**: Context is site-specific DU settings.  
- **Step 5**: Intent is to analyze DU cell configurations.  
**Conclusion**: Use the **DU Topology State Table (`mcms_cm_topology_state_du_12hr`)** (e.g., columns like `nr-arfcn-dl`, `du-name`).  

## Example 5
**Query**: "Which RRUs at site STSTL00114A have a degraded state?"  
- **Step 1**: Focus is on RRU operational status.  
- **Step 2**: Keywords "RRU" and "degraded state" align with `operational_state` column.  
- **Step 3**: Requests RRU status data (e.g., `operational_state`, `site-id`).  
- **Step 4**: Context is site-specific RRU status.  
- **Step 5**: Intent is to investigate RRU connectivity.  
**Conclusion**: Use the **RRU Topology State Table (`mcms_cm_topology_state_rru_12hr`)** (e.g., columns like `operational_state`, `site-id`).  

## Example 6
**Query**: "For CUCPID: 551001000, what is the value for maxAllowedScells parameter at the CUCP level?"  
- **Step 1**: Focus is on configuration parameters (maxAllowedScells).  
- **Step 2**: Keywords "maxAllowedScells" and "CUCPID" align with configuration parameters.  
- **Step 3**: Requests configuration data (e.g., `maxallowedscells`, `cucp_id`).  
- **Step 4**: Context is CUCP-specific configuration.  
- **Step 5**: Intent is to analyze configuration settings.  
**Conclusion**: Use the **Mavenir RAN Configuration Table (`mcms_cm_config_combined_12hr`)** (e.g., columns like `maxallowedscells`, `cucp_id`).

## Final Response
**Final Response** :Always provide only one single table name in final response without any irrelevant information. It must one of the table name defined above.

By following this structured CoT reasoning process, you can confidently select the appropriate table for your query.
"""