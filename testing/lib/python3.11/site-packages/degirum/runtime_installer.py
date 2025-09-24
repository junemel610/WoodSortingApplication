#
# runtime_installer.py - DeGirum PySDK: runtime and driver installer
# Copyright DeGirum Corp. 2025
#
# Handles CLI runtime installation for publicly available runtimes
#

import argparse
import os
import platform
import subprocess
from typing import Optional
import yaml

# Variable DegirumException import to allow module + standalone run
if __name__ == "__main__":
    from exceptions import DegirumException
else:
    from .exceptions import DegirumException


# Global constants
VERSIONING_FILE = "plugin_versions.yaml"
DEFAULT_INSTALLER_DIR = "runtime_installers"
OS_ARCH_CATCHALL = "All"
SUPPORTED_OS = ["Debian", "Windows", "macOS"]
EXTENSION_MAP = {"Debian": "sh", "Windows": "bat", "macOS": "sh"}


def get_os():
    """
    Get OS/platform of current system
    """

    current_platform = platform.system()
    if current_platform == "Linux":
        is_debian = False
        try:
            with open("/etc/os-release") as f:
                os_release = f.read().lower()
                is_debian = "debian" in os_release or "ubuntu" in os_release or "raspbian" in os_release
        except FileNotFoundError:
            is_debian = False
        return "Debian" if is_debian else "Other Linux"
    elif current_platform == "Windows":
        return current_platform
    elif current_platform == "Darwin":
        return "macOS"
    else:
        return current_platform


def get_arch():
    """
    Get architecture of current system
    """

    architecture = platform.machine().lower()

    if any(x in architecture for x in ['x86_64', 'amd64']):
        return 'x86'
    elif any(x in architecture for x in ['arm64', 'aarch64']):
        return 'ARM'
    else:
        return architecture


####################################################################################################


class RuntimeInstaller:
    def __init__(self, custom_installer_dir: Optional[str] = None):
        """
        Constructor to define runtime-specific variables
        """

        # OS + architecture of host current host
        self._current_os = get_os()
        self._current_arch = get_arch()

        # Directory that this file is located in or custom dir passed as arg
        self._installer_dir = (custom_installer_dir or os.path.join(os.path.dirname(__file__), DEFAULT_INSTALLER_DIR))

        # List of runtimes that have installers available for current OS
        if self._current_os in SUPPORTED_OS:
            self._available_installers = \
                [dirname for dirname in os.listdir(self._installer_dir)
                 if os.path.isfile(os.path.join(
                     self._installer_dir, dirname, f"install_{dirname}.{EXTENSION_MAP[self._current_os]}"))]
        else:
            self._available_installers = []

        # Dict of available runtimes and versions
        self._installer_dict = self.read_version_yaml() if self._current_os in SUPPORTED_OS else {}

    def read_version_yaml(self, yaml_path: Optional[str] = None) -> dict:
        """
        Returns a dict of valid runtimes and versions for the current OS
        Prioritizes specific OS filters above default "All" classifier

        Args:
            yaml_path: Path to versioning file, default path used if none specified

        Return:
            Dict in the following format: {plugin_name: [plugin_version(s)]}
        """

        # Default versioning file location
        if yaml_path is None:
            yaml_path = os.path.join(self._installer_dir, VERSIONING_FILE)

        # Read valid runtimes from file, abort if read fail
        try:
            with open(yaml_path, "r") as f:
                version_dict = yaml.safe_load(f)

                filtered_versions = {}

                # Define search priority: (OS, Arch)
                search_order = [
                    (self._current_os, self._current_arch),
                    (self._current_os, OS_ARCH_CATCHALL),
                    (OS_ARCH_CATCHALL, self._current_arch),
                    (OS_ARCH_CATCHALL, OS_ARCH_CATCHALL)
                ]

                for plugin_name, os_dict in version_dict.items():

                    # If the current OS is explicitly excluded by having a None architecture key, skip this plugin
                    if self._current_os in os_dict and None in os_dict[self._current_os]:
                        continue

                    matched_versions = None

                    for os_key, arch_key in search_order:
                        matched_versions = os_dict.get(os_key, {}).get(arch_key)
                        if matched_versions:
                            filtered_versions[plugin_name] = matched_versions
                            break  # Stop at first successful match

            return filtered_versions

        except FileNotFoundError:
            raise DegirumException(f"Version control file [{yaml_path}] not found.")

    def list_runtimes(self) -> list:
        """
        Return list of all available runtime installers for current OS
        Checks that runtime has valid installation script before adding it
        """

        return [runtime_name for runtime_name in self._installer_dict if runtime_name in self._available_installers]

    def list_versions(self, runtime_name: str) -> list:
        """
        Return list of available versions for given runtime, returns empty list if no versions availble

        Args:
            runtime_name: name of runtime to query
        """

        if runtime_name in self.list_runtimes():
            return self._installer_dict[runtime_name]
        return []

    def print_versions(self, runtime_name: str):
        """
        Print semicolon-separated list of versions for usage in CMake
        Does NOT check for existence of valid installer, lists all versions available to current OS

        Args:
            runtime_name: name of runtime to install
        """

        print(";".join(self._installer_dict.get(runtime_name, [])))

    def install_one(self, runtime_name: str, version: str, driver: Optional[bool] = False):
        """
        Runs installer for specified version of a runtime

        Args:
            runtime_name: name of runtime to install
            version: runtime version to install
            driver: flag to enable DRIVER mode of install script
        """

        # Check install script existence
        if runtime_name not in self._available_installers:
            raise DegirumException(f"Cannot find [{runtime_name}] installer compatible with [{self._current_os}]")

        # Define script path
        installer_file = os.path.join(
            self._installer_dir, runtime_name, f"install_{runtime_name}.{EXTENSION_MAP[self._current_os]}")

        # Define optional driver flag
        driver_flag = ["DRIVER"] if driver else []

        # Run install script using bash or powershell
        try:
            if EXTENSION_MAP[self._current_os] == "sh":
                subprocess.run(["bash", installer_file, version] + driver_flag, check=True)
            elif EXTENSION_MAP[self._current_os] == "bat":
                subprocess.run(["cmd.exe", "/c", installer_file, version] + driver_flag, check=True)
            else:
                raise DegirumException(f"Platform [{self._current_os}] not supported for script [{installer_file}]")
        except subprocess.CalledProcessError as e:
            raise DegirumException(f"Script failed with exit code {e.returncode}")

    def install_latest(self, runtime_name: str, driver: Optional[bool] = False):
        """
        Runs installer for latest version of a runtime

        Args:
            runtime_name: name of runtime to install
            driver: flag to enable DRIVER mode of install script
        """

        version_list = self.list_versions(runtime_name)
        if len(version_list) == 0:
            raise DegirumException(f"Runtime [{runtime_name}] has no versions listed for OS [{self._current_os}].")

        # Topmost listed version should always be most recent
        latest_version = version_list[0]

        self.install_one(runtime_name, latest_version, driver)


####################################################################################################


def installer_entrypoint(args: argparse.Namespace):
    """
    Entrypoint for CLI, CMake, and Dockerfile

    Args:
        args: argparse object containing CLI args
    """

    installer = RuntimeInstaller(args.path) if args.path else RuntimeInstaller()

    # Handle "install-runtime --list"
    # Print list of available runtimes
    if args.list:
        # Handle "install-runtime plugin_name --list"
        if args.plugin_name:
            available_runtimes = [args.plugin_name] if args.plugin_name in installer.list_runtimes() else []
        else:
            available_runtimes = installer.list_runtimes()
        for runtime in available_runtimes:
            print(f"{runtime}:")
            runtime_versions = installer.list_versions(runtime)
            for version in runtime_versions:
                print(f"    {version}")
        return

    # Handle "--cmake_list"
    if args.plugin_name and args.cmake_list:
        installer.print_versions(args.plugin_name)
        return

    # Handle "install-runtime <no args>"
    # Trigger --help command
    if (not args.plugin_name) and (not args.plugin_versions):
        args._parser.print_help()
        return

    # Handle "install-runtime plugin_name"
    # Run installer for latest version
    if args.plugin_name and (not args.plugin_versions):
        installer.install_latest(args.plugin_name, args.driver)
        return

    # Handle "install-runtime plugin_name <plugin_versions>"
    # Run installer for specified version(s)
    if args.plugin_name and args.plugin_versions:

        # Handle "install-runtime plugin_name ALL"
        if "ALL" in args.plugin_versions:
            selected_versions = installer.list_versions(args.plugin_name) if (args.plugin_name in installer.list_runtimes()) else []
        else:
            selected_versions = args.plugin_versions

        # Driver flag only valid when num_versions == 1
        driver_flag = args.driver if len(selected_versions) == 1 else False

        # Run installers
        for version in selected_versions:
            installer.install_one(args.plugin_name, version, driver_flag)
        return


# Entrypoint for degirum CLI
def _install_runtime_args(parser: argparse.ArgumentParser):
    """
    Define install subcommand arguments

    Args:
        parser: argparse parser object to be stuffed with args
    """

    parser.add_argument('plugin_name', nargs='?', help='Name of the plugin')
    parser.add_argument('plugin_versions', nargs='*', help='One or more plugin versions, or leave blank for latest')
    parser.add_argument('--list', action='store_true', help='List available plugins and versions')
    parser.add_argument('--cmake_list', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--driver', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--path', help=argparse.SUPPRESS)

    parser.set_defaults(func=installer_entrypoint, _parser=parser)


# Entrypoint for CMake and Dockerfile
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeGirum runtime installer")
    _install_runtime_args(parser)
    args = parser.parse_args()
    args.func(args)
