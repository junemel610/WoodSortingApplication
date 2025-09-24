#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_memryx.sh
#
# An installer script for installing one or more memryx versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.5
#   ./install_memryx.sh 1.5
#
#   # 2. Install runtime + driver for version 1.5
#   ./install_memryx.sh 1.5 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_memryx.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_memryx.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

declare -A MEMX_DRIVER_VERSIONS
MEMX_DRIVER_VERSIONS["1.2.3-1"]="1.2.1-3.1"

# Install a runtime for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    # Download and install the specified runtime.
    
    MEMX_ACCL_VERSION=$1

    # Check if MemryX is already installed and matches version
    if check_version memx-accl "$MEMX_ACCL_VERSION"; then
        echo "MemryX RT version $MEMX_ACCL_VERSION is already installed."
        return
    fi

    # Add MemryX apt repo if not exist
    add_memryx_repo

    # REMOVE WHEN DEPENDENCY TREE IS FIXED BY MEMRYX
    # Install proper version of drivers before runtime
    install_driver "${MEMX_ACCL_VERSION}"

    # Install runtime
    sudo apt install -y memx-accl=$MEMX_ACCL_VERSION

    # Confirm installation
    if check_version memx-accl "$MEMX_ACCL_VERSION"; then
        echo "MemryX RT version $MEMX_ACCL_VERSION installed successfully."
    else
        echo "Failed to install MemryX RT version $MEMX_ACCL_VERSION. Please check for errors above."
        exit 1
    fi
}

# Install driver(s) for version $1
# Parameters:
#   $1  Version string (must match the one passed to install_runtime)
install_driver() {
    # Download and install driver. Using the 'ver' is optional, but can be useful
    # if the driver needs to match a specific runtime version.
    
    MEMX_ACCL_VERSION=$1
    MEMX_DRIVER_VERSION="${MEMX_DRIVER_VERSIONS[$MEMX_ACCL_VERSION]}"

    # Check if MemryX driver is already installed and matches version
    INSTALLED_DRIVER_VERSION=$(dpkg -s memx-drivers 2>/dev/null | grep '^Version:' | awk '{print $2}')
    echo "Installed driver version: $INSTALLED_DRIVER_VERSION"

    if [ "$INSTALLED_DRIVER_VERSION" == "$MEMX_DRIVER_VERSION" ]; then
        echo "MemryX RT version $MEMX_DRIVER_VERSION is already installed."
        exit 0
    elif [ -n "$INSTALLED_DRIVER_VERSION" ]; then
        # if version mismatch, uninstall the existing version
        echo "A different version of MemryX RT is installed: $INSTALLED_DRIVER_VERSION. Removing it..."
        sudo apt purge memx-* -y
        sudo rm /etc/apt/sources.list.d/memryx.list /etc/apt/trusted.gpg.d/memryx.asc
    else
        echo "Memryx RT is not currently installed."
    fi

    # Ensure kernel headers are installed before installing the driver
    sudo apt install -y linux-headers-$(uname -r)

    # install the MemryX drivers and runtime libraries
    sudo apt install -y memx-drivers=$MEMX_DRIVER_VERSION

    # Confirm installation
    if check_version memx-drivers "$MEMX_DRIVER_VERSION"; then
        echo "MemryX RT version $MEMX_DRIVER_VERSION installed successfully."
    else
        echo "Failed to install MemryX RT version $MEMX_DRIVER_VERSION. Please check for errors above."
        exit 1
    fi
}

add_memryx_repo() {
    # Set variables
    KEY_URL="https://developer.memryx.com/deb/memryx.asc"
    KEY_PATH="/etc/apt/trusted.gpg.d/memryx.asc"
    REPO_LIST_PATH="/etc/apt/sources.list.d/memryx.list"
    REPO_SOURCE="https://developer.memryx.com/deb stable main"

    # Check if repo already added
    if [ -f "$REPO_LIST_PATH" ]; then
        echo "MemryX apt repo already added"
        return
    fi

    # Add the MemryX signing key
    wget -qO- "${KEY_URL}" | sudo tee "${KEY_PATH}" >/dev/null
    # Add the MemryX repository
    echo "deb ${REPO_SOURCE}" | sudo tee "${REPO_LIST_PATH}" >/dev/null

    # Update APT
    sudo apt update
}

check_version() {
    local PACKAGE_NAME="$1"
    local EXPECTED_VERSION="$2"

    # Get installed version of the package
    local INSTALLED_VERSION

    # Try to get the installed version
    if ! INSTALLED_VERSION=$(dpkg -s "$PACKAGE_NAME" 2>/dev/null | grep '^Version:' | awk '{print $2}'); then
        INSTALLED_VERSION=""
    fi

    # Check version matching, return code 0 if match
    if [ "$INSTALLED_VERSION" = "$EXPECTED_VERSION" ]; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Print usage/help text and exit
# -----------------------------------------------------------------------------
usage() {
    cat <<EOF >&2
Usage: $0 <version1> [version2 ...] [DRIVER]

  - Specify one or more version strings.
  - Optionally, add a final argument "DRIVER" (exactly) to also install a driver.
    * “DRIVER” may only be passed if exactly one version is given.

EXAMPLES:
  ./install_memryx.sh 1.5
  ./install_memryx.sh 1.5 DRIVER
  ./install_memryx.sh 1.0 2.0 3.0
EOF
    exit 1
}

# -----------------------------------------------------------------------------
# ARGUMENT PARSING
# -----------------------------------------------------------------------------
if [[ $# -lt 1 ]]; then
    usage
fi

# Detect optional DRIVER flag (must be the very last argument)
driver_flag=false
if [[ "${!#}" == "DRIVER" ]]; then
    driver_flag=true
    # Strip off the last argument so "$@" now contains only versions
    set -- "${@:1:$(($#-1))}"
fi

# Remaining args are version strings
versions=("$@")

# Enforce: DRIVER only valid when exactly one version is given
if $driver_flag && [[ "${#versions[@]}" -ne 1 ]]; then
    echo "Error: DRIVER may only be used when exactly one version is specified." >&2
    usage
fi

# 1. Install all requested runtimes
for ver in "${versions[@]}"; do
    echo "Installing runtime for version $ver..."
    install_runtime "$ver"
done

# 2. If requested, install the driver for the single version
if $driver_flag; then
    echo "Installing driver for version ${versions[0]}..."
    install_driver "${versions[0]}"
fi
