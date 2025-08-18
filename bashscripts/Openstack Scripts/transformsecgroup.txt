#!/bin/bash

# Get user input
read -p "Enter the new Security Group name: " NEW_SG_NAME
read -p "Enter the project ID: " PROJECT_ID
read -p "Enter the source Security Group ID: " SOURCE_SG_ID

# Check for openstack client existence
if ! command -v openstack &> /dev/null
then
    echo "OpenStack CLI is not installed. Please install it."
    exit 1
fi

# Display existing rules from the source Security Group
echo "Fetching rules from the source Security Group ($SOURCE_SG_ID)..."
openstack security group rule list "$SOURCE_SG_ID"

# Ask for confirmation
read -p "Do you want to proceed with cloning these rules? (yes/no): " CONFIRMATION
if [ "$CONFIRMATION" != "yes" ]; then
    echo "Operation cancelled by the user."
    exit 1
fi

# Create new Security Group
NEW_SG_ID=$(openstack security group create "$NEW_SG_NAME" --project "$PROJECT_ID" -f value -c id)
if [ -z "$NEW_SG_ID" ]; then
    echo "Failed to create new Security Group."
    exit 1
fi

echo "New Security Group created: $NEW_SG_ID"

# Get list of rules from the source Security Group
RULES=$(openstack security group rule list "$SOURCE_SG_ID" -f json)

# Debugging output for RULES
if [ -z "$RULES" ] || [ "$RULES" == "[]" ]; then
    echo "Source Security Group contains no rules or failed to retrieve rules."
    exit 1
fi

RULE_COUNT=$(echo "$RULES" | jq '. | length')

echo "Checking existing rules in the destination Security Group..."
EXISTING_RULES=$(openstack security group rule list "$NEW_SG_ID" -f json)
EXISTING_RULE_COUNT=$(echo "$EXISTING_RULES" | jq '. | length')

if [ "$EXISTING_RULE_COUNT" -ge "$RULE_COUNT" ]; then
    echo "Destination Security Group already contains $EXISTING_RULE_COUNT rules. No new rules will be added."
    exit 0
fi

echo "$RULE_COUNT rules found in the source. Proceeding to copy..."

# Process and copy rules to the new Security Group
COUNTER=0
for ((i=0; i<RULE_COUNT; i++)); do
    row=$(echo "$RULES" | jq -c ".[$i]")
    ID=$(echo "$row" | jq -r '."ID"')
    PROTOCOL=$(echo "$row" | jq -r '."IP Protocol" // ""')
    ETHER_TYPE=$(echo "$row" | jq -r '."Ethertype"')
    IP_RANGE=$(echo "$row" | jq -r '."IP Range" // ""')
    PORT_RANGE=$(echo "$row" | jq -r '."Port Range" // ""')
    DIRECTION=$(echo "$row" | jq -r '."Direction"' | tr '[:upper:]' '[:lower:]')
    REMOTE_SECURITY_GROUP=$(echo "$row" | jq -r '."Remote Security Group" // ""')
    REMOTE_ADDRESS_GROUP=$(echo "$row" | jq -r '."Remote Address Group" // ""')

    # Skip egress rules
    if [ "$DIRECTION" == "egress" ]; then
        echo "Skipping egress rule $ID."
        continue
    fi

    # Skip rule if it already exists in the destination
    EXISTS=$(echo "$EXISTING_RULES" | jq -c ".[] | select(.\"IP Protocol\" == \"$PROTOCOL\" and .\"Ethertype\" == \"$ETHER_TYPE\" and .\"IP Range\" == \"$IP_RANGE\" and .\"Port Range\" == \"$PORT_RANGE\" and .\"Direction\" == \"$DIRECTION\")")
    if [ -n "$EXISTS" ]; then
        echo "Rule $ID already exists in destination. Skipping..."
        continue
    fi

    CMD="openstack security group rule create $NEW_SG_ID --ethertype $ETHER_TYPE"
    
    if [ "$DIRECTION" == "ingress" ]; then
        CMD+=" --ingress"
    fi
    
    if [ -n "$PROTOCOL" ]; then
        CMD+=" --protocol $PROTOCOL"
    fi
    if [ -n "$PORT_RANGE" ]; then
        CMD+=" --dst-port $PORT_RANGE"
    fi
    if [ -n "$IP_RANGE" ] && [ -z "$REMOTE_SECURITY_GROUP" ]; then
        CMD+=" --remote-ip $IP_RANGE"
    elif [ -n "$REMOTE_SECURITY_GROUP" ] && [ -z "$IP_RANGE" ]; then
        CMD+=" --remote-group $REMOTE_SECURITY_GROUP"
    fi
    
    echo "Executing: $CMD"
    eval $CMD
    
    if [ $? -eq 0 ]; then
        echo "Rule $ID copied successfully. ($((++COUNTER))/$RULE_COUNT)"
    else
        echo "Error copying rule $ID. ($COUNTER/$RULE_COUNT)"
    fi

done

echo "All applicable ingress rules have been copied."
