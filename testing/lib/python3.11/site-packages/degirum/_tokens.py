#
# _tokens.py - DeGirum Python SDK: cloud tokens management
# Copyright DeGirum Corp. 2024
#
# Contains DeGirum cloud tokens management implementation
#

from typing import Union
import time, threading, os, json, copy, yaml, datetime, secrets, webbrowser, socket, urllib, argparse
from ._misc import default_cloud_server, get_app_data_dir, cloud_server_request
from .exceptions import DegirumException


class TokenManager:

    _lock = threading.Lock()  # global lock for thread safety

    # JSON keys
    key_token = "token"
    key_desc = "description"
    key_created_at = "created_at"
    key_expiration = "expiration"
    key_user = "user"
    key_space = "space"
    key_error = "error"

    def __init__(self, cloud_url=default_cloud_server):
        """
        Initialize a cloud token manager.

        Args:
            cloud_url: cloud server URL to work with
        """

        self._cloud_url = cloud_url
        self._token_info: dict = {}
        self._token_file_path = os.path.join(
            get_app_data_dir(), "pysdk_cloud_token.json"
        )
        self._token_load()

    def token_get(self) -> str:
        """
        Get currently loaded cloud token value and renew it if needed.

        Returns:
            str: cloud token string.
        """

        infinite_expiration = "0001-01-01T00:00:00"

        with TokenManager._lock:
            token_str = self._token_str_get()
            if token_str:
                # query cloud for token info
                info = self._token_cloud_info_get(token_str)
                if isinstance(info, str):
                    return token_str  # in case of error, just return token

                # check expiration
                expiration_str = info.get(self.key_expiration, "")
                if expiration_str and infinite_expiration not in expiration_str:
                    expiration_dt = datetime.datetime.fromisoformat(
                        expiration_str.replace("Z", "").split(".")[0] + "+00:00"
                    )
                    if expiration_dt <= datetime.datetime.now(
                        datetime.timezone.utc
                    ) + datetime.timedelta(hours=1):
                        # token is to be expired, renew it
                        try:
                            new_token = self._token_renew_do(token_str)
                            token_str = new_token
                        except Exception:
                            pass  # ignore renew errors

            return token_str

    def token_info_get(self, local_only: bool) -> dict:
        """
        Get currently loaded cloud token info.

        Args:
            local_only: if True, do not connect to cloud server, just return local token info

        Returns:
            dict: cloud token info.
        """

        with TokenManager._lock:
            token_str = self._token_str_get()
            ret = copy.deepcopy(self._token_info)

            if not local_only and token_str:
                info = self._token_cloud_info_get(token_str)

                if isinstance(info, dict):
                    # delete all keys from info not in keys set
                    keys = {
                        self.key_desc,
                        self.key_created_at,
                        self.key_expiration,
                        self.key_user,
                        self.key_space,
                    }
                    info = {k: v for k, v in info.items() if k in keys}
                    ret.update(info)
                else:
                    ret[self.key_error] = info

            return ret

    def token_install(self, token_str: str, local_only: bool):
        """
        Save a cloud token into local storage.

        Args:
            token: cloud token string.
            local_only: if True, do not connect to cloud server, just save token locally
        """
        if not token_str:
            raise DegirumException("Cannot install token: empty token string")
        with TokenManager._lock:
            self._save_token_to_file(token_str, local_only)

    def token_create(self):
        """
        Create a new cloud token and save it to local storage.
        """

        # create shared secret (random string)
        shared_secret = secrets.token_urlsafe(32)

        # define message to be shown in the browser
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        message = (
            f"New token is created by PySDK CLI request from host {hostname} ({ip_address})."
            " You can close this tab and return to PySDK CLI - your new token should be already installed by now."
        )

        # try to launch browser to request token creation
        short_url = f"{self._cloud_url}/create_token?seed={shared_secret}"
        url = short_url + f"&message={urllib.parse.quote(message)}"
        try:
            controller = webbrowser.get()
            controller.open(url, new=2)
            print(
                "\nToken creation link is now opened in your browser.\n"
                "Please login to DeGirum AI Hub.\n"
                "New token will be created for you after successful login."
            )
        except Exception:
            print(
                f"Please open {short_url} link\n"
                "in any browser on any device to login to DeGirum AI Hub.\n"
                "New token will be created for you after successful login."
            )

        print("Waiting for token creation...")

        self._token_pick_and_save(shared_secret)
        print("New token is successfully created and installed on your system.")

    def token_renew(self):
        """
        Renew installed cloud token and save it to local storage.
        """
        with TokenManager._lock:
            token_str = self._token_str_get()
            if not token_str:
                raise DegirumException("Cannot renew token: no token installed")

            self._token_renew_do(token_str)

    def token_clear(self):
        """
        Clear a cloud token from local storage.
        """
        with TokenManager._lock:
            self._save_token_to_file("")

    def _token_str_get(self) -> str:
        """
        Get currently loaded cloud token string.
        Returns:
            str: cloud token string.
        """
        return self._token_info.get(self.key_token, "")

    def _save_token_to_file(self, token: str, local_only: bool = False):
        """
        Save token file to disk. Internal method: does not take lock.

        Args:
            token: cloud token to save.
            local_only: if True, do not connect to cloud server, just save token locally
        """

        if token:
            self._token_info = {self.key_token: token}
            if not local_only:
                cloud_info = self._token_cloud_info_get(token)
                if isinstance(cloud_info, dict):
                    self._token_info.update(cloud_info)
        else:
            self._token_info = {}

        app_data_dir = get_app_data_dir()
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)

        try:
            with open(self._token_file_path, "r") as f:
                token_file_contents = json.loads(f.read())
        except Exception:
            token_file_contents = {}  # ignore ill-formatted or absent files

        token_file_contents[self._cloud_url] = self._token_info

        with open(self._token_file_path, "w") as f:
            f.write(json.dumps(token_file_contents, indent=2))

    def _token_load(self):
        """
        Load a cloud token info from local storage.

        """

        with TokenManager._lock:
            try:
                if os.path.exists(self._token_file_path):
                    with open(self._token_file_path, "r") as f:
                        token_file_contents = json.loads(f.read())
                        self._token_info = token_file_contents.get(self._cloud_url, {})
                else:
                    self._token_info = {}
            except Exception:
                self._token_info = {}

    def _token_cloud_info_get(self, token_str: str) -> Union[dict, str]:
        """
        Query info about the currently installed token from cloud

        Args:
            token_str: cloud token string to query info for.

        Returns:
            dict: cloud token info
            str: error message if query failed
        """

        try:
            return cloud_server_request(
                base_url=self._cloud_url, api_url=f"/api/v1/tokens/{token_str}/info"
            )
        except Exception as e:
            return str(e)

    def _token_renew_do(self, old_token: str) -> str:
        """
        Renew an expired cloud token and save it to local storage.

        Args:
            old_token: cloud token string to renew.

        Returns:
            str: new cloud token string.
        """

        result = cloud_server_request(
            base_url=self._cloud_url,
            api_url=f"/api/v1/tokens/{old_token}/refresh",
            method="PATCH",
        )

        new_token = result.get("value")
        if not new_token:
            raise DegirumException(
                f"Cannot renew token: no new token returned; cloud response: {result}"
            )

        self._save_token_to_file(new_token)
        return new_token

    def _token_pick_and_save(self, shared_secret: str, tries: int = -1):
        """
        Pick token from cloud and save it to local storage.
        """

        token_str = ""
        while tries != 0:
            # wait until token is created
            try:
                ret = cloud_server_request(
                    base_url=self._cloud_url,
                    api_url="/api/v1/tokens-seed/pick",
                    method="POST",
                    data={"seed": shared_secret},
                )
                token_str = ret.get(self.key_token)
                break
            except Exception:
                time.sleep(1)

            if tries > 0:
                tries -= 1

        if token_str:
            with TokenManager._lock:
                self._save_token_to_file(token_str)

        return token_str


def _token_manage(args):
    """
    Execute token command

    Args:
        args: argparse command line arguments
    """

    token_manager = TokenManager(args.cloud_url)

    if args.command == "status":
        print(yaml.dump(token_manager.token_info_get(args.local), sort_keys=False))
    elif args.command == "install":
        token_manager.token_install(args.token, args.local)
        print("Token is successfully installed on your system")
    elif args.command == "create":
        token_manager.token_create()
    elif args.command == "renew":
        token_manager.token_renew()
        print("Token is successfully renewed and saved to your system")
    elif args.command == "clear":
        token_manager.token_clear()
        print("Token is successfully cleared from your system")


def _token_args(parser):
    """
    Define token subcommand arguments

    Args:
        parser: argparse parser object to be stuffed with args

    """

    parser.add_argument(
        "command",
        nargs="?",
        choices=["status", "install", "create", "renew", "clear"],
        default="status",
        help=(
            "token command: show token status, install a token into the system, create new token,"
            " renew expired token (default is 'status'), clear installed token from the system"
        ),
    )

    parser.add_argument(
        "--token",
        default="",
        help="[install] token string to install",
    )

    parser.add_argument(
        "--cloud_url",
        default=default_cloud_server,
        help=f"cloud server URL to operate with (default is {default_cloud_server})",
    )

    parser.add_argument(
        "--local",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    parser.set_defaults(func=_token_manage)
