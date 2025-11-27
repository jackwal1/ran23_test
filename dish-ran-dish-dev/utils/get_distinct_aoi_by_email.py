import logging
from utils.snow_utils.snowdb_util import query_snow_db
import traceback
from utils.log_init import logger
import re


async def get_distinct_aoi_by_email(email: str) -> dict:
    """
    Retrieve distinct AOI values and associated engineer name from an email address.
    The name is searched in MARKET_MANAGER, RF_DESIGN_ENGINEER, RF_DESIGN_MANAGER, or RF_ENGINEER columns.
    Uses case-insensitive matching with exact word matching for individual name components.

    Args:
        email: Email address (e.g., angelo.ferrer@dish.com)

    Returns:
        Dictionary with distinct AOI values, engineer name, and status message
    """
    table_name = 'dish_mno_outbound.genai_app.n1_site_cells_vw'
    target_columns = ['RF_DESIGN_ENGINEER']

    if not email:
        logger.info("Empty email received.")
        return {"aoi": [], "engineer": "", "message": "Email cannot be empty."}

    # Extract name part from email (before '@')
    if '@' not in email:
        logger.info(f"Invalid email format: {email}")
        return {"aoi": [], "engineer": "", "message": "Invalid email format."}

    name_part = email.split('@')[0]

    # Clean the name part:
    # 1. Replace dots with spaces
    # 2. Remove any special characters except letters, numbers, and spaces
    cleaned_name = re.sub(r'[^a-zA-Z0-9\s]', '', name_part.replace('.', ' '))

    # Convert to lowercase for consistent matching
    cleaned_name = cleaned_name.lower()

    # Split into individual name components
    name_components = [comp for comp in cleaned_name.split() if comp]

    # If no valid components after cleaning, return error
    if not name_components:
        logger.info(f"No valid name components found in email: {email}")
        return {"aoi": [], "engineer": "", "message": "No valid name components found in email."}

    # Build conditions
    conditions = []

    # Condition 1: Full name match (exact phrase with word boundaries) - we'll keep this as is for now
    escaped_full_name = cleaned_name.replace("'", "''")
    # Create regex pattern with word boundaries
    full_name_pattern = r'\b' + re.escape(escaped_full_name) + r'\b'
    # Escape backslashes for SQL
    full_name_pattern = full_name_pattern.replace('\\', '\\\\')
    full_name_condition = ' OR '.join([f'REGEXP_LIKE(LOWER("{col}"), \'{full_name_pattern}\')' for col in target_columns])
    conditions.append(f"({full_name_condition})")

    # Condition 2: Individual name components with AND logic and exact word matching using LIKE
    if len(name_components) > 1:
        # For each column, create a condition that checks if ALL name components are present as whole words
        column_conditions = []
        for col in target_columns:
            component_conditions = []
            for component in name_components:
                escaped_component = component.replace("'", "''")
                # Create conditions for exact word match using LIKE
                # We'll check for:
                #   - component at the beginning: "component %"
                #   - component at the end: "% component"
                #   - component in the middle: "% component %"
                #   - exact match: "component"
                like_conditions = [
                    f'LOWER("{col}") LIKE \'{escaped_component} %\'',
                    f'LOWER("{col}") LIKE \'% {escaped_component} %\'',
                    f'LOWER("{col}") LIKE \'% {escaped_component}\'',
                    f'LOWER("{col}") = \'{escaped_component}\''
                ]
                component_condition = ' OR '.join(like_conditions)
                component_conditions.append(f"({component_condition})")
            # Combine component conditions with AND for the same column
            column_condition = ' AND '.join(component_conditions)
            column_conditions.append(f"({column_condition})")

        # Combine all column conditions with OR (any column can contain all name components)
        and_condition = ' OR '.join(column_conditions)
        conditions.append(f"({and_condition})")

    # Combine all conditions with OR
    where_clause = ' OR '.join(conditions)

    sql_query = f"""
        SELECT DISTINCT "AOI", "RF_DESIGN_ENGINEER" as "engineer"
        FROM {table_name}
        WHERE {where_clause}
        AND "AOI" IS NOT NULL
        AND "AOI" <> ''
        AND "RF_DESIGN_ENGINEER" IS NOT NULL
        AND "RF_DESIGN_ENGINEER" <> '';
    """

    logger.info(f"Generated SQL Query for email '{email}':\n{sql_query.strip()}")

    try:
        sql_result = await query_snow_db(sql_query)
        logger.info(f"SQL Result for email '{email}': {sql_result}")

        if sql_result:
            aoi_list = []
            engineer_name = ""

            # Process results to get unique AOIs and the first engineer name
            for row in sql_result:
                if row.get('aoi') and row['aoi'] not in aoi_list:
                    aoi_list.append(row['aoi'])
                if not engineer_name and row.get('engineer'):
                    engineer_name = row['engineer']

            message = f"Found {len(aoi_list)} distinct AOI(s) for email: {email}"
            return {"aoi": aoi_list, "engineer": engineer_name, "message": message}
        else:
            logger.info(f"No matching AOI or engineer found for email: {email}")
            return {"aoi": [], "engineer": "", "message": f"No matching AOI or engineer found for email: {email}"}

    except Exception as e:
        traceback.print_exc()
        logger.error(f"Exception while querying Snowflake for email '{email}': {str(e)}")
        return {"aoi": [], "engineer": "", "message": f"Error occurred while retrieving AOI data for email: {email}"}