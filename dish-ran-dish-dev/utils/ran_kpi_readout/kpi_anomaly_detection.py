# import json
# from pathlib import Path

import numpy as np
import pandas as pd
# import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from utils import constants as CONST
from utils.log_init import logger
# JSON_PATH = "ran-kpi-readout-14days-daily-freq.json"

# # ****************** Load JSON ****************** 

# def load_json_to_df(json_path: str) -> pd.DataFrame:
# 	JSON_PATH = json_path	
# 	obj = json.loads(Path(JSON_PATH).read_text(encoding="utf-8", errors="ignore"))	
# 	raw_df = pd.DataFrame(obj["data"])
# 	return raw_df


# ****************** Extracting Features ******************

def rename_and_prepare(raw_df: pd.DataFrame) -> pd.DataFrame:

	df = raw_df.rename(columns={'object': "aoi", '__time': "timestamp"}).copy()
	df["timestamp"] = pd.to_datetime(df["timestamp"])
	df = df.dropna(subset=["timestamp"]).sort_values(["aoi","timestamp"]).reset_index(drop=True)
	
	#  features
	df["year"]		  = df["timestamp"].dt.year
	df["month"]		  = df["timestamp"].dt.month
	df["dayofmonth"]		 = df["timestamp"].dt.day
	df["dayofweek"]	  = df["timestamp"].dt.dayofweek #M-0,Su-6
	df["weekday_name"]= df["timestamp"].dt.day_name() 
	df['is_weekend']  = (df.dayofweek >= 5).astype(int)
	df["hour"]		  = df["timestamp"].dt.hour
	return df
 
# ****************** Getting KPI Cols ******************


def get_kpi_cols(feature_df: pd.DataFrame) -> pd.DataFrame:		   
	non_kpi = {"aoi","timestamp","year","month","day","dayofweek","weekday_name","is_weekend","dayofmonth","hour"}
	numeric_cols = feature_df.select_dtypes(include=[np.number]).columns.tolist()
	kpi_cols = [nc for nc in numeric_cols if nc not in non_kpi]
	return kpi_cols
		
# ****************** Unpivoting ******************

def to_long_table(df: pd.DataFrame, kpi_cols: pd.DataFrame) -> pd.DataFrame:

	long_df = df.melt(id_vars=["aoi","timestamp","year","month","dayofmonth","dayofweek","weekday_name","is_weekend"], value_vars=kpi_cols,var_name="kpi_name", value_name="kpi_value").dropna(subset=["kpi_value"]) # unpivoting
	
	#  frequency label 
	long_df["freq"] = "Daily"
	
	# print("Long shape:", long_df.shape)
	# display(long_df.tail(13))
	return long_df

# ****************** Isolation Forest Model ******************

def run_iforest_per_group(g: pd.DataFrame, min_points=48, contamination=0.05) -> pd.DataFrame:
   
	g = g.sort_values("timestamp").copy()
	# X = g[["kpi_value"]].values
	X = g[["kpi_value","dayofmonth","dayofweek","is_weekend"]].values

	model = IsolationForest(n_estimators=200, contamination=contamination, random_state=42)
	model.fit(X)
	g["if_pred"] = model.predict(X)				   # -1 anomaly, 1 normal
	g["if_anomaly"] = (g["if_pred"] == -1)
	g["if_score"] = model.decision_function(X)
	return g

# ****************** 3-Days Mean Trend ******************

def add_daily_trends(g: pd.DataFrame) -> pd.DataFrame:
	g = g.sort_values("timestamp").copy()
	g["mean_3d"]  = g["kpi_value"].rolling(window=3).mean()
	return g

# ****************** Detecting Spike/Dip ******************

def add_spike_dip(df: pd.DataFrame) -> pd.DataFrame:
	g = df.copy()
	g["spike_dip"] = "normal"
	g.loc[(g["if_anomaly"]) & (g["kpi_value"] > g["mean_3d"]), "spike_dip"] = "spike"  # above trend
	g.loc[(g["if_anomaly"]) & (g["kpi_value"] < g["mean_3d"]), "spike_dip"] = "dip"	   # below trend
	return g

# ****************** Detecting upward/downward ******************

def detecting_upward_downward(df: pd.DataFrame) -> pd.DataFrame:
	g = df.sort_values(["aoi", "kpi_name", "timestamp"]).copy()

	# % change per (aoi, kpi)
	g["pct_change"] = g.groupby(["aoi", "kpi_name"])["kpi_value"].pct_change() * 100

	# Aggregate over full days
	summary = g.groupby(["aoi", "kpi_name"], as_index=False).agg(
		std_deviation=("kpi_value", "std"),		   
		mean_kpi=("kpi_value", "mean"),
		trend_variance=("pct_change", "mean")
	)
	summary["std_percent"] =summary["std_deviation"]/summary["mean_kpi"]

	# Trend indicator
	tol=0.1
	summary["trend_indicator"] = "Stable"
	summary.loc[summary["trend_variance"] > tol, "trend_indicator"] = "Upward"
	summary.loc[summary["trend_variance"] < -tol, "trend_indicator"] = "Downward"

	# variance 
	summary["trend_variance"] = summary["trend_variance"].round(1).astype(str) + "%"
	summary.loc[summary["trend_variance"] == "nan%", "trend_variance"] = None

	return summary

# ****************** Standardizing Output ******************
def build_final_output(spike_dip: pd.DataFrame, summary_14d: pd.DataFrame) -> dict:
	# Build anomaly data records
    data_records = []
    for ts, group in spike_dip.groupby(["aoi", "timestamp"]):
        record = {
            "object": ts[0],
            "__time": ts[1].strftime("%Y-%m-%d %H:%M:%S"),
        }
        anomalies = {}
        violations = []

        for _, row in group.iterrows():
            kpi = row["kpi_name"]
            value = row["kpi_value"]

            # Add KPI value
            record[kpi] = value

            # Anomaly flag
            if row["spike_dip"].lower() in ["spike", "dip"]:
                anomalies[kpi] = row["spike_dip"]

            # Threshold check
            if kpi in CONST.KPI_THRESHOLDS:
                try:
                    if CONST.KPI_THRESHOLDS[kpi](value) == False:  # apply lambda
                        violations.append(kpi)
                except Exception as e:
                    logger.error(f"Error checking threshold for {kpi}: {e}")

        record["anomaly"] = anomalies
        record["violations"] = violations
        data_records.append(record)

# ****************** Build trend summary dictionary ******************
    trend_summary = {}
    for _, row in summary_14d.iterrows():
        trend_summary[row["kpi_name"]] = {
            "std_deviation": round(float(row["std_deviation"]), 2),
            "trend_indicator": row["trend_indicator"],
            "trend_variance": row["trend_variance"],
            "std_percent": row["std_percent"],
        }

    final_output = {
        "data": data_records,
        "trend_indicator": trend_summary,
    }

    return final_output
	

# Main Function
def detect_anomalies(aoi_data):
	raw_df = pd.DataFrame(aoi_data)
	feature_df = rename_and_prepare(raw_df)
	kpi_cols =	 get_kpi_cols(feature_df) 
	long_df = to_long_table(feature_df,kpi_cols)
	if_df = (long_df.groupby(["aoi","kpi_name"], group_keys=False).apply(run_iforest_per_group, min_points=48, contamination=0.02).reset_index(drop=True))
	trend_df = (if_df.groupby(["aoi","kpi_name"], group_keys=False).apply(add_daily_trends).reset_index(drop=True))
	spike_dip = add_spike_dip(trend_df)
	upward_downward = detecting_upward_downward(spike_dip)
	final_output = build_final_output(spike_dip, upward_downward)
      
      
	return final_output
	
# if __name__ == "__main__":
# 	anomaly_json = main('ran-kpi-readout-14days-daily-freq.json')
# 	print(json.dumps(anomaly_json, indent=4))
# 	#anomaly_json = main('call_drops_AOI_DEN_hourly_aug.json')

	








