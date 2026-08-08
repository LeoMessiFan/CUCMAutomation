"""
core/axl_client.py
──────────────────
Initialises and returns the Cisco AXL SOAP service object (axl).
Call get_axl_service() once per job — Zeep caches the WSDL internally.
"""

from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client
from zeep.transports import Transport
from zeep.cache import SqliteCache
from zeep.plugins import HistoryPlugin
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

from config import Config

disable_warnings(InsecureRequestWarning)

# Module-level cache — reuse the same client across requests
_client = None
_axl    = None
history = HistoryPlugin()


def get_axl_service():
    """
    Returns the AXL service proxy.
    Raises RuntimeError if WSDL is missing or credentials are empty.
    """
    global _client, _axl

    if _axl is not None:
        return _axl

    if not Config.AXL_FQDN:
        raise RuntimeError("AXL_FQDN is not configured. Check your .env file.")
    if not Config.AXL_PASSWORD:
        raise RuntimeError("AXL_PASSWORD is not configured. Check your .env file.")

    session = Session()
    session.verify = False
    session.auth = HTTPBasicAuth(Config.AXL_USERNAME, Config.AXL_PASSWORD)

    transport = Transport(
        cache=SqliteCache(),
        session=session,
        timeout=Config.AXL_TIMEOUT
    )

    _client = Client(
        wsdl=Config.WSDL_PATH,
        transport=transport,
        plugins=[history]
    )
    _axl = _client.create_service(Config.AXL_BINDING, Config.AXL_ADDRESS)
    return _axl
