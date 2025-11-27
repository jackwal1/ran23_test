import os
import json
from dotenv import load_dotenv
from datetime import datetime
import psycopg2

import logging
from utils import constants as CONST

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")

try:
    pg_host = os.environ["POSTGRESS_URL"]
    pg_db = os.environ["POSTGRES_DB"]
    pg_user = os.environ["POSTGRESS_USERNAME"]
    pg_pass = os.environ["POSTGRESS_PASSWORD"]
    pg_port = os.environ["POSTGRES_PORT"]


except Exception as e:
    print(e)
    logger.info("Loading Environmment Variables from local .env file")

    load_dotenv()

    pg_host = os.environ["POSTGRESS_URL"]
    pg_db = os.environ["POSTGRES_DB"]
    pg_user = os.environ["POSTGRESS_USERNAME"]
    pg_pass = os.environ["POSTGRESS_PASSWORD"]
    pg_port = os.environ["POSTGRES_PORT"]


def postgres_get_kb_file(file_name):
    """
    Fetch the S3 URL for a given file name from the telco.doc_metadata table.

    Parameters:
    file_name (str): The name of the file to search for.

    Returns:
    str: The S3 URL if found, otherwise None.
    """
    try:
        with psycopg2.connect(
                host=pg_host, database=pg_db, user=pg_user, password=pg_pass, port=pg_port
        ) as conn:
            cursor = conn.cursor()
            # Construct the SQL query
            select_query = """SELECT s3_url
                              FROM telco.doc_metadata
                              WHERE file_name = %s
                              LIMIT 1;"""

            # Execute the query
            cursor.execute(select_query, (file_name,))

            # Fetch the result
            record = cursor.fetchone()

            # Check if a record was found and return the result
            if record is None:
                print(f"Record NOT found for file_name: {file_name}")
                return None

            response = record[0]
            logger.info(f"Record found: {response}")
            return response

    except Exception as e:
        # Handle any errors
        logger.error(f"Error during SELECT query: {e}")
        return None
