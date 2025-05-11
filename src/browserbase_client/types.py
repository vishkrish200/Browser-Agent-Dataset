from typing import List, Dict, Any, Literal, Union, TypedDict

# For Python versions < 3.11, Unpack is in typing_extensions
# from typing_extensions import Unpack
# For Python 3.11+
# from typing import Unpack

# Using total=False for all TypedDicts to indicate all keys are optional,
# as per typical API request body patterns where not all fields are required.

class ViewportDict(TypedDict, total=False):
    width: int
    height: int

class ScreenDict(TypedDict, total=False):
    maxWidth: int
    maxHeight: int
    minWidth: int
    minHeight: int

class FingerprintDict(TypedDict, total=False):
    httpVersion: Literal['1', '2']
    browsers: List[Literal['chrome', 'edge', 'firefox', 'safari']]
    devices: List[Literal['desktop', 'mobile']]
    locales: List[str]
    operatingSystems: List[Literal['android', 'ios', 'linux', 'macos', 'windows']]
    screen: ScreenDict

class BrowserContextDict(TypedDict, total=False):
    id: str
    persist: bool

class BrowserSettingsDict(TypedDict, total=False):
    context: BrowserContextDict
    extensionId: str # Also a top-level CreateSessionKwargs param
    fingerprint: FingerprintDict
    viewport: ViewportDict
    blockAds: bool
    solveCaptchas: bool
    recordSession: bool # Not explicitly in provided API docs, but good to anticipate
    logSession: bool    # Not explicitly in provided API docs, but good to anticipate
    advancedStealth: bool

# Placeholder for detailed custom proxy configurations if available from Browserbase docs later
# For now, can be a generic dict or a more specific common structure if known.
class CustomProxyConfigDict(TypedDict, total=False):
    # Example fields if known, e.g.:
    # server: str
    # port: int
    # username: Optional[str]
    # password: Optional[str]
    # type: Literal['http', 'https', 'socks5']
    pass # Keep as a generic dict for now if structure is unknown

# Top-level keyword arguments for the create_session API call
class CreateSessionKwargs(TypedDict, total=False):
    # projectId is a direct parameter to create_session, not in kwargs
    extensionId: str # Can also be under browserSettings.extensionId as per some API designs
    browserSettings: BrowserSettingsDict
    timeout: int
    keepAlive: bool
    proxies: Union[bool, List[CustomProxyConfigDict]] # bool for default, list for custom
    region: Literal['us-west-2', 'us-east-1', 'eu-central-1', 'ap-southeast-1']
    userMetadata: Dict[str, Any] 