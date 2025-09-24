#!/bin/bash

# Prompt user for the host name
read -p "Enter the host name: " HOSTNAME

# Prompt user for instance status
read -p "Enter the instance status (SHUTOFF or ACTIVE): " STATUS

# Validate input status (uppercase check)
if [[ "$STATUS" != "SHUTOFF" && "$STATUS" != "ACTIVE" ]]; then
  echo "Invalid status. Please enter 'SHUTOFF' or 'ACTIVE'."
  exit 1
fi

# List all instance IDs and instance names based on the given host and status
echo "Listing all instance IDs and instance names for host '$HOSTNAME' with status '$STATUS'..."

# Fetch instances with additional fields (instance name)
INSTANCE_INFO=$(openstack server list --host "$HOSTNAME" --all-projects --status "$STATUS" -f value -c ID -c Name)

# Check if there are no instances matching the status and host
if [[ -z "$INSTANCE_INFO" ]]; then
  echo "No instances found with status '$STATUS' on host '$HOSTNAME'."
  exit 1
else
  # Display the instance info with numbering
  echo "The following instances with status '$STATUS' were found on host '$HOSTNAME':"
  echo "No | Instance ID    | Instance Name"
  echo "----------------------------------"
  # Add a counter to number each record
  COUNTER=1
  while IFS= read -r line; do
    echo "$COUNTER | $line"
    COUNTER=$((COUNTER + 1))
  done <<< "$INSTANCE_INFO"
fi

# Prompt user for action based on the selected status
if [[ "$STATUS" == "SHUTOFF" ]]; then
  echo "You have selected shutoff instances."
  echo "Choose an action:"
  echo "1. Start all shutoff instances."
  read -p "Enter your choice (1): " ACTION
elif [[ "$STATUS" == "ACTIVE" ]]; then
  echo "You have selected active instances."
  echo "Choose an action:"
  echo "2. Shut off all active instances."
  read -p "Enter your choice (2): " ACTION
fi

# Validate action choice based on status
if [[ "$STATUS" == "SHUTOFF" && "$ACTION" != "1" ]]; then
  echo "Invalid choice. You can only select '1' to start shutoff instances."
  exit 1
elif [[ "$STATUS" == "ACTIVE" && "$ACTION" != "2" ]]; then
  echo "Invalid choice. You can only select '2' to shut off active instances."
  exit 1
fi

# Extract the instance IDs from the instance information
INSTANCE_IDS=$(echo "$INSTANCE_INFO" | awk '{print $1}')

# Perform actions based on the user's choice
if [[ "$ACTION" == "1" && "$STATUS" == "SHUTOFF" ]]; then
  # Start all shutoff instances
  echo "Starting the following shutoff instances:"
  for INSTANCE_ID in $INSTANCE_IDS; do
    echo "Starting instance $INSTANCE_ID..."
    openstack server start "$INSTANCE_ID"
  done
elif [[ "$ACTION" == "2" && "$STATUS" == "ACTIVE" ]]; then
  # Shut off all active instances
  echo "Shutting off the following active instances:"
  for INSTANCE_ID in $INSTANCE_IDS; do
    echo "Shutting off instance $INSTANCE_ID..."
    openstack server stop "$INSTANCE_ID"
  done
fi

echo "Action completed."
