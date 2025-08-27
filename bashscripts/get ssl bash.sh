#!/bin/bash

# Display introductory message
echo "Welcome to the Let's Encrypt SSL Setup Script!"
echo "This script will help you obtain a free SSL certificate using Certbot."

# Function to check if certbot is installed
check_certbot() {
    if ! command -v certbot &> /dev/null; then
        echo "Certbot not found. Installing Certbot..."
        sudo apt-get update
        sudo apt-get install certbot -y
    else
        echo "Certbot is already installed."
    fi
}

# Function to obtain SSL certificate for the domain
obtain_ssl_certificate() {
    echo "Please enter the domain name for the SSL certificate (e.g., example.com):"
    read domain_name

    # Confirm domain name
    echo "You are requesting an SSL certificate for: $domain_name"
    echo "Is this correct? (y/n)"
    read confirmation
    if [[ "$confirmation" != "y" ]]; then
        echo "Exiting... Please run the script again to correct the domain name."
        exit 1
    fi

    echo "Do you want to enable HTTP to HTTPS redirect? (y/n)"
    read redirect_choice

    # Run Certbot to obtain the SSL certificate
    if [[ "$redirect_choice" == "y" ]]; then
        sudo certbot --apache -d "$domain_name" --redirect
    else
        sudo certbot --apache -d "$domain_name"
    fi

    # Check if SSL was successfully obtained
    if [[ $? -eq 0 ]]; then
        echo "SSL certificate successfully obtained for $domain_name."
    else
        echo "Failed to obtain SSL certificate. Please check the logs for more details."
        exit 1
    fi
}

# Function to set up automatic certificate renewal
setup_renewal() {
    echo "Would you like to set up automatic renewal for your SSL certificate? (y/n)"
    read renewal_choice

    if [[ "$renewal_choice" == "y" ]]; then
        sudo systemctl enable certbot.timer
        echo "Automatic certificate renewal has been enabled."
    else
        echo "You can manually renew your certificate by running 'sudo certbot renew'."
    fi
}

# Function to display options menu
display_menu() {
    echo "Please select an option:"
    echo "1. Install Certbot (if not already installed)"
    echo "2. Obtain SSL certificate for a domain"
    echo "3. Set up automatic certificate renewal"
    echo "4. Exit"

    read -p "Enter your choice [1-4]: " user_choice
    case $user_choice in
        1)
            check_certbot
            ;;
        2)
            obtain_ssl_certificate
            ;;
        3)
            setup_renewal
            ;;
        4)
            echo "Exiting the script. Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice. Please choose a number between 1 and 4."
            ;;
    esac
}

# Main loop to display the menu
while true; do
    display_menu
done

