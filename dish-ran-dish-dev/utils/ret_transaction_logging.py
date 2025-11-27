import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
import json
from datetime import datetime, date
import inspect
from decimal import Decimal
import utils.postgres_util.dbutil as db
from utils import constants as CONST
import json
import logging
import uuid
from datetime import datetime
from sqlalchemy import text


# Set up logging with filename and method name
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

# Define a batch size
BATCH_SIZE = 100  # Adjust this as needed

async def log_ret_transaction(ret_transactions_list: list, vendor: str,new_tilt: str, user_id, transaction_id):
    """
    Log a RET transaction based on the vendor for each transaction in the ret_transactions_list.
    Uses batch insert for efficiency and skips failed inserts without rolling back the whole operation.
    """
    async with db.get_session() as session:
        try:
            response = "fail"
            # Prepare the data to be inserted
            transaction_data_list = []  # List to hold transaction data for batch insert

            for transaction in ret_transactions_list:
                logger.info("Processing transaction: %s", transaction)

                # Prepare data for insertion based on the vendor
                transaction_data = {
                    "transaction_id": transaction_id,  # Generate a unique transaction ID
                    "vendor": vendor,
                    "table_type": "RET",
                    "status": "PENDING",
                    "cell_id": transaction.get("cellname"),
                    "created_at":  datetime.now(),
                    "updated_at": None,
                    "created_by": user_id,  # Change as needed
                    "updated_by": None,
                    "is_active": True,
                    "reason": None
                }

                if vendor.lower() == "samsung":
                    # Add fields specific to Vendor 2
                    transaction_data.update({
                        "usmip": transaction.get("usmip"),
                        "ruid": transaction.get("ruid"),
                        "duid": transaction.get("duid"),
                        "aldid": transaction.get("aldid"),
                        "antennaid": transaction.get("antennaid"),
                        "new_tilt": new_tilt,
                        "current_tilt": transaction.get("tilt"),
                        # Ensure Mavenir-specific fields exist but are None
                        "ip": None,
                        "port": None,
                        "hdlc_address": None,
                        "antenna_unit": None,

                    })
                elif vendor.lower() == "mavenir":
                    # Add fields specific to other vendors
                    transaction_data.update({
                        "ruid": transaction.get("ruid"),
                        "ip": transaction.get("ip"),
                        "port": transaction.get("port"),
                        "hdlc_address": transaction.get("hdlc_address"),
                        "antenna_unit": transaction.get("antenna_unit"),
                        "new_tilt": new_tilt,
                        "current_tilt": transaction.get("tilt"),
                        # Ensure Samsung-specific fields exist but are None
                        "usmip": None,
                        "duid": None,
                        "aldid": None,
                        "antennaid": None,
                    })

                # Add the transaction data to the list
                transaction_data_list.append(transaction_data)

            # Break transaction data list into smaller batches
            for i in range(0, len(transaction_data_list), BATCH_SIZE):
                batch = transaction_data_list[i:i + BATCH_SIZE]

                # Perform batch insert
                insert_query = text("""
                INSERT INTO ran.ret_transactions (
                    transaction_id, vendor,cell_id, ruid, ip, port, hdlc_address,
                    usmip, duid, aldid, antennaid,antenna_unit, current_tilt, new_tilt, table_type, status, reason,
                    created_at, updated_at,
                    created_by, updated_by, is_active
                ) VALUES (
                    :transaction_id, :vendor, :cell_id, :ruid, :ip, :port, :hdlc_address,
                    :usmip, :duid, :aldid, :antennaid, :antenna_unit, :current_tilt, :new_tilt, :table_type, :status,:reason,
                     :created_at, :updated_at,
                    :created_by, :updated_by, :is_active
                )
                """)

                try:
                    # Insert in batches
                    await session.execute(insert_query, batch)
                    await session.commit()

                    logger.info("Successfully logged %d transactions in batch", len(batch))
                    response = "success"
                except Exception as e:
                    logger.error("Error occurred during batch insert: %s", e)
                    await session.rollback()

                    # Handle failure gracefully by logging the failed transactions in the batch
                    for failed_transaction in batch:
                        logger.error("Failed to insert transaction: %s", failed_transaction)

            return response

        except Exception as e:
            logger.error("Error occurred while processing RET transactions: %s", e)
            await session.rollback()
            raise
