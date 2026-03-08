import os
import json
import stripe as stripe_lib
import urllib.request

_cached_keys = None


def _get_credentials():
    global _cached_keys
    if _cached_keys:
        return _cached_keys

    live_secret = os.environ.get("STRIPE_LIVE_SECRET_KEY", "")
    live_publishable = os.environ.get("STRIPE_LIVE_PUBLISHABLE_KEY", "")
    if live_secret and live_publishable:
        _cached_keys = {"publishable_key": live_publishable, "secret_key": live_secret}
        return _cached_keys

    hostname = os.environ.get("REPLIT_CONNECTORS_HOSTNAME")
    repl_identity = os.environ.get("REPL_IDENTITY")
    web_repl_renewal = os.environ.get("WEB_REPL_RENEWAL")

    if repl_identity:
        token = f"repl {repl_identity}"
    elif web_repl_renewal:
        token = f"depl {web_repl_renewal}"
    else:
        raise RuntimeError("No Replit identity token available for Stripe connection")

    is_production = os.environ.get("REPLIT_DEPLOYMENT") == "1"
    envs_to_try = ["production", "development"] if is_production else ["development"]

    for target_env in envs_to_try:
        url = f"https://{hostname}/api/v2/connection?include_secrets=true&connector_names=stripe&environment={target_env}"

        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Replit-Token": token,
        })

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        items = data.get("items", [])
        if not items:
            continue

        settings = items[0].get("settings", {})
        publishable = settings.get("publishable")
        secret = settings.get("secret")

        if publishable and secret:
            break
    else:
        raise RuntimeError("Stripe connection not found (tried production and development)")

    _cached_keys = {"publishable_key": publishable, "secret_key": secret}
    return _cached_keys


def get_stripe_client():
    creds = _get_credentials()
    stripe_lib.api_key = creds["secret_key"]
    return stripe_lib


def get_publishable_key():
    creds = _get_credentials()
    return creds["publishable_key"]


def get_webhook_secret():
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "")
