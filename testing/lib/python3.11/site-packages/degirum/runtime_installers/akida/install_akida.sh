#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_akida.sh
#
# An installer script for installing one or more akida versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.5
#   ./install_akida.sh 1.5
#
#   # 2. Install runtime + driver for version 1.5
#   ./install_akida.sh 1.5 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_akida.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_akida.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

# Install a runtime for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    # Download and install the specified runtime.

    AKIDA_VERSION="$1"

    # Find Python executable
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        PYTHON_EXEC="$VIRTUAL_ENV/bin/python"
    else
        PYTHON_EXEC=$(command -v python3)
    fi

    if [ -z "$PYTHON_EXEC" ] || [ ! -x "$PYTHON_EXEC" ]; then
        echo "No usable Python interpreter found."
        return 1
    fi

    # Step 2: Check current Akida version
    if CURRENT_VERSION=$("$PYTHON_EXEC" -m akida version 2>/dev/null); then
        if [ "$CURRENT_VERSION" = "$AKIDA_VERSION" ]; then
            echo "Akida version $AKIDA_VERSION already installed."
            return 0
        fi
    fi

    # Install desired version
    "$PYTHON_EXEC" -m pip install "akida==$AKIDA_VERSION"
    INSTALL_CODE=$?

    if [ $INSTALL_CODE -ne 0 ]; then
        echo "Akida installation failed with code ${INSTALL_CODE}"
        return $INSTALL_CODE
    fi

    echo "Akida $AKIDA_VERSION installed successfully."
    return 0
}

# Install driver(s) for version $1
# Parameters:
#   $1  Version string (must match the one passed to install_runtime)
install_driver() {
    # Download and install driver. Using the 'ver' is optional, but can be useful
    # if the driver needs to match a specific runtime version.
    local ver="$1"
    # TODO: IMPLEMENT driver installation for version "$ver"
    :
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
  ./install_akida.sh 1.5
  ./install_akida.sh 1.5 DRIVER
  ./install_akida.sh 1.0 2.0 3.0
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
    echo "Installing Akida runtime for version $ver..."
    install_runtime "$ver"
done

# 2. If requested, install the driver for the single version
if $driver_flag; then
    echo "Installing Akida driver for version ${versions[0]}..."
    install_driver "${versions[0]}"
fi
