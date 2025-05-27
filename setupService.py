#!/usr/bin/python3
import os
import sys
from enum import Enum, auto
from pathlib import Path

from simpleWorkReporter import config, defs, sslcert, syslog
from simpleWorkReporter.errors import *

config_path = defs.CONFIG_FILE_PATH


class RunMode(Enum):
    INIT = auto()
    UPDATE = auto()
    RESET = auto()


# =============================================================================
# User Interface Functions
# =============================================================================

def print_header():
    """Print application header with version info."""
    print("=" * 60)
    print("simpleWorkReporter - Setup Wizard")
    print("=" * 60)
    print()


def print_section(title: str):
    """Print section header."""
    print(f"\n{title}")
    print("-" * len(title))


def print_success(message: str):
    """Print success message."""
    print(f"✓ {message}")


def print_warning(message: str):
    """Print warning message."""
    print(f"⚠ WARNING: {message}")


def print_error(message: str):
    """Print error message."""
    print(f"✗ ERROR: {message}")


def msg__init_intro(config_path):
    print_section("Configuration Initialization")
    print(f"Creating new configuration file: {config_path}")


def msg__no_password():
    print_warning(
        "You have skipped setting a passphrase to protect the portal.\n"
        "  Submit an empty password field when prompted for authentication."
    )


def query_setup_value(
    key: str, value: dict, default: str = None, update=False
):
    """Uses the supplied setup key and value details to request user input."""
    print()
    
    # Print description with proper formatting
    for line in value["desc"]:
        print(f"  {line}")
    print()

    default = default or value["default"]
    
    # Format prompt based on field type
    if key.lower() == "access":
        prompt = f"{key}: "
    else:
        if default:
            prompt = f"{key} [{default}]: "
        else:
            prompt = f"{key}: "

    try:
        if key.lower() == "access":
            # Hide password input if available
            try:
                import getpass
                response = getpass.getpass(prompt)
            except ImportError:
                response = input(prompt)
        else:
            response = input(prompt)
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        sys.exit(1)
    except EOFError:
        print("\n\nUnexpected end of input.")
        sys.exit(1)

    # Handle empty responses
    if not response:
        if key.lower() == "access":
            if not update:
                response = ""
                msg__no_password()
            else:
                response = None
        else:
            if default:
                print(f"  → Using default: {default}")
                response = default
            else:
                print_error("This field is required.")
                return query_setup_value(key, value, default, update)

    return response


def verify_settings(settings: dict, update: bool = False):
    """Display settings for user verification and get confirmation."""
    print_section("Configuration Summary")
    
    # Display settings in a formatted table
    max_key_length = max(len(k) for k in settings.keys())
    
    for k, v in settings.items():
        if k == "access":
            if v is None:
                display_value = "<no change>"
            elif v == "":
                display_value = "<empty>"
            else:
                display_value = "*" * len(v) if v else "<empty>"
        else:
            display_value = v
        
        print(f"  {k.ljust(max_key_length)} : {display_value}")

    print()
    
    while True:
        try:
            response = input("Commit these settings? [y/N/q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup interrupted.")
            sys.exit(1)
        
        if not response or response == 'n':
            return False
        elif response == 'y':
            return True
        elif response == 'q':
            print("Setup cancelled by user.")
            sys.exit(0)
        else:
            print("Please enter 'y' for yes, 'n' for no, or 'q' to quit.")


def prompt_yes_no(message: str, default: bool = False) -> bool:
    """Generic yes/no prompt with proper error handling."""
    default_char = "Y/n" if default else "y/N"
    
    while True:
        try:
            response = input(f"{message} [{default_char}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup interrupted.")
            sys.exit(1)
        
        if not response:
            return default
        elif response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")


def prompt_ssl_setup():
    """Prompt user for SSL setup decision."""
    print_section("SSL Configuration")
    print("SSL/HTTPS is recommended for all simpleWorkReporter instances.")
    print("The web portal will run in HTTP mode if SSL is not configured.")
    print()
    
    return prompt_yes_no("Create self-signed SSL certificates?", default=True)


def prompt_ssl_file_removal():
    """Prompt user to remove invalid SSL files."""
    print_error("Existing SSL certificate files are invalid:")
    print(f"  - {defs.SSL_CERT_FILE}")
    print(f"  - {defs.SSL_KEY_FILE}")
    print()
    
    if not prompt_yes_no("Remove invalid files and continue?"):
        print("Setup cancelled.")
        sys.exit(1)
    return True


def prompt_update_config():
    """Prompt user to update existing configuration."""
    print_section("Configuration Update")
    print("An existing configuration file was found.")
    print()
    
    if not prompt_yes_no("Update existing configuration?"):
        print("Setup cancelled.")
        sys.exit(1)
    return True


def prompt_reset_config(config_path: Path, error: str):
    """Prompt user to reset corrupted configuration."""
    print_error(f"Configuration file is invalid: {config_path}")
    print(f"  Reason: {error}")
    print()
    print("The corrupt file must be removed to continue.")
    print()
    
    if not prompt_yes_no("Remove corrupt file and reinitialize?"):
        print("Setup cancelled.")
        sys.exit(1)
    return True


# =============================================================================
# Wizard Functions
# =============================================================================

def wizard__collect_settings(
    config_path: Path, settings: dict = {}, update: bool = False
):
    """Collect configuration settings from user input."""
    print_section("Configuration Settings")
    if update:
        print("Leave fields blank to keep existing values.")
    print()
    
    while True:
        for k, v in defs.REQUIRED_CONF_VALUES.items():
            settings[k.lower()] = query_setup_value(
                k, v, settings.get(k.lower(), ""), update=update
            )
        
        if verify_settings(settings, update):
            break
        
        print("\nReturning to configuration entry...")

    # Save configuration
    if update:
        print("\nUpdating configuration...")
        config.update_config(
            config_path,
            service_port=settings["service_port"],
            worker_name=settings["worker_name"],
            worker_email=settings["worker_email"],
            manager_name=settings["manager_name"],
            manager_email=settings["manager_email"],
            smtp=settings["smtp"],
            access=settings["access"],
        )
        print_success("Configuration updated successfully")
    else:
        print("\nSaving configuration...")
        config.create_config_file(config_path, settings)
        print_success("Configuration saved successfully")


def wizard__init(config_path: Path, settings={}):
    """Initialize new configuration."""
    msg__init_intro(config_path)
    wizard__collect_settings(config_path, settings)
    
    print()
    print_success("Setup completed successfully!")
    print(f"Start the service by running: python3 startService.py")
    sys.exit(0)


def wizard__update(config_path: Path, settings: dict = {}):
    """Update existing configuration."""
    prompt_update_config()
    wizard__collect_settings(config_path, settings, update=True)
    
    print()
    print_success("Configuration updated successfully!")
    print("Restart the service for changes to take effect.")
    sys.exit(0)


def wizard__reset(config_path: Path, error: str, settings: dict = {}):
    """Reset corrupted configuration."""
    prompt_reset_config(config_path, error)
    
    print("Removing corrupted configuration file...")
    os.remove(config_path)
    print_success("Corrupted file removed")
    
    wizard__init(config_path, settings)


def wizard__sslsetup():
    """Handle SSL certificate setup."""
    if not sslcert.is_ssl_configured(defs.SSL_CERT_FILE, defs.SSL_KEY_FILE):
        if prompt_ssl_setup():
            print("Creating SSL certificate files...")
            print(f"  Certificate: {defs.SSL_CERT_FILE}")
            print(f"  Private Key: {defs.SSL_KEY_FILE}")
            
            try:
                sslcert.create_ssl_files(defs.SSL_CERT_FILE, defs.SSL_KEY_FILE)
                print_success("SSL certificates created successfully")
            except Exception as e:
                print_error(f"Failed to create SSL certificates: {e}")
                sys.exit(1)
        else:
            print("Skipping SSL setup - service will run in HTTP mode")
    elif not sslcert.validate_ssl_files(defs.SSL_CERT_FILE, defs.SSL_KEY_FILE):
        if prompt_ssl_file_removal():
            sslcert.remove_ssl_files(defs.SSL_CERT_FILE, defs.SSL_KEY_FILE)
            print_success("Invalid SSL files removed")


# =============================================================================
# Main Execution
# =============================================================================

def determine_run_mode(config_path):
    """Determine the appropriate run mode based on config file state."""
    if not os.path.isfile(config_path):
        return RunMode.INIT, {}

    try:
        settings = config._load_config(config_path)
        return RunMode.UPDATE, settings
    except swrConfigError as e:
        settings = config._load_config(config_path, allow_partial=True)
        return RunMode.RESET, settings, str(e)


def main():
    """Main setup function."""
    print_header()
    
    # Handle SSL setup first
    wizard__sslsetup()

    # Determine run mode and load existing settings if available
    mode_result = determine_run_mode(config_path)
    run_mode = mode_result[0]
    settings = mode_result[1] if len(mode_result) > 1 else {}
    error = mode_result[2] if len(mode_result) > 2 else None

    # Execute appropriate wizard based on run mode
    if run_mode == RunMode.INIT:
        wizard__init(config_path, settings)
    elif run_mode == RunMode.UPDATE:
        wizard__update(config_path, settings)
    elif run_mode == RunMode.RESET:
        wizard__reset(config_path, error, settings)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
