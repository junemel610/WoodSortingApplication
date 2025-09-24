#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_axelera.sh
#
# An installer script for installing one or more axelera versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.3
#   ./install_axelera.sh 1.3
#
#   # 2. Install runtime + driver for version 1.3
#   ./install_axelera.sh 1.3 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_axelera.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_axelera.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

declare -A METIS_VERSIONS
METIS_VERSIONS["1.3.3"]="1.0.3"

# Install a runtime for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    # Download and install the specified runtime.

    AXELERA_VERSION="$1"

    if [ -d "/opt/axelera/runtime-$AXELERA_VERSION-1" ]; then
        echo "Axelera version $AXELERA_VERSION is already installed."
        return
    fi

    # Add axelera apt repo if not exist
    add_axelera_repo

    # Install the packages with specific versions
    sudo apt install -y \
        axelera-runtime-$AXELERA_VERSION \
        axelera-device-$AXELERA_VERSION \
        axelera-riscv-gnu-newlib-toolchain-409b951ba662-7

    # Add Axelera runtime libraries to ldconfig
    echo "/opt/axelera/runtime-$AXELERA_VERSION-1/lib" | sudo tee /etc/ld.so.conf.d/axelera.conf > /dev/null
    sudo ldconfig

    echo "Axelera version $AXELERA_VERSION installed successfully."
}

# Install driver(s) for version $1
# Parameters:
#   $1  Version string (must match the one passed to install_runtime)
install_driver() {
    # Download and install driver. Using the 'ver' is optional, but can be useful
    # if the driver needs to match a specific runtime version.

    # Match passed runtime version to Metis driver version
    AXELERA_VERSION=$1
    METIS_VERSION="${METIS_VERSIONS[$AXELERA_VERSION]}"

    # Add axelera apt repo if not exist
    add_axelera_repo

    # Install the packages with specific versions
    sudo apt install -y metis-dkms=$METIS_VERSION 
}

# Adds Axelera's public repo to apt
add_axelera_repo() {
    # Set variables
    GPG_URL="https://software.axelera.ai/artifactory/api/security/keypair/axelera/public"
    GPG_KEY_PATH="/etc/apt/keyrings/axelera.gpg"
    REPO_LIST_PATH="/etc/apt/sources.list.d/axelera.list"
    REPO_SOURCE="https://software.axelera.ai/artifactory/axelera-apt-source/ stable main"

    # Check if repo already added
    if [ -f "$REPO_LIST_PATH" ]; then
        echo "Axelera apt repo already added"
        return
    fi

    # Create keyring directory if it doesn't exist
    sudo mkdir -p "$(dirname "$GPG_KEY_PATH")"

    # Download and store the GPG key
    curl -fsSL "$GPG_URL" | gpg --dearmor | sudo tee "$GPG_KEY_PATH" > /dev/null

    # Ensure correct permissions for the GPG key
    sudo chmod 644 "$GPG_KEY_PATH"

    # Add the repository source
    echo "deb [signed-by=$GPG_KEY_PATH] $REPO_SOURCE" | sudo tee "$REPO_LIST_PATH" > /dev/null

    # Update APT, ignore errors encountered by apt
    sudo apt update || true
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
  ./install_axelera.sh 1.3
  ./install_axelera.sh 1.3 DRIVER
  ./install_axelera.sh 1.0 2.0 3.0
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
    echo "Installing Axelera runtime for version $ver..."
    install_runtime "$ver"
done

# 2. If requested, install the driver for the single version
if $driver_flag; then
    echo "Installing Axelera driver for version ${versions[0]}..."
    install_driver "${versions[0]}"
fi
