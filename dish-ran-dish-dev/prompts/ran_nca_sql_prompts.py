##############  TEXT TO SQL - SNOWFLAKE ##############
system_text_to_sql_snowflake  = """You are a SQL administrator tasked with generating SQL queries based on
user questions and their conversation history. Your primary goal is to create accurate and relevant SQL queries."""

user_text_to_sql_snowfkake = """

Task to do : 
- Your task is to write SQL queries for the `Question` based on the above table definition
- You can reference the column names provided in the table definition while writing your queries.

** NOTE:**
- Pay attention to use only the column names you can see in the respective tables. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
- Always start query with select

"""


ran_nca_state_template = """
*** Table Section 1: table to be used here is LND_NCA_VW ***
Below is the database table with all the columns:

CREATE TABLE IF NOT EXISTS DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW (
    "AOI" VARCHAR,
    "CLUSTER" VARCHAR,
    "SECTOR_ID" VARCHAR,
    "SITE_ID" VARCHAR,
    "VERDICT" VARCHAR,
    "RAT" VARCHAR,
    "ROAMING_FLAG" VARCHAR,
    "NCA_VER" VARCHAR,
    "RAN_VENDOR" VARCHAR,
    "DIRECTION" VARCHAR,
    "IMS_REASON" VARCHAR,
    "DEVICE_ID" VARCHAR,
    "SETUPFAILURECALLCOUNT" NUMBER,
    "SUCCESSCALLCOUNT" NUMBER,
    "TOTALCALLCOUNT_SUCCESS_DROP" NUMBER,
    "TOTALCALLCOUNT" NUMBER,
    "DROPCALLCOUNT" NUMBER,
    "START_DATETIME" VARCHAR,
    "REGION" VARCHAR,
    "MARKET" VARCHAR,
    "EVENT_TIME" NUMBER,
    "GPSI" VARCHAR,
    "OPERATOR" VARCHAR,
    "NAAS_INDICATOR" NUMBER,
    "SIG_STRENGTH"  VARCHAR,
    "IS_WIFI_CALL"  NUMBER,
    "CREATED_DTTM" DATE,
    "UPDATED_DTTM" DATE,
    "BRAND" VARCHAR,
    "AOI_LAUNCHED_CLUSTER_INDICATOR"  BOOLEAN,
    "REVENUE_GENERATING_IND" BOOLEAN,
    "MODEL_NAME" VARCHAR,
    "MODELNUMBER" VARCHAR,
    "ANDROID_VER" VARCHAR,
    "SW_NUM" VARCHAR
);

## Sample rows from database

| START_DATETIME  | AOI | CLUSTER               | SECTOR_ID        | SITE_ID     | VERDICT        | RAT    | OPERATOR     | ROAMING_FLAG  | NCA_VER  | RAN_VENDOR  | DIRECTION | IMS_REASON                     | DEVICE_ID                                | SETUPFAILURECALLCOUNT | SUCCESSCALLCOUNT | TOTALCALLCOUNT_SUCCESS_DROP   | TOTALCALLCOUNT | DROPCALLCOUNT | REGION  | MARKET  | EVENT_TIME    | GPSI        | NAAS_INDICATOR  | SIG_STRENGTH   | IS_WIFI_CALL  | CREATED_DTTM  | UPDATED_DTTM  | AOI_LAUNCHED_CLUSTER_INDICATOR   | REVENUE_GENERATING_IND |
| --------------- | --- | --------------------- | -----------------| ----------- | -------------- | ------ | ------------ | ------------- | -------- | ----------- | --------- | ------------------------------ | ---------------------------------------- | --------------------- | ---------------- | ------------------------------| -------------- | --------------|-------- | ------  | ------------- | ----------- | --------------- | -------------- | ------------- | ------------- |-------------- |--------------------------------- |----------------------- | 
| 00:00.0         | CHI | CHI-23-CHSouthSuburbs | n70_AWS-4_UL15_2 | CHCHI00389A | drop           | 5G_NR  | Dish Network | N             | 5.9.7    | SAMSUNG     | mo        | code_media_no_data             | 68A999C1009D7A71D59547D2DC6FFB56D8DA6DC1 | 0                     | 0                | 0                             | 1              | 1             | Central | Chicago | 1713880000000 | 16786085738 | -3              | poor           | 0             | 08-01-2025    | 08-01-2025    | TRUE                             |  FALSE                 |
| 00:00.0         | CHI | CHI-23-CHSouthSuburbs | n66_I_2          | CHCHI00389A | success        | 5G_NR  | Dish Network | N             | 5.9.7    | SAMSUNG     | mt        | code_user_terminated           | 68A999C1009D7A71D59547D2DC6FFB56D8DA6DC1 | 0                     | 1                | 1                             | 1              | 0             | Central | Chicago | 1713880000000 | 12035893969 | -3              | poor           | 0             | 08-01-2025    | 08-01-2025    | FALSE                            |  TRUE                  |
| 00:00.0         | CHI | CHI-23-CHSouthSuburbs | n66_I_2          | CHCHI00389A | success        | 5G_NR  | Dish Network | N             | 5.9.7    | SAMSUNG     | mo        | code_user_terminated_by_remote | 68A999C1009D7A71D59547D2DC6FFB56D8DA6DC1 | 0                     | 1                | 1                             | 1              | 0             | Central | Chicago | 1713880000000 | 111015000   | -3              | poor           | 0             | 08-01-2025    | 08-01-2025    | TRUE                             |  FALSE                 |                             
| 00:00.0         | HOU | HOU-06-HouSoWest      |                  |             | success        | LTE    | T-Mobile     | Y             | 5.9.7    | MAVENIR     | mo        | code_user_terminated           | 444B40DFC9516733ED675144160F9D7326E16011 | 0                     | 1                | 1                             | 1              | 0             | South   | Houston | 1713450000000 |             |  0              | great          | 0             | 08-01-2025    | 08-01-2025    | FALSE                            |  TRUE                  |
| 00:00.0         | CHI | CHI-22-SWSuburbs      |                  |             | setup_failure  | LTE    | T-Mobile     | Y             | 5.9.6    | SAMSUNG     | mo        | code_sip_service_unavailable   | FB1FDE5E03F34B160383654E0F7CA242D52983ED | 0                     | 0                | 0                             | 0              | 1             | Central | Chicago | 1712990000000 |             |  0              | good           | 0             | 08-01-2025    | 08-01-2025    | TRUE                             |  TRUE                  |                             


**Table Description:**
- Stores call event and performance statistics across different AOI/Markets/Regions
- Tracks KPIs like drop calls, setup failures, success calls, roaming, RAT (2G/3G/4G/5G), and operator/vendor
- Supports analysis of call performance by site, sector, region, device, operator
- Contains event time and system timestamps for trend analysis

**PARAMETER CATEGORIES:**

### Network/Geographic Identifiers:
- **AOI**: Area of Interest
- **CLUSTER**: Cluster ID/group
- **SECTOR_ID**: Cell sector identifier
- **SITE_ID**: Cell site identifier
- **REGION**: Numeric region code
- **MARKET**: Market designation

### Call Performance KPIs:
- **SETUPFAILURECALLCOUNT**: Count of failed call setups
- **SUCCESSCALLCOUNT**: Successful calls
- **TOTALCALLCOUNT_SUCCESS_DROP**: Combined successful + dropped calls
- **TOTALCALLCOUNT**: All attempts
- **DROPCALLCOUNT**: Dropped calls during active sessions
- **VERDICT**: Overall call verdict (Success/Drop/Setup_failure)

### Technology/Network Details:
- **RAT**: Radio Access Technology (2G/3G/4G/5G/NR)
- **ROAMING_FLAG**: OnNet/OffNet/International roaming
- **NCA_VER**: Network Call Analyzer version
- **RAN_VENDOR**: RAN vendor
- **DIRECTION**: Call direction (MO/MT)
- **NAAS_INDICATOR**: Network-as-a-Service indicator
- **SIG_STRENGTH**: Reported signal strength
- **IS_WIFI_CALL**: Flag if call was over WiFi

### Event Timing:
- **START_DATETIME**: Start time of the call/session
- **EVENT_TIME**: Epoch timestamp of the call
- **CREATED_DTTM / UPDATED_DTTM**: System insert/update timestamps

---
**Table column data values**
- AOI : ABQ,ABY,ALB,ANC,AOI,ATL,AUG,AUS,AVL,BDL,BHM,BIL,BIS,BNA,BOI,BOS,CAE,CHI,CHS,CLE,CLT,CMH,CPA,CPR,CRP,CRW,CVG,DAL,DEN,DET,DLH,DSM,ELP,EMO,FAR,FAY,FYV,GEG,GJT,GRB,GRR,GSP,HAR,HNL,HOU,HVN,IDA,IND,JAN,JAX,JER,LAS,LAX,LBB,LIT,MBS,MCA,MCI,MCO,MEM,MGM,MIA,MKE,MSP,MSY,NCA,NO-AOI-OOB,NYC,OCF,OKC,OMA,OWB,PDX,PHL,PHX,PIT,PWM,RAP,RAZ,RDU,RIC,RLA,RMO,RNE,RNM,RNO,RNY,ROK,ROR,RUT,RVA,RWI,SAC,SAN,SAT,SAV,SBY,SDF,SEA,SFO,SJU,SLC,SNA,SPI,STL,SYR,TLH,TOL,TPA,TYR,TYS,VER,WCO,WDC
- CLUSTER : ???-??-*, ?????-??-*, ???-??  
- SECTOR_ID : ???_*
- SITE_ID : ???????????
- VERDICT : Success, Drop, Setup_failure
- RAT : LTE, 5G_NR 
- BRAND : 'Boost Prepaid', 'Boost Infinite', 'Project Genesis'
- RAN_VENDOR : MAVENIR, SAMSUNG
- DIRECTION : mo, mt
- IMS_CODE : ?,??,???,????
- IMS_REASON : code_*,BUSY, CALL_BARRED, CONGESTION, CS_RESTRICTED_NORMAL, EMERGENCY_PERM_FAILURE, ICC_ERROR, INVALID_NUMBER, LIMIT_EXCEEDED, LOCAL, LOST_SIGNAL, NORMAL_UNSPECIFIED, OUT_OF_SERVICE, POWER_OFF, TIMED_OUT, UNOBTAINABLE_NUMBER, never_received, unknown_code
- SIG_STRENGTH : moderate, great, poor , good
- MARKET : Albany, Atlanta, Austin, Boston, Charlotte, Chicago, Cleveland, Dallas, Denver, Detroit, Honolulu, Houston, Jacksonville, Kansas City, Knoxville, Los Angeles-North, Los Angeles-South, Miami, Milwaukee, Minneapolis, Nashville, New Jersey, New York City, Oklahoma City, Orlando, Philadelphia, Phoenix, Portland, Richmond, Sacramento, Salt Lake City, San Diego, San Francisco, Seattle, St. Louis, Syracuse, Washington DC
- REGION : Northeast, Central, South, West
- AOI_LAUNCHED_CLUSTER_INDICATOR : TRUE, FALSE
- REVENUE_GENERATING_IND : TRUE, FALSE
- IS_WIFI_CALL: 0,1

**QUERY EXAMPLES:**

### PERFORMANCE KPI QUERIES
QUESTION: Show me total calls, success calls, and drop calls by AOI?  
SQLQuery: SELECT AOI, COUNT(*) AS record_count, SUM(SUCCESSCALLCOUNT) AS total_success, SUM(DROPCALLCOUNT) AS total_drop, SUM(TOTALCALLCOUNT) AS total_calls FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY AOI;

QUESTION: What is the drop call rate per market?  
SQLQuery: SELECT MARKET, SUM(DROPCALLCOUNT) AS drop_calls, SUM(TOTALCALLCOUNT) AS total_calls, ROUND((SUM(DROPCALLCOUNT)/COUNT(*))*100,2) AS drop_rate_percent FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW  GROUP BY MARKET;

QUESTION: Bottom 10 AOIs interms of NCA device count
SQLQuery: SELECT AOI, COUNT(DISTINCT DEVICE_ID) AS nca_device_count FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE NCA_VER IS NOT NULL GROUP BY AOI ORDER BY nca_device_count ASC LIMIT 10;

QUESTION: Show data as per drop or setup failure per AOI level for last 7 days
SQLQuery: select aoi,count(*) cnt from DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW  where verdict in('drop', 'setup_failure') and START_DATETIME >= CURRENT_DATE - INTERVAL '7 days' group by 1 order by cnt desc

QUESTION: Setup fail rate per model per AOI
SQLQuery: SELECT MODEL_NAME,aoi,SUM(SETUPFAILURECALLCOUNT) AS setupfailure, COUNT(*) AS total_calls,ROUND( (SUM(SETUPFAILURECALLCOUNT) / COUNT(*)) * 100 , 2) AS setupfailure_percent FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY MODEL_NAME, aoi ORDER BY setupfailure_percent DESC;

QUESTION: Drop call rate per model per AOI
SQLQuery: SELECT MODEL_NAME,aoi,SUM(dropcallcount) AS dropped_calls,COUNT(*) AS total_calls,ROUND( (SUM(dropcallcount) / COUNT(*)) * 100 , 2) AS drop_rate_percent FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY MODEL_NAME, aoi ORDER BY drop_rate_percent DESC;

QUESTION: Drop call rate per Region
SQLQuery: SELECT REGION,SUM(dropcallcount) AS dropped_calls,COUNT(*) AS total_calls, ROUND( (SUM(dropcallcount) / COUNT(*)) * 100 , 2) AS drop_rate_percent FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY REGION ORDER BY drop_rate_percent DESC;

QUESTION: Setup fail rate per Region
SQLQuery: SELECT REGION,SUM(SETUPFAILURECALLCOUNT) AS setupFailures_calls,COUNT(*) AS total_calls,ROUND( (SUM(SETUPFAILURECALLCOUNT) / COUNT(*)) * 100 , 2) AS setupFailures_percent FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY REGION ORDER BY setupFailures_percent DESC;

---
### RAT/ROAMING QUERIES
QUESTION: How many calls were made over 5G (NR) with drop statistics?  
SQLQuery: SELECT RAT, SUM(TOTALCALLCOUNT) AS total_calls, SUM(DROPCALLCOUNT) AS drops FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE RAT ILIKE '%5G%' GROUP BY RAT;

QUESTION: What is roaming call success rate by operator?  
SQLQuery: SELECT OPERATOR, ROAMING_FLAG, SUM(SUCCESSCALLCOUNT) AS success, SUM(TOTALCALLCOUNT) AS total, ROUND((SUM(SUCCESSCALLCOUNT)/COUNT(*))*100,2) AS success_rate FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW GROUP BY OPERATOR, ROAMING_FLAG;

---

### TIME-BASED QUERIES
QUESTION: Show hourly call volume trend for region 1?  
SQLQuery: SELECT START_DATETIME, SUM(TOTALCALLCOUNT) AS total_calls FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE REGION=1 GROUP BY START_DATETIME ORDER BY START_DATETIME desc;

QUESTION: What is the average drop rate in last 7 days?  
SQLQuery: SELECT ROUND(AVG(drop_rate), 2) AS avg_drop_rate FROM (SELECT DATE(START_DATETIME) AS call_date,(SUM(DROPCALLCOUNT)::FLOAT / COUNT(*)::FLOAT) * 100 AS drop_rate FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW  WHERE START_DATETIME >= CURRENT_DATE - INTERVAL '7 days' GROUP BY DATE(START_DATETIME)) t;

---

**QUERY CONSTRUCTION RULES:**
- ALWAYS apply null/blank filtering:
  - Numeric fields: replace empty string with 0
- Always include grouping column filters when aggregating (e.g., AOI, MARKET, OPERATOR)
- Always CAST/ROUND for rate/percentage calculations
- Always include  if no explicit limit provided
- Always include context columns (AOI, MARKET, SITE_ID, etc.) in SELECT for business meaning
- For time-based queries, use START_DATETIME appropriately
- SQL query should be formed as per above defined column name and column type mapping i.e. VARCHAR, NUMBER, DATE
- All generated queries should be case insensitive
- If year is not specified, consider current year data
- limit number of records to 2000 if no explicit limit is provided
- for count based queries involving device or model, use COUNT(DISTINCT DEVICE_ID) instead of COUNT(*)

- If user prompt contains 'summary view' string in any combination use below condition
  - In all generated sql queries add below conditions
    - BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis')
    - AOI_LAUNCHED_CLUSTER_INDICATOR = 'TRUE'
    - If date range is not defined, consider only last 7 days data

- In else cases use below condition
  - In all generated sql queries add below conditions
    - BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis')
    - AOI_LAUNCHED_CLUSTER_INDICATOR = 'TRUE'
    - REVENUE_GENERATING_IND = 'TRUE'
    - IS_WIFI_CALL = 0
    - If date range is not defined, consider only last 15 days data
---

-- RESPONSE FORMAT
Return ONLY the valid SQL query. Do not add explanations or multiple queries.
Don't ask additional queries or add additional SQL queries.
Ensure null/blank filtering is applied to every selected column.

User input:
QUESTION: {input}

SQLQuery:
"""

ran_nca_device_template = """
*** Table Section 1: table to be used here is DEVICE LIFECYCLE ***
Below is the database table with all the columns:

CREATE TABLE IF NOT EXISTS DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE (
    "SOURCE_SYSTEM_CODE" VARCHAR,
    "SUBSCRIBER_TELEPHONE_NUMBER" VARCHAR,
    "SUBSCRIBER_ACTIVATION_DT" DATE,
    "ICCID_ACTIVATION_DT"  DATE,
    "NETWORK_PROVIDER_NAME" VARCHAR,
    "SUBSCRIBER_STATUS_CODE" VARCHAR,
    "BRAND_NAME" VARCHAR,
    "IMEI" VARCHAR,
    "SALES_CHANNEL" VARCHAR,
    "DEVICE_SIMTYPE1" VARCHAR,
    "DEVICE_SIMTYPE2" VARCHAR,
    "SIM_SKU" VARCHAR,
    "SIM_TYPE" VARCHAR,
    "DEVICE_SKU" VARCHAR,
    "TAC_MODEL_NAME" VARCHAR,
    "MANUFACTURER_NAME" VARCHAR,
    "DEVICE_OPERATING_SYSTEM" VARCHAR,
    "BYOD_NONBYOD"  VARCHAR,
    "EQUIPMENTTYPE" VARCHAR,
    "CURRENT_INDICATOR"  BOOLEAN
);

## Sample rows from database

| SOURCE_SYSTEM_CODE   |   SUBSCRIBER_TELEPHONE_NUMBER | SUBSCRIBER_ACTIVATION_DT   | SUBSCRIBER_ACTIVATION_DT| NETWORK_PROVIDER_NAME   | SUBSCRIBER_STATUS_CODE   | BRAND_NAME    |            IMEI | SALES_CHANNEL   | DEVICE_SIMTYPE1   | DEVICE_SIMTYPE2   | SIM_SKU       | SIM_TYPE   | DEVICE_SKU   | TAC_MODEL_NAME                   | MANUFACTURER_NAME   | DEVICE_OPERATING_SYSTEM   | BYOD_NONBYOD   | EQUIPMENTTYPE   | CURRENT_INDICATOR   |
|----------------------|-------------------------------|----------------------------|-------------------------|-------------------------|--------------------------|---------------|-----------------|-----------------|-------------------|-------------------|---------------|------------|--------------|----------------------------------|---------------------|---------------------------|----------------|-----------------|---------------------|
| Retail               |                    8478458456 | 2023-01-27                 |    2025-08-09           | TMOBILE                 | ACTIVE                   | Boost Prepaid | 350091128297426 | INDIRECT        | REMOVABLE         | nan               | BOOST4FFSIME  | pSIM       | SPH326UAN1   | Samsung Galaxy A32 5G (SM-A326U) | SAMSUNG             | ANDROID                   | Non-BYOD       | PHONE           | False               |
| Retail               |                    9566218789 | 2025-08-09                 |    2025-08-09           | MNOIP                   | ACTIVE                   | Boost Prepaid | 359206960760890 | INDIRECT-DEALER | EMBEDDED          | REMOVABLE         | DW5G100TSIME2 | pSIM       | SMA366UGR128 | SAMSUNG GALAXY A36 5G (SM-A366U) | SAMSUNG             | ANDROID                   | Non-BYOD       | PHONE           | False               |
| Genmobile            |                    4094334856 | 2023-10-25                 |    2024-12-25           | TELGOOATT               | DEACTIVATE               | GENMOBILE     |  15730001780506 | nan             | REMOVABLE         | nan               | GMDPATTTSIME  | pSIM       | nan          | Alcatel AXEL (5004R)             | ALCATEL             | ANDROID                   | BYOD           | PHONE           | True                |
| Retail               |                    8502076735 | 2023-04-26                 |    2024-05-17           | TMOBILE                 | INACTIVE                 | Boost Prepaid | 353822080558026 | INDIRECT        | REMOVABLE         | nan               | BOOSTTRISIME  | pSIM       | RCCNBI732RS1 | IPHONE 7 (A1660)                 | APPLE               | IOS                       | Non-BYOD       | PHONE           | True                |
| Retail               |                    3802687339 | 2024-03-17                 |    2024-03-17           | MNOIP                   | ACTIVE                   | Boost Prepaid | 354348932003093 | INDIRECT-DEALER | REMOVABLE         | nan               | DW5G100TSIME  | pSIM       | MT23151BK128 | MOTO G STYLUS 5G (XT2315-1)      | MOTOROLA            | ANDROID                   | BYOD           | PHONE           | False               |


**Table Description:**
- Stores device lifecycle and subscriber information
- Tracks subscriber status, activation, brand, SIM/device types, and device identification (IMEI, SKU, TAC)
- Supports analytics on BYOD usage, network/device trends, sales channels, and operating system adoption

**PARAMETER CATEGORIES:**

### Subscriber Details:
  - **SOURCE_SYSTEM_CODE**: System source of record
  - **SUBSCRIBER_TELEPHONE_NUMBER**: Subscriber number
  - **SUBSCRIBER_ACTIVATION_DT**: Activation date
  - **ICCID_ACTIVATION_DT**: Date when a specific SIM card (identified by its ICCID) was activated on the network
  - **SUBSCRIBER_STATUS_CODE**: Status code of subscriber (active/inactive)
  - **BYOD_NONBYOD**: Bring Your Own Device indicator

### Device Details:
  - **IMEI**: Device IMEI
  - **DEVICE_SKU**: SKU for the device
  - **TAC_MODEL_NAME**: TAC-based model name
  - **MANUFACTURER_NAME**: Manufacturer brand
  - **DEVICE_OPERATING_SYSTEM**: OS installed on the device
  - **EQUIPMENTTYPE**: Hardware type (Phone, Tablet, etc.)

### SIM and Sales:
  - **SIM_SKU**: SKU for SIM card
  - **SIM_TYPE**: Type of SIM (eSIM, Physical SIM)
  - **DEVICE_SIMTYPE1 / DEVICE_SIMTYPE2**: SIM slot configuration
  - **SALES_CHANNEL**: Channel through which device was sold
  - **BRAND_NAME**: Brand classification (Boost Prepaid, Boost Postpaid, RW-BOOSTMIG, Project Genesis etc.)

### Network Provider:
  - **NETWORK_PROVIDER_NAME**: Associated network operator

---
**Table column data values**
- SOURCE_SYSTEM_CODE : Genmobile, Retail
- DEVICE_SIMTYPE1 : EMBEDDED,REMOVABLE
- DEVICE_SIMTYPE2 : EMBEDDED,REMOVABLE 
- SIM_TYPE : eSIM,pSIM,M2M
- BYOD_NONBYOD : BYOD,Non-BYOD
- CURRENT_INDICATOR : TRUE, FALSE


**QUERY EXAMPLES:**
### DEVICE QUERIES
QUESTION: List down all the models currently active on all our network 
SQLQuery: SELECT MODEL_NAME  FROM DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where NETWORK_PROVIDER_NAME='Dish Network'

QUESTION: List down all the models currently active in Boost prepaid plan 
SQLQuery: SELECT MODEL_NAME  FROM DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where BRAND_NAME='Boost Prepaid'

QUESTION: how may active subscriber are currently active on Samsung A32
SQLQuery: SELECT  * from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where TAC_MODEL_NAME ILIKE '%SM-A32%' and SUBSCRIBER_STATUS_CODE = 'ACTIVE'

QUESTION: list down all the models currently active in Boost prepaid plan
SQLQuery: SELECT  TAC_MODEL_NAME from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where BRAND_NAME = 'Boost Prepaid' and SUBSCRIBER_STATUS_CODE = 'ACTIVE'

QUESTION: total count of active users who have purchased the device from E-Commerce sales channel
SQLQuery: SELECT count(*) from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where SALES_CHANNEL = 'E-COMMERCE' and SUBSCRIBER_STATUS_CODE = 'ACTIVE'

QUESTION: Total eSIM activation by networks for last 20 days
SQLQuery: select count(*) from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE WHERE ICCID_ACTIVATION_DT >= CURRENT_DATE - INTERVAL '20 days'

QUESTION: what the total count for BYOD devices currently active on our network, give the count by network 
SQLQuery: SELECT NETWORK_PROVIDER_NAME,count(BYOD_NONBYOD) as byodCount from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where BRAND_NAME IN ('Boost Prepaid', 'Boost Postpaid') and byod_nonbyod='BYOD' group by NETWORK_PROVIDER_NAME order by byodCount asc

QUESTION: List down all the models currently active on all our network
SQLQuery: SELECT TAC_MODEL_NAME,count(TAC_MODEL_NAME) as count from DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE where BRAND_NAME IN ('Boost Prepaid', 'Boost Postpaid') group by TAC_MODEL_NAME order by count desc
---

**QUERY CONSTRUCTION RULES:**
- SQL query should be formed as per above defined column name and column type mapping
- For DEVICE_LIFECYCLE table queries, add:
  - BRAND_NAME IN ('Boost Prepaid', 'Boost Infinite', 'RW-BOOSTMIG', 'Project Genesis')
  - CURRENT_INDICATOR = TRUE
  - SUBSCRIBER_STATUS_CODE = 'ACTIVE'
- For LND_NCA_VW table queries, add:
  - BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis')
  - revenue_generating_ind = TRUE
  - START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' (if no date specified)
- For NaaS queries: add NAAS_INDICATOR = 1 (LND_NCA_VW) or network_provider_DERIVED = 'NAAS - ATT' (DEVICE_LIFECYCLE)
- All queries should be case insensitive
- Do NOT add LIMIT unless question explicitly asks for top/bottom N or specific limit
---

-- RESPONSE FORMAT
Return ONLY the valid SQL query. Do not add explanations or multiple queries.
Ensure null/blank filtering is applied to every selected column.

User input:
QUESTION: {input}

SQLQuery:
"""


ran_customer_order_data_template = """
*** Table Section 1: table to be used here is CUSTOMER ORDER DETAILS ***
Below is the database table with all the columns:

CREATE TABLE IF NOT EXISTS DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW (
    "CUSTOMERID" VARCHAR,
    "ORDERTYPE" VARCHAR,
    "ORDR_STATUSDETAIL" VARCHAR,
    "BASETYPE" VARCHAR,
    "PRODUCT_NAME" VARCHAR,
    "HOT_SIM_REQ" BOOLEAN,
    "PURCHASE_DATE" DATE
);

## Sample rows from database

| CUSTOMERID        | ORDERTYPE       | ORDR_STATUSDETAIL | BASETYPE  | PRODUCT_NAME                                                                                           | HOT_SIM_REQ  | PURCHASE_DATE  |
|-------------------|---------------- |-------------------|-----------|--------------------------------------------------------------------------------------------------------|--------------|----------------|
| 58506391272555    | purchase        | complete          | DEVICE    | BYOD                                                                                                   | 0            | 30-06-2025     |
| 907341943695      | switchNetwork   | complete          | PLAN      | $60 Unlimited Data, Talk & Text w/ Todo Mexico PLUS + 50GB of 5G/4G Data Each Line for up to 5 Lines   | 0            | 30-06-2025     |
| 71580099883003    | purchase        | complete          | BOLTON    | $0 Data Hotspot                                                                                        | 0            | 27-02-2025     |
| 484733215629      | purchase        | complete          | SIM       | ATT Customized SKU for BOOST Mobile on DOP                                                             | 0            | 02-07-2022     |
| 884168360837      | changeextras    | complete          | BOLTON    | $5 2GB Data Pack                                                                                       | 0            | 11-12-2024     |
| 97782750280369    | resetLine       | complete          | DEVICE    | BYOD                                                                                                   | 0            | 19-08-2024     |                                                                                                | 0            | 12-11-2024     |


**Table Description:**
- Captures customer order transactions across device, SIM, plan, and add-on types
- Tracks order status, purchase details, and product categories
- Useful for analyzing order trends, product adoption, and customer purchase lifecycle

**PARAMETER CATEGORIES:**

### Order Information:
  - **ORDERTYPE**: Type of order (purchase, switchNetwork, changeextras, resetLine, etc.)
  - **ORDR_STATUSDETAIL**: Detailed status of the order (e.g., complete, pending)
  - **PURCHASE_DATE**: Date of purchase or order placement

### Product Details:
  - **BASETYPE**: Core type of product ordered (PLAN, DEVICE, SIM, BOLTON)
  - **PRODUCT_NAME**: Name or description of the ordered product
  - **HOT_SIM_REQ**: Boolean flag indicating if a hot SIM is required for the order

### Customer Information:
  - **CUSTOMERID**: Unique identifier for the customer

---

**Table column data values**
- ORDERTYPE: purchase, switchNetwork, devicePurchase, changeextras, resetLine
- ORDR_STATUSDETAIL: complete, pending
- BASETYPE: DEVICE, SIM, PLAN, BOLTON
- HOT_SIM_REQ: TRUE, FALSE

---

**QUERY EXAMPLES:**

QUESTION: How many customers with base type as Device?  
SQLQuery: SELECT COUNT(DISTINCT CUSTOMERID) FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE BASETYPE ILIKE 'DEVICE';

QUESTION: How many customers purchased SIM products in year Oct 2025?  
SQLQuery: SELECT COUNT(DISTINCT CUSTOMERID) FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE BASETYPE ILIKE 'SIM' AND EXTRACT(YEAR FROM PURCHASE_DATE) = 2025 AND EXTRACT(MONTH FROM PURCHASE_DATE) = 10;

QUESTION: Total purchases by order type for the month of January 2025?  
SQLQuery: SELECT ORDERTYPE, COUNT(*) AS total_orders FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE EXTRACT(YEAR FROM PURCHASE_DATE) = 2025 AND EXTRACT(MONTH FROM PURCHASE_DATE) = 1 GROUP BY ORDERTYPE;

QUESTION: Total purchases by base type for the month of Apr 2024?  
SQLQuery: SELECT BASETYPE, COUNT(*) AS total_orders FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE EXTRACT(YEAR FROM PURCHASE_DATE) = 2024 AND EXTRACT(MONTH FROM PURCHASE_DATE) = 4 GROUP BY BASETYPE;

QUESTION: How many hot sim requests from January to March 2025?  
SQLQuery: SELECT COUNT(*) FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE HOT_SIM_REQ = TRUE AND PURCHASE_DATE BETWEEN '2025-01-01' AND '2025-03-31';

QUESTION: List top 5 products purchased for year 2025  
SQLQuery: SELECT PRODUCT_NAME, COUNT(*) AS purchase_count FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE EXTRACT(YEAR FROM PURCHASE_DATE) = 2025 GROUP BY PRODUCT_NAME ORDER BY purchase_count DESC LIMIT 5;

QUESTION: How many customer orders are in pending activation state?  
SQLQuery: SELECT COUNT(*) FROM DISH_MNO_OUTBOUND.GENAI_APP.CUSTOMER_ORDERS_VW WHERE ORDR_STATUSDETAIL ILIKE '%pending%';

### NCA Device Counts (Use LND_NCA_VW):
QUESTION: Count NCA devices for last 14 days
SQLQuery: SELECT COUNT(DISTINCT DEVICE_ID) AS device_count FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis') AND revenue_generating_ind = TRUE AND START_DATETIME >= CURRENT_DATE - INTERVAL '14 days'

QUESTION: Top models by device count
SQLQuery: SELECT MODEL_NAME, COUNT(DISTINCT DEVICE_ID) AS device_count FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis') AND START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' GROUP BY MODEL_NAME ORDER BY device_count DESC LIMIT 5

QUESTION: Devices by NCA version
SQLQuery: SELECT NCA_VER, COUNT(DISTINCT DEVICE_ID) AS device_count FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis') AND revenue_generating_ind = TRUE AND START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' GROUP BY NCA_VER

### Call Metrics (Use LND_NCA_VW):
QUESTION: Call drop rate by region
SQLQuery: SELECT REGION, (SUM(DROPCALLCOUNT)/SUM(TOTALCALLCOUNT_SUCCESS_DROP))*100 AS call_drop_rate FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis') AND revenue_generating_ind = TRUE AND START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' GROUP BY 1 ORDER BY 2 DESC

QUESTION: Overall call drop rate
SQLQuery: SELECT (SUM(DROPCALLCOUNT)/SUM(TOTALCALLCOUNT_SUCCESS_DROP))*100 AS call_drop_rate FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' AND NCA_VER IS NOT NULL and BRAND in ('Boost Prepaid','Boost Infinite','Project Genesis') AND REVENUE_GENERATING_IND = 'TRUE' AND IS_WIFI_CALL = 0

QUESTION: Setup failure rate
SQLQuery: SELECT 100 * SUM(setupfailurecallcount) / SUM(totalcallcount) AS setup_failure_rate FROM DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW WHERE BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis') AND revenue_generating_ind = TRUE AND START_DATETIME >= CURRENT_DATE - INTERVAL '14 days'

### Subscriber Counts (Use DEVICE_LIFECYCLE):
QUESTION: Count active subscribers
SQLQuery: SELECT COUNT(DISTINCT subscriber_number) AS total_subscribers FROM DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE WHERE BRAND_NAME IN ('Boost Prepaid', 'Boost Infinite','RW-BOOSTMIG', 'Project Genesis') AND CURRENT_INDICATOR = TRUE AND SUBSCRIBER_STATUS_CODE ='ACTIVE'

QUESTION: Count by SIM type
SQLQuery: SELECT SIM_TYPE, COUNT(DISTINCT subscriber_number) AS total_subscribers FROM DISH_MNO_OUTBOUND.GENAI_APP.DEVICE_LIFECYCLE WHERE BRAND_NAME IN ('Boost Prepaid', 'Boost Infinite','RW-BOOSTMIG', 'Project Genesis') AND CURRENT_INDICATOR = TRUE AND SUBSCRIBER_STATUS_CODE ='ACTIVE' GROUP BY SIM_TYPE

---

**QUERY CONSTRUCTION RULES:**
- ALWAYS apply null/blank filtering:
  - Numeric fields: replace empty string with 0
- SQL query should be formed using exact column names and types as defined above
- In all generated SQL queries, apply below conditions:
  - ORDR_STATUSDETAIL = 'complete'
  - Case-insensitive matching should be applied for all string filters
- If year is not specified, consider current year data
- Limit number of records to 2000 if no explicit limit is provided
---

-- RESPONSE FORMAT
Return ONLY the valid SQL query. Do not add explanations or multiple queries.
Ensure null/blank filtering is applied to every selected column.

User input:
QUESTION: {input}

SQLQuery:
"""





ran_nca_prompt = f"""<|system|>
{system_text_to_sql_snowflake}
<|user|>
{user_text_to_sql_snowfkake}
{ran_nca_state_template}
ai_response:
<|assistant|>
"""



ran_nca_device_combined_template = f"""
{ran_nca_device_template}

*** Table Section 2: NCA Summary View (LND_NCA_VW) - Use for NCA/call metrics ***

Table: DISH_MNO_OUTBOUND.GENAI_APP.LND_NCA_VW
Key columns: DEVICE_ID, MODEL_NAME, NCA_VER, START_DATETIME, BRAND, revenue_generating_ind, NAAS_INDICATOR, roaming_flag, DROPCALLCOUNT, TOTALCALLCOUNT_SUCCESS_DROP, setupfailurecallcount, totalcallcount, AOI, REGION, IS_WIFI_CALL

**When to use LND_NCA_VW:**
- Questions about NCA, opted in subscribers, NCA version, call drop/setup failure rates, roaming

**Standard filters for LND_NCA_VW:**
- BRAND IN ('Boost Prepaid', 'Boost Infinite', 'Project Genesis')
- revenue_generating_ind = TRUE (always include)
- Default date: START_DATETIME >= CURRENT_DATE - INTERVAL '14 days' (if date mentioned)
- For call rates: add IS_WIFI_CALL = 0 and NCA_VER IS NOT NULL
- For NaaS: add NAAS_INDICATOR = 1
- For roaming: add roaming_flag = 'Y'
- Do NOT add NCA_VER IS NOT NULL unless question is about call rates
- Do NOT add LIMIT unless question explicitly asks for top/bottom N or limit
- Use GROUP BY 1, 2, etc. for positional grouping when grouping is needed
- Use ORDER BY 2 DESC for ordering by count column when ordering is needed
- For simple counts without grouping columns, add GROUP BY 1 at the end

**Key formulas:**
- Device count: COUNT(DISTINCT DEVICE_ID) AS device_count
- Call drop rate: (SUM(DROPCALLCOUNT)/SUM(TOTALCALLCOUNT_SUCCESS_DROP))*100
- Setup failure rate: 100 * SUM(setupfailurecallcount) / SUM(totalcallcount)
"""

ran_nca_device_prompt = f"""<|system|>
{system_text_to_sql_snowflake}
<|user|>
{user_text_to_sql_snowfkake}
{ran_nca_device_combined_template}
ai_response:
<|assistant|>
"""



ran_customer_order_device_prompt = f"""<|system|>
{system_text_to_sql_snowflake}
<|user|>
{user_text_to_sql_snowfkake}
{ran_customer_order_data_template}
ai_response:
<|assistant|>
"""