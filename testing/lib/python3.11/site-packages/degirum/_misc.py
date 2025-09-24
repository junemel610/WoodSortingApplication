#
# _misc.py - DeGirum Python SDK: miscellaneous utilities
# Copyright DeGirum Corp. 2024
#
# Contains miscellaneous utilities implementation
#

import json, os, platform, requests, copy
from typing import Optional
from requests.adapters import HTTPAdapter, Retry
from degirum.exceptions import DegirumException
from ._version import pysdk_version

# default cloud server hostname
default_cloud_server_hostname = "hub.degirum.com"

# default cloud server URL
default_cloud_server = f"https://{default_cloud_server_hostname}"


def get_app_data_dir() -> str:
    """
    Returns the path to the user profile application data directory.
    Platform independent:
    - On Windows, it uses %APPDATA%.
    - On Linux, it uses ~/.local/share.

    Returns:
        str: Path to the application data directory.
    """
    if platform.system() == "Windows":
        appdata_dir = os.getenv("APPDATA")
        if not appdata_dir:
            raise OSError("Environment variable APPDATA is not set")
        return os.path.join(appdata_dir, "DeGirum")
    elif platform.system() in {
        "Linux",
        "Darwin",
    }:  # Darwin for macOS, similar handling to Linux
        return os.path.expanduser("~/.local/share/DeGirum")
    else:
        raise OSError("Unsupported operating system")


def cloud_server_request(
    base_url: str,
    api_url: str,
    *,
    token: Optional[str] = None,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    timeout_s: float = 5.0,
    is_octet_stream: bool = False,
    no_returns: bool = False,
):
    """Perform request to cloud server

    Args:
        base_url: cloud server base url
        api_url: api request url (path)
        token: cloud token to access the cloud server
        method: request method (GET, POST, PUT, DELETE etc.)
        data: request data dictionary
        params: request parameters dictionary
        headers: header parameters dictionary
        timeout_s: request timeout in seconds
        is_octet_stream: true to request binary data, false to request JSON
        no_returns: true to ignore response content (do not parse)

    Returns:
        response parsed JSON (when is_octet_stream is False) or binary content otherwise
    """

    host = base_url.split("://")[-1]

    try:
        retries = Retry(total=3)  # the number of retries for http/https requests
        s = requests.Session()
        for m in ["https://", "http://"]:
            s.mount(m, HTTPAdapter(max_retries=retries))

        headers = {} if headers is None else copy.copy(headers)
        headers["dg_version"] = pysdk_version
        if token:
            headers["token"] = token
        if is_octet_stream:
            headers["accept"] = "application/octet-stream"

        res = s.request(
            method,
            f"{base_url}{api_url}",
            params=params,
            json=data,
            headers=headers,
            timeout=timeout_s,
        )
    except requests.RequestException as e:
        raise DegirumException(f"Unable to access server {host}: {e}") from None
    if res.status_code == 401:
        response = res.json()
        reason = (
            response["detail"]
            if response and isinstance(response, dict) and "detail" in response
            else "invalid token value"
        )
        raise DegirumException(f"Unable to connect to server {host}: {reason}")

    try:
        res.raise_for_status()
    except requests.RequestException as e:
        details = str(e)
        try:
            j = res.json()
            if "detail" in j:
                details = f"{j['detail']}. (cloud server response: {str(e)})"
        except json.JSONDecodeError:
            pass
        raise DegirumException(details) from None

    if no_returns:
        return None

    if is_octet_stream:
        return res.content
    else:
        try:
            return res.json()
        except json.JSONDecodeError:
            raise DegirumException(
                f"Unable to parse response from server {host}: {res}"
            ) from None
