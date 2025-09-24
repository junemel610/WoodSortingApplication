#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# install_openvino.sh
#
# An installer script for installing one or more openvino versions, optionally
# followed by a single “driver” installation.
#
# EXAMPLE USAGE:
#
#   # 1. Install runtime only for version 1.5
#   ./install_openvino.sh 1.5
#
#   # 2. Install runtime + driver for version 1.5
#   ./install_openvino.sh 1.5 DRIVER
#
#   # 3. Install runtimes for multiple versions
#   ./install_openvino.sh 1.0 2.0 3.0
#
#   # 4. (not allowed) Install runtime + driver for multiple versions
#   ./install_openvino.sh 1.0 2.0 DRIVER
#   ---> will throw an error and exit. assume that 'DRIVER' flag
#        will only exist in single-version installations
#
###############################################################################

declare -A openvino_versions
openvino_versions["2024.6.0"]="https://storage.openvinotoolkit.org/repositories/openvino/packages/2024.6/linux/l_openvino_toolkit_ubuntu20_2024.6.0.17404.4c0f47d2335_x86_64.tgz"
openvino_versions["2024.2.0"]="https://storage.openvinotoolkit.org/repositories/openvino/packages/2024.2/linux/l_openvino_toolkit_ubuntu20_2024.2.0.15519.5c0f38f83f6_x86_64.tgz"
openvino_versions["2023.3.0"]="https://storage.openvinotoolkit.org/repositories/openvino/packages/2023.3/linux/l_openvino_toolkit_ubuntu20_2023.3.0.13775.ceeafaf64f3_x86_64.tgz"


# Install openvino for version $1
# Parameters:
#   $1  Version string (e.g. "4.20.1", "2.0-rc1")
install_runtime() {
    version=$1
    link="${openvino_versions[$version]}"
    dir="/opt/intel/openvino_$version"

    # Check if the version is already installed
    if [ -d "$dir" ]; then
        echo "OpenVINO $version is already installed."
        return
    fi

    # Create /opt/intel if it doesn't exist
    sudo mkdir -p /opt/intel

    # Download and extract OpenVINO
    echo "Downloading OpenVINO $version..."
    curl -L "$link" --output "openvino_$version.tgz"
    tar -xf "openvino_$version.tgz"
    extracted_folder=""
    while IFS= read -r line; do
        extracted_folder="${line%%/*}"
        break
    done < <(tar -tf "openvino_$version.tgz")
    sudo mv "$extracted_folder" "$dir"

    # Install dependencies
    echo "Installing dependencies for OpenVINO $version..."
    sudo -E "$dir/install_dependencies/install_openvino_dependencies.sh"

    # Remove the downloaded tar file
    rm "openvino_$version.tgz"
    
    # Success message
    echo "OpenVINO $version installed successfully."
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
  ./install_openvino.sh 1.5
  ./install_openvino.sh 1.5 DRIVER
  ./install_openvino.sh 1.0 2.0 3.0
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
    echo "Installing OpenVINO runtime for version $ver..."
    install_runtime "$ver"
done

# 2. If requested, install the driver for the single version
if $driver_flag; then
    echo "Installing OpenVINO driver for version ${versions[0]}..."
    install_driver "${versions[0]}"
fi
