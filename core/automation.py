"""
core/automation.py
──────────────────
All automation functions refactored from the original Jupyter notebook.
Handles CUCM DNs with \+ prefix (e.g. \+19786007919).
Internal extensions (e.g. 60012) do NOT get \+ prefix.
"""

from zeep import helpers
from zeep.exceptions import Fault
from core.axl_client import get_axl_service

JABBER_TYPE_MAP = {
    "CSF": "Unified Client Services Framework",
    "TCT": "Dual Mode for iPhone",
    "BOT": "Dual Mode for Android",
    "TAB": "Cisco Jabber for Tablet",
}


def _normalize_dn(dn: str) -> str:
    """Strip leading \\+ or + from user input, return digits only."""
    return dn.lstrip("\\").lstrip("+")


def _search_pattern(dn: str) -> str:
    """Build AXL wildcard search pattern: %<digits>"""
    digits = _normalize_dn(dn)
    return "%" + digits


def _full_dn(dn: str) -> str:
    """Build full E.164 DN with \\+ prefix — only for external numbers."""
    digits = _normalize_dn(dn)
    return "\\+" + digits


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Resolve Mirror DN to device names
# ════════════════════════════════════════════════════════════════════════════

def get_mirror_devices(mirror_dn: str):
    axl = get_axl_service()

    resp = axl.listRoutePlan(
        searchCriteria={"dnOrPattern": _search_pattern(mirror_dn)},
        returnedTags={"routeDetail": ""}
    )

    data = helpers.serialize_object(resp)
    route_plans = data.get("return", {}).get("routePlan", []) or []

    if not route_plans:
        raise RuntimeError(f"No route plan found for Mirror DN: {mirror_dn}")

    device_names = []
    for item in route_plans:
        if isinstance(item, dict):
            detail = item.get("routeDetail")
        else:
            detail = getattr(item, "routeDetail", None)
        if detail:
            device_names.append(str(detail))

    mirror_phone = next((i for i in device_names if i.startswith("SEP")), None)
    mirror_j4w   = next((i for i in device_names if i.startswith("CSF")), None)

    return mirror_phone, mirror_j4w


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — Get Route Partition for the Mirror DN
# ════════════════════════════════════════════════════════════════════════════

def get_line_pt(mirror_dn: str) -> str:
    axl = get_axl_service()

    try:
        resp = axl.listRoutePlan(
            searchCriteria={"dnOrPattern": _search_pattern(mirror_dn)},
            returnedTags={"partition": ""}
        )
        data = helpers.serialize_object(resp)
        route_plans = data.get("return", {}).get("routePlan", []) or []
        if not route_plans:
            raise RuntimeError(f"No partition found for DN: {mirror_dn}")

        first = route_plans[0]
        if isinstance(first, dict):
            pt = (first.get("partition") or {}).get("_value_1") or ""
        else:
            pt = getattr(getattr(first, "partition", None), "_value_1", "") or ""

        return pt

    except (Fault, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Failed to get partition for {mirror_dn}: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — Get Line Configuration from Mirror DN
# ════════════════════════════════════════════════════════════════════════════

def get_line_config(mirror_dn: str) -> dict:
    axl = get_axl_service()

    try:
        resp = axl.getLine(pattern=_full_dn(mirror_dn), routePartitionName="INTERNAL-PT")
        data = helpers.serialize_object(resp)
        line = data.get("return", {}).get("line", {}) or {}

        line_css    = (line.get("shareLineAppearanceCssName") or {}).get("_value_1") or ""
        vm_profile  = (line.get("voiceMailProfileName")       or {}).get("_value_1") or ""
        line_fwdcss = ((line.get("callForwardAll") or {}).get("callingSearchSpaceName") or {}).get("_value_1") or ""

        return {
            "line_css":    line_css,
            "vm_profile":  vm_profile,
            "line_fwdcss": line_fwdcss,
        }

    except Fault as e:
        err = str(e)
        if "The specified Line was not found" in err:
            raise RuntimeError(f"Mirror DN '{mirror_dn}' not found in CUCM.")
        elif "INTERNAL-PT" in err:
            raise RuntimeError(f"Partition 'INTERNAL-PT' not found in CUCM.")
        else:
            raise RuntimeError(f"AXL error getting line config: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — Get Phone Configuration from Mirror Device
# ════════════════════════════════════════════════════════════════════════════

def get_phone_config(mirror_device: str) -> dict:
    axl = get_axl_service()

    try:
        resp = axl.getPhone(name=mirror_device)
        data = helpers.serialize_object(resp)
        phone = data.get("return", {}).get("phone", {}) or {}

        model_raw      = phone.get("model") or ""
        phone_model    = model_raw[6:] if model_raw.startswith("Cisco ") else model_raw
        phone_protocol = phone.get("protocol") or "SIP"
        phone_dp       = (phone.get("devicePoolName")        or {}).get("_value_1") or ""
        phone_css      = (phone.get("callingSearchSpaceName") or {}).get("_value_1") or ""
        phone_loc      = (phone.get("locationName")           or {}).get("_value_1") or ""
        phone_mrgl     = (phone.get("mediaResourceListName")  or {}).get("_value_1") or ""

        line_mask = ""
        lines     = phone.get("lines") or {}
        line_list = lines.get("line") or []
        if isinstance(line_list, dict):
            line_list = [line_list]
        if line_list:
            mask = (line_list[0] or {}).get("e164Mask") or ""
            if mask and "X" in str(mask):
                line_mask = mask

        return {
            "phone_model":    phone_model,
            "phone_protocol": phone_protocol,
            "phone_dp":       phone_dp,
            "phone_css":      phone_css,
            "phone_loc":      phone_loc,
            "phone_mrgl":     phone_mrgl,
            "line_mask":      line_mask,
        }

    except Fault as e:
        raise RuntimeError(f"Failed to get phone config for {mirror_device}: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 5 — Add or Update Line (DN)
# ════════════════════════════════════════════════════════════════════════════

def add_line_config(new_dn: str, line_pt: str, full_name: str,
                    vm_enable: bool, line_css: str, vm_profile: str,
                    line_fwdcss: str) -> str:
    axl = get_axl_service()
    vm_tick = str(vm_enable).lower()

    line_payload = {
        "pattern":                    new_dn,
        "usage":                      "Device",
        "routePartitionName":         line_pt,
        "description":                full_name,
        "alertingName":               full_name,
        "asciiAlertingName":          full_name,
        "shareLineAppearanceCssName": line_css,
        "voiceMailProfileName":       vm_profile,
        "callForwardAll":             {"callingSearchSpaceName": line_fwdcss},
        "callForwardBusy":            {"forwardToVoiceMail": vm_tick},
        "callForwardBusyInt":         {"forwardToVoiceMail": vm_tick},
        "callForwardNoAnswer":        {"forwardToVoiceMail": vm_tick},
        "callForwardNoAnswerInt":     {"forwardToVoiceMail": vm_tick},
    }

    try:
        axl.addLine(line=line_payload)
        return "added"
    except Fault as e:
        err = str(e)
        if "Number Invalid" in err:
            raise RuntimeError(f"DN '{new_dn}' is invalid.")
        elif "A DN exist" in err:
            try:
                axl.updateLine(
                    pattern=new_dn,
                    routePartitionName=line_pt,
                    description=full_name,
                    alertingName=full_name,
                    asciiAlertingName=full_name,
                )
                return "updated"
            except Fault as ue:
                raise RuntimeError(f"DN update failed: {ue}")
        else:
            raise RuntimeError(f"AXL error adding line: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 6 — Add or Update Physical Phone (SEP)
# ════════════════════════════════════════════════════════════════════════════

def add_phone_config(phone_mac: str, phone_model: str, phone_protocol: str,
                     phone_css: str, phone_dp: str, phone_loc: str,
                     phone_mrgl: str, full_name: str, user_id: str,
                     new_dn: str, line_pt: str, line_mask: str) -> str:
    axl = get_axl_service()
    mac_upper = phone_mac.upper()

    phone_payload = {
        "name":               f"SEP{mac_upper}",
        "description":        full_name,
        "product":            f"Cisco {phone_model}",
        "class":              "Phone",
        "protocol":           phone_protocol,
        "callingSearchSpaceName": phone_css,
        "devicePoolName":     phone_dp,
        "locationName":       phone_loc,
        "mediaResourceListName": phone_mrgl,
        "ownerUserName":      user_id,
        "securityProfileName": f"Cisco {phone_model} - Standard {phone_protocol} Non-Secure Profile",
        "commonPhoneConfigName": "Standard Common Phone Profile",
        "phoneTemplateName":  f"Standard {phone_model} {phone_protocol}",
        "softkeyTemplateName": "Standard User",
        "enableExtensionMobility": "true",
        "lines": {
            "line": {
                "index":        "1",
                "display":      full_name,
                "displayAscii": full_name,
                "label":        full_name,
                "e164Mask":     line_mask,
                "dirn": {
                    "pattern":            new_dn,
                    "routePartitionName": line_pt,
                },
                "associatedEndusers": {"enduser": user_id},
            }
        },
    }

    try:
        axl.addPhone(phone=phone_payload)
        return "added"
    except Fault as e:
        err = str(e)
        if "invalid characters" in err:
            raise RuntimeError(f"Phone MAC '{phone_mac}' has invalid characters.")
        elif "not found" in err:
            raise RuntimeError(f"Phone model 'Cisco {phone_model}' not found in CUCM.")
        elif "duplicate value" in err:
            try:
                axl.updatePhone(
                    name=f"SEP{mac_upper}",
                    description=full_name,
                    ownerUserName=user_id,
                    lines={
                        "line": {
                            "index":        "1",
                            "display":      full_name,
                            "displayAscii": full_name,
                            "label":        full_name,
                            "e164Mask":     line_mask,
                            "dirn": {
                                "pattern":            new_dn,
                                "routePartitionName": line_pt,
                            },
                            "associatedEndusers": {"enduser": user_id},
                        }
                    },
                )
                return "updated"
            except Fault as ue:
                raise RuntimeError(f"Phone update failed: {ue}")
        else:
            raise RuntimeError(f"AXL error adding phone: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 7 — Add or Update Jabber Client
# ════════════════════════════════════════════════════════════════════════════

def add_jabber_config(jabber_model: str, user_id: str, full_name: str,
                      phone_css: str, phone_dp: str, phone_loc: str,
                      phone_mrgl: str, new_dn: str, line_pt: str,
                      line_mask: str) -> str:
    axl = get_axl_service()
    jm = jabber_model.upper()

    if jm not in JABBER_TYPE_MAP:
        raise RuntimeError(f"Invalid jabber_model '{jabber_model}'. Must be CSF, TCT, BOT, or TAB.")

    jabber_type = JABBER_TYPE_MAP[jm]
    device_name = f"{jm}{user_id}"

    jabber_payload = {
        "name":               device_name,
        "description":        full_name,
        "product":            f"Cisco {jabber_type}",
        "class":              "Phone",
        "protocol":           "SIP",
        "callingSearchSpaceName": phone_css,
        "devicePoolName":     phone_dp,
        "locationName":       phone_loc,
        "ownerUserName":      user_id,
        "mediaResourceListName": phone_mrgl,
        "securityProfileName": f"Cisco {jabber_type} - Standard SIP Non-Secure Profile",
        "commonPhoneConfigName": "Standard Common Phone Profile",
        "lines": {
            "line": {
                "index":        "1",
                "display":      full_name,
                "displayAscii": full_name,
                "label":        full_name,
                "e164Mask":     line_mask,
                "dirn": {
                    "pattern":            new_dn,
                    "routePartitionName": line_pt,
                },
                "associatedEndusers": {"enduser": user_id},
            }
        },
    }

    try:
        axl.addPhone(phone=jabber_payload)
        return "added"
    except Fault as e:
        err = str(e)
        if "not found" in err:
            raise RuntimeError(f"Jabber type 'Cisco {jabber_type}' not found in CUCM.")
        elif "duplicate value" in err:
            try:
                axl.updatePhone(
                    name=device_name,
                    description=full_name,
                    ownerUserName=user_id,
                    lines={
                        "line": {
                            "index":        "1",
                            "display":      full_name,
                            "displayAscii": full_name,
                            "label":        full_name,
                            "e164Mask":     line_mask,
                            "dirn": {
                                "pattern":            new_dn,
                                "routePartitionName": line_pt,
                            },
                            "associatedEndusers": {"enduser": user_id},
                        }
                    },
                )
                return "updated"
            except Fault as ue:
                raise RuntimeError(f"Jabber update failed: {ue}")
        else:
            raise RuntimeError(f"AXL error adding Jabber device: {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 8 — Update End User
# ════════════════════════════════════════════════════════════════════════════

def update_user(user_id: str, jabber_model: str) -> None:
    axl = get_axl_service()
    jm = jabber_model.upper()
    device_name = f"{jm}{user_id}"

    try:
        axl.updateUser(
            userid=user_id,
            pin="54321",
            homeCluster="true",
            imAndPresenceEnable="true",
            serviceProfile="Jabber Service Profile - Agent Dropped Calls",
            associatedDevices={"device": device_name},
            enableCti="true",
            enableEmcc="true",
            enableMobility="true",
            enableMobileVoiceAccess="true",
            associatedGroups={
                "userGroup": {
                    "name":      "Insulet LDAP User",
                    "userRoles": {"userRole": "Insulet IT LDAP User"},
                }
            },
        )
    except Fault as e:
        raise RuntimeError(f"Failed to update end user '{user_id}': {e}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 9 — Set Primary Extension
# ════════════════════════════════════════════════════════════════════════════

def update_user_pri_dn(user_id: str, dn: str, line_pt: str) -> None:
    """
    Set primary extension for end user.
    dn is used as-is — do NOT add \\+ prefix for internal extensions.
    """
    axl = get_axl_service()

    try:
        axl.updateUser(
            userid=user_id,
            primaryExtension={
                "pattern":            dn,
                "routePartitionName": line_pt,
            },
        )
    except Fault as e:
        raise RuntimeError(f"Failed to set primary DN for '{user_id}': {e}")
