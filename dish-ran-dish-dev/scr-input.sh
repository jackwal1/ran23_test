#!/bin/bash
#Call out breaking changes
BACKWARDS_COMPATIBLE=yes

#Application Name for GenAI-Platform
#TODO: This is a temporary APP_Name, need to replace it with correct one when REQ0896113 gets approved and fulfilled.
#APP_NAME="Perpetual Inventory Management System"
APP_NAME="GenAI-Platform"

#Service Now Assignment Group
ASSIGNMENT_GROUP="GenAI-Platform"

#project number for the related deployment
PROJECT_OR_INCIDENT_NUMBER=PRJ0017834

#NT name of the peer reviewer
PEER_REVIEWER=sreedeep.katragadda

#NT name of the manager who approved this deployment
#The manager is responsible for the developers added to this project
MANAGER_APPROVAL=ramanathan.sekkappan

# gitlab url of source code
SOURCE_URL=https://gitlab.com/dish-it-wireless-devops/dishwireless-mno/serverless-automation/wireless-network-datalake/watsonx-genai/dish-ran

#ties directly to Rally data that is imported into ServiceNow
RALLY_NUMBERS="GENAI-8"

#Why is this change necessary? Must be unique between SCRs.
WHY_NECESSARY="Prompt update for defects"

# Optional target to prod date in "YYYY-MM-DD HH-MM-SS" format
TARGET_TO_PROD_DATE="2025-11-21 10:15:00"