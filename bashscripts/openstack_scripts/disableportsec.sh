#!/bin/bash

read -p "Enter the project ID: " project_id

ports=$(openstack port list --project "$project_id" -f value -c ID -c Name -c Status -c MAC\ Address -c Fixed\ IPs)

if [[ -z "$ports" ]]; then
    echo "No ports found for project ID $project_id."
    exit 1
fi

echo -e "Index\tPort ID\t\t\t\tName\t\tStatus\t\tMAC Address\t\t\tFixed IPs"
echo "-----------------------------------------------------------------------------------------------------"

ports_array=()
index=0

while IFS= read -r line; do
    ports_array+=("$line")
    port_id=$(echo "$line" | awk '{print $1}')
    port_name=$(echo "$line" | awk '{print $2}')
    status=$(echo "$line" | awk '{print $3}')
    mac_address=$(echo "$line" | awk '{print $4}')
    fixed_ips=$(echo "$line" | cut -d' ' -f5-)
    echo -e "[$index]\t$port_id\t$port_name\t$status\t$mac_address\t$fixed_ips"
    index=$((index + 1))
done <<< "$ports"
read -p "Enter the index number of the port you want to disable port security for: " selected_index
if ! [[ "$selected_index" =~ ^[0-9]+$ ]] || [ "$selected_index" -ge "$index" ] || [ "$selected_index" -lt 0 ]; then
    echo "Invalid index number."
    exit 1
fi
selected_port=$(echo "${ports_array[$selected_index]}" | awk '{print $1}')
openstack port set --disable-port-security "$selected_port"
echo "Port security has been disabled for port ID: $selected_port"
