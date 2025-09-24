#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_rknn.sh
#
# An installer script for installing one or more rknn versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.5
#   ./install_rknn.sh 1.5
#
#   # 2. Install runtime + driver for version 1.5
#   ./install_rknn.sh 1.5 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_rknn.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_rknn.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

# Install a runtime for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    local RKNN_TARGET_VERSION="$1"

    # Check existing installation
    local SO_PATHS=("/usr/lib/librknnrt.so" "/usr/local/lib/librknnrt.so")
    for so_path in "${SO_PATHS[@]}"; do
        if [[ -f "$so_path" ]]; then
            local existing_version
            existing_version=$(get_version_string "$so_path")
            if [[ "$existing_version" == "$RKNN_TARGET_VERSION" ]]; then
                echo "RKNN runtime version $RKNN_TARGET_VERSION already installed at $so_path. Skipping installation."
                return 0
            else
                echo "Found librknnrt.so, version is old: $existing_version (need: $RKNN_TARGET_VERSION)"
            fi
        fi
    done

    # Create temporary directory and set up trap for cleanup
    TMP_DIR=$(mktemp -d)
    trap '[[ -d "$TMP_DIR" ]] && rm -rf "$TMP_DIR"' EXIT

    # Download the repository
    git clone --branch "v${RKNN_TARGET_VERSION}" --depth 1 https://github.com/airockchip/rknn-toolkit2.git "$TMP_DIR/rknn-toolkit2" || {
        echo "Failed to download rknn-toolkit2 version v${RKNN_TARGET_VERSION}"
        return 1
    }

    # Copy runtime shared object and includes
    sudo cp "$TMP_DIR/rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so" /usr/lib/
    sudo cp "$TMP_DIR/rknn-toolkit2/rknpu2/runtime/Linux/librknn_api/include/"* /usr/local/include/

    echo "RKNN runtime version $RKNN_TARGET_VERSION installed successfully."
}

# Get rknn version from .so file
get_version_string() {
  local file_path="$1"
  strings "$file_path" | grep -oP 'librknnrt version: \K[0-9\.]+'
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
  ./install_rknn.sh 1.5
  ./install_rknn.sh 1.5 DRIVER
  ./install_rknn.sh 1.0 2.0 3.0
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
