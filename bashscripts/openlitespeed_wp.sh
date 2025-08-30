#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No color

# Display menu
function show_menu() {
    clear
    echo -e "${BLUE}==============================="
    echo -e "  WordPress Installation with OpenLiteSpeed"
    echo -e "==============================="
    echo -e "${YELLOW}Please choose an option:${NC}"
    echo -e "1) Install OpenLiteSpeed and PHP"
    echo -e "2) Install OpenLiteSpeed, PHP, and MariaDB"
    echo -e "3) Install OpenLiteSpeed, PHP, MariaDB, and WordPress"
    echo -e "4) Install OpenLiteSpeed, PHP, MariaDB, WordPress, and LiteSpeed Cache Plugin"
    echo -e "5) Install WordPress only"
    echo -e "6) Install WordPress with full configuration (no wp-config.php required)"
    echo -e "7) Exit"
    read -p "Your choice: " choice
    case $choice in
        1) install_ols_php ;;
        2) install_ols_php_mariadb ;;
        3) install_ols_php_mariadb_wp ;;
        4) install_ols_php_mariadb_wp_lscache ;;
        5) install_wp ;;
        6) install_wp_full ;;
        7) exit 0 ;;
        *) echo -e "${RED}Please enter a valid option.${NC}" && sleep 2 && show_menu ;;
    esac
}

# Install OpenLiteSpeed and PHP
function install_ols_php() {
    echo -e "${GREEN}Installing OpenLiteSpeed and PHP...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh)
    show_menu
}

# Install OpenLiteSpeed, PHP, and MariaDB
function install_ols_php_mariadb() {
    echo -e "${GREEN}Installing OpenLiteSpeed, PHP, and MariaDB...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh) --mariadbver 11.4    show_menu
}

# Install OpenLiteSpeed, PHP, MariaDB, and WordPress
function install_ols_php_mariadb_wp() {
    echo -e "${GREEN}Installing OpenLiteSpeed, PHP, MariaDB, and WordPress...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh) -w
    show_menu
}

# Install OpenLiteSpeed, PHP, MariaDB, WordPress, and LiteSpeed Cache Plugin
function install_ols_php_mariadb_wp_lscache() {
    echo -e "${GREEN}Installing OpenLiteSpeed, PHP, MariaDB, WordPress, and LiteSpeed Cache Plugin...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh) -w
    # Install LiteSpeed Cache Plugin
    wp plugin install litespeed-cache --activate
    show_menu
}

# Install WordPress only
function install_wp() {
    echo -e "${GREEN}Installing WordPress only...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh) -w --skip-ols
    show_menu
}

# Install WordPress with full configuration
function install_wp_full() {
    echo -e "${GREEN}Installing WordPress with full configuration...${NC}"
    bash <(curl -k https://raw.githubusercontent.com/litespeedtech/ols1clk/master/ols1clk.sh) --wordpressplus --wpuser admin --wppassword admin --wplang fa_IR --sitetitle "My Website"
    show_menu
}

# Start menu
show_menu