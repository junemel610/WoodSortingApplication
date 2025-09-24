#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_onnx.sh
#
# An installer script for installing one or more onnx versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.5
#   ./install_onnx.sh 1.5
#
#   # 2. Install runtime + driver for version 1.5
#   ./install_onnx.sh 1.5 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_onnx.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_onnx.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

# Install ONNX runtime for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    ONNX_RUNTIME_VERSION=$1

    # Determine architecture
    if [[ "$(uname -m)" == "x86_64" ]]; then
        arch_suff=x64
        echo "Detected architecture: x86_64"
    else
        arch_suff=aarch64
        echo "Detected architecture: ARM64"
    fi

    # Set the string to 'linux' or 'osx'
    linux_or_mac_string=linux
    if [[ "$(uname)" == "Darwin" ]]; then
        linux_or_mac_string=osx
        
        if [[ "$(uname -m)" == "arm64" ]]; then
            arch_suff=arm64 # linux arm is 'aarch64' but mac arm is 'arm64'
        fi
    fi

    # Construct archive name
    installer_name="onnxruntime-${linux_or_mac_string}-${arch_suff}-${ONNX_RUNTIME_VERSION}"

    # Check if the directory exists in /usr/local
    if [[ -d "/usr/local/${installer_name}" ]]; then
        echo "ONNX Runtime version $ONNX_RUNTIME_VERSION is already installed."
        return
    fi

    # Install ONNX runtime
    echo "Installing ONNX Runtime version ${ONNX_RUNTIME_VERSION}"
    curl -L -O "https://github.com/microsoft/onnxruntime/releases/download/v${ONNX_RUNTIME_VERSION}/${installer_name}.tgz"
    tar -xzf "${installer_name}.tgz"
    sudo mv "${installer_name}" /usr/local
    rm "${installer_name}.tgz"
    echo "ONNX Runtime installation completed"
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
  ./install_onnx.sh 1.5
  ./install_onnx.sh 1.5 DRIVER
  ./install_onnx.sh 1.0 2.0 3.0
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
    echo "Installing ONNX runtime for version $ver..."
    install_runtime "$ver"
done

# 2. If requested, install the driver for the single version
if $driver_flag; then
    echo "Installing ONNX driver for version ${versions[0]}..."
    install_driver "${versions[0]}"
fi
