import os
from dotenv import load_dotenv
import boto3
import traceback

def test_athena_connectivity():
    """
    Self-contained script to test Athena connectivity and query execution.
    """
    print("--- Starting Athena Connectivity Test ---")
    load_dotenv()

    # --- Configuration ---
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")
    ATHENA_REGION = os.getenv("ATHENA_REGION")
    ATHENA_S3_OUTPUT_LOCATION = os.getenv("ATHENA_S3_OUTPUT_LOCATION")
    CATALOG_NAME = 'AwsDataCatalog'
    DATABASE_NAME = 'dl_silver_ran_mavenir_piiprod'
    QUERY = 'SELECT * FROM dl_silver_ran_mavenir_piiprod.mcms_cm_ret_state_12hr limit 10;'

    # --- Print Configuration for Debugging ---
    print(f"Using region: {ATHENA_REGION}")
    print(f"Using catalog: {CATALOG_NAME}")
    print(f"Using S3 output location: {ATHENA_S3_OUTPUT_LOCATION}")

    # --- Validate Environment Variables ---
    required_vars = {
        "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
        "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
        "AWS_SESSION_TOKEN": AWS_SESSION_TOKEN,
        "ATHENA_REGION": ATHENA_REGION,
        "ATHENA_S3_OUTPUT_LOCATION": ATHENA_S3_OUTPUT_LOCATION
    }
    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        print(f"\nERROR: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please ensure they are set in your .env file or environment.")
        return

    try:
        # --- Test 1: S3 Write Permissions ---
        print("\n--- [Test 1/3] Testing S3 Write Permissions ---")
        s3_client = boto3.client(
            's3',
            region_name=ATHENA_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN
        )
        bucket_name = ATHENA_S3_OUTPUT_LOCATION.split('/')[2]
        test_key = f'athena_test/connectivity-test-{os.urandom(4).hex()}.txt'
        print(f"Attempting to write a test file to s3://{bucket_name}/{test_key}...")
        s3_client.put_object(Bucket=bucket_name, Key=test_key, Body='test')
        print("S3 write permission test: SUCCEEDED.")
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("Cleaned up S3 test file.")

        # --- Test 2: Database Visibility ---
        print("\n--- [Test 2/3] Testing Database Visibility ---")
        athena_client = boto3.client(
            'athena',
            region_name=ATHENA_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            aws_session_token=AWS_SESSION_TOKEN
        )
        print(f"Listing databases in catalog '{CATALOG_NAME}'...")
        databases_response = athena_client.list_databases(CatalogName=CATALOG_NAME)
        database_list = [db['Name'] for db in databases_response.get('DatabaseList', [])]
        print(f"Found {len(database_list)} databases.")
        if DATABASE_NAME in database_list:
            print(f"Database visibility test: SUCCEEDED. Found '{DATABASE_NAME}'.")
        else:
            print(f"Database visibility test: FAILED. Could not find '{DATABASE_NAME}' in the list of databases.")
            print("Available databases:", database_list)
            return

        # --- Test 3: Table Listing Permissions ---
        print("\n--- [Test 3/4] Testing Table Listing Permissions (This test is expected to fail) ---")
        try:
            print(f"Attempting to list tables in database '{DATABASE_NAME}'...")
            tables_response = athena_client.list_table_metadata(CatalogName=CATALOG_NAME, DatabaseName=DATABASE_NAME)
            table_list = [tbl['Name'] for tbl in tables_response.get('TableMetadataList', [])]
            print(f"Table listing permission test: UNEXPECTEDLY SUCCEEDED. Found {len(table_list)} tables.")
            print("Visible tables:", table_list)
        except Exception as e:
            if "AccessDeniedException" in str(e) or "not authorized to perform: glue:GetTables" in str(e):
                print("Table listing permission test: FAILED AS EXPECTED.")
                print("Reason: The IAM role does not have 'glue:GetTables' permission, which is correct.")
            else:
                print(f"Table listing permission test: FAILED with an unexpected error: {e}")


        # --- Test 4: Athena Query Execution ---
        print("\n--- [Test 4/4] Testing Athena Query Execution ---")
        print(f"Running test query on Athena: {QUERY}")
        response = athena_client.start_query_execution(
            QueryString=QUERY,
            QueryExecutionContext={'Database': DATABASE_NAME},
            ResultConfiguration={'OutputLocation': ATHENA_S3_OUTPUT_LOCATION}
        )
        query_execution_id = response['QueryExecutionId']
        print(f"Query Execution ID: {query_execution_id}")

        while True:
            status = athena_client.get_query_execution(QueryExecutionId=query_execution_id)
            state = status['QueryExecution']['Status']['State']
            if state == 'SUCCEEDED':
                print("Athena query test: SUCCEEDED.")
                break
            elif state in ['FAILED', 'CANCELLED']:
                reason = status['QueryExecution']['Status'].get('StateChangeReason', 'No reason provided.')
                print(f"Athena query test: FAILED. Reason: {reason}")
                return
            else:
                print("Waiting for query to complete...")
                import time
                time.sleep(2)

        # Fetch and print results on success
        results = athena_client.get_query_results(QueryExecutionId=query_execution_id)
        rows = results['ResultSet']['Rows']
        if len(rows) > 1:
            headers = [col.get('VarCharValue', '') for col in rows[0]['Data']]
            print("\nQuery Results:")
            for row in rows[1:]:
                print({headers[i]: col.get('VarCharValue', '') for i, col in enumerate(row['Data'])})
        else:
            print("\nQuery succeeded but returned no rows.")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_athena_connectivity() 