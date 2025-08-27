#!/bin/bash

# Define color codes
BLUE="\033[34m"
YELLOW="\033[33m"
ORANGE="\033[38;5;208m" # ANSI 256 color for orange
GREEN="\033[32m"
RED="\033[31m"
RESET="\033[0m"

simplify_dig_output() {
  local domain=$1
  echo -e "${BLUE}Simplified DNS Information for $domain:${RESET}"
  dig +noall +answer "$domain" | awk -v orange="$ORANGE" -v reset="$RESET" '{print orange"Record: "$4 reset", "orange"TTL: "$2 reset", "orange"Data: "$5 reset}'
}

fetch_ns_records() {
  local domain=$1
  echo -e "${BLUE}Nameserver Records for $domain:${RESET}"
  dig NS "$domain" +short | awk -v yellow="$YELLOW" -v reset="$RESET" '{print yellow $0 reset}'
}

fetch_http_headers() {
  local domain=$1
  echo -e "${BLUE}HTTP Headers for $domain:${RESET}"
  curl -Iv "$domain" 2>/dev/null | awk -v orange="$ORANGE" -v reset="$RESET" '{print orange $0 reset}'
}

fetch_ip_geolocation() {
  local ip=$1
  echo -e "${BLUE}Geolocation Information for IP $ip:${RESET}"
  curl -s "http://ip-api.com/json/$ip" | jq --color-output '. | {Country: .country, Region: .regionName, City: .city, ISP: .isp, Org: .org, Latitude: .lat, Longitude: .lon}'
}

check_and_install_jq() {
  if ! command -v jq &> /dev/null; then
    echo -e "${RED}jq is not installed. Installing jq...${RESET}"
    sudo apt install -y jq
  fi
}

check_and_install_jq

read -p "Enter the domain name: " domain
if [[ -z "$domain" ]]; then
  echo -e "${RED}Error: Domain name cannot be empty.${RESET}"
  exit 1
fi

simplify_dig_output "$domain"
fetch_ns_records "$domain"
fetch_http_headers "$domain"

ip=$(dig +short "$domain" | head -n 1)
if [[ -z "$ip" ]]; then
  echo -e "${RED}Error: Unable to resolve IP address for $domain.${RESET}"
  exit 1
fi

# Display resolved IP address in red
echo -e "${BLUE}Resolved IP Address: ${RED}$ip${RESET}"
echo -e "${BLUE}Scanning ports 80 and 443 on $ip...${RESET}"
nmap -p 80,443 "$ip" | grep -E "^(80|443)/tcp" | awk -v green="$GREEN" -v orange="$ORANGE" -v red="$RED" -v reset="$RESET" '
/open/ {print green $0 reset}
/closed/ {print orange $0 reset}
/filtered/ {print red $0 reset}'

fetch_ip_geolocation "$ip"
