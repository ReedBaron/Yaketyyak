from flask import Flask, render_template, send_from_directory, request, jsonify, redirect
import os
import json
import hmac
import hashlib

from db import init_db, get_user_by_license_key, get_user_by_email, get_user_by_stripe_customer, create_user, update_user_status, update_user_subscription, log_usage, get_monthly_usage
from pro_api import generate_license_key, validate_license_key, check_rate_limit, cloud_translate
from stripe_client import get_stripe_client, get_publishable_key, get_webhook_secret

app = Flask(__name__)

init_db()

MONTHLY_PRICE_ID = os.environ.get("STRIPE_MONTHLY_PRICE_ID", "")
YEARLY_PRICE_ID = os.environ.get("STRIPE_YEARLY_PRICE_ID", "")


@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["X-Frame-Options"] = "ALLOWALL"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://*.replit.dev https://*.repl.co https://*.replit.app"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/success")
def success_page():
    session_id = request.args.get("session_id", "")
    return render_template("success.html", session_id=session_id)


@app.route("/getting-started")
def getting_started_page():
    return render_template("getting-started.html")


@app.route("/account")
def account_page():
    return render_template("account.html")


@app.route("/api/config")
def api_config():
    try:
        pk = get_publishable_key()
    except Exception:
        pk = ""
    return jsonify({
        "publishable_key": pk,
        "monthly_price_id": MONTHLY_PRICE_ID,
        "yearly_price_id": YEARLY_PRICE_ID,
    })


@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json()
    plan = data.get("plan", "monthly")
    email = data.get("email", "")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    price_id = MONTHLY_PRICE_ID if plan == "monthly" else YEARLY_PRICE_ID
    if not price_id:
        return jsonify({"error": f"Price ID for {plan} plan not configured"}), 500

    try:
        stripe = get_stripe_client()

        host = request.headers.get("Host", "localhost:5000")
        scheme = "https" if "replit" in host or "repl" in host else request.scheme

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            customer_email=email,
            success_url=f"{scheme}://{host}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{scheme}://{host}/#download",
            metadata={"plan": plan},
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/checkout/success", methods=["GET"])
def api_checkout_success():
    session_id = request.args.get("session_id", "")
    if not session_id:
        return jsonify({"error": "No session ID"}), 400

    try:
        stripe = get_stripe_client()
        session = stripe.checkout.Session.retrieve(session_id)

        if session.status != "complete":
            return jsonify({"error": "Payment not completed"}), 400

        if session.payment_status not in ("paid", "no_payment_required"):
            return jsonify({"error": "Payment not confirmed"}), 400

        customer_id = session.customer
        subscription_id = session.subscription

        if not customer_id or not subscription_id:
            return jsonify({"error": "Invalid checkout session — missing customer or subscription"}), 400

        sub = stripe.Subscription.retrieve(subscription_id)
        if sub.status not in ("active", "trialing"):
            return jsonify({"error": f"Subscription is not active (status: {sub.status})"}), 400

        email = session.customer_email or ""
        if hasattr(session, "customer_details") and session.customer_details:
            email = email or getattr(session.customer_details, "email", "")
        plan_meta = session.metadata.get("plan", "monthly") if session.metadata else "monthly"
        plan = f"pro_{plan_meta}"

        existing = get_user_by_stripe_customer(customer_id)
        if existing:
            license_key = existing["license_key"]
            update_user_subscription(customer_id, subscription_id, plan)
        else:
            license_key = generate_license_key()
            create_user(email, customer_id, subscription_id, license_key, plan)

        return jsonify({
            "license_key": license_key,
            "email": email,
            "plan": plan,
            "status": "active",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/webhook", methods=["POST"])
def api_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    webhook_secret = get_webhook_secret()
    if not webhook_secret:
        return jsonify({"error": "Webhook secret not configured"}), 500

    try:
        stripe = get_stripe_client()
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "customer.subscription.updated":
        customer_id = data_obj.get("customer", "")
        status = data_obj.get("status", "")
        sub_id = data_obj.get("id", "")

        if status in ("active", "trialing"):
            update_user_status(customer_id, "active")
        elif status in ("past_due", "unpaid"):
            update_user_status(customer_id, "past_due")
        elif status in ("canceled", "incomplete_expired"):
            update_user_status(customer_id, "canceled")

        update_user_subscription(customer_id, sub_id)

    elif event_type == "customer.subscription.deleted":
        customer_id = data_obj.get("customer", "")
        update_user_status(customer_id, "canceled")

    elif event_type == "invoice.payment_succeeded":
        customer_id = data_obj.get("customer", "")
        update_user_status(customer_id, "active")

    elif event_type == "invoice.payment_failed":
        customer_id = data_obj.get("customer", "")
        update_user_status(customer_id, "past_due")

    return jsonify({"received": True})


@app.route("/api/validate-key", methods=["POST"])
def api_validate_key():
    data = request.get_json()
    license_key = data.get("license_key", "")

    user, error = validate_license_key(license_key)
    if error:
        return jsonify({"valid": False, "error": error}), 401

    usage = get_monthly_usage(license_key)

    return jsonify({
        "valid": True,
        "plan": user["plan"],
        "status": user["status"],
        "email": user["email"],
        "usage": {
            "translations_this_month": usage["count"],
            "limit": 500,
        },
    })


_email_attempts = {}

@app.route("/api/activate-by-email", methods=["POST"])
def api_activate_by_email():
    import time
    data = request.get_json()
    email = (data.get("email", "") or "").strip().lower()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    now = time.time()
    key = f"{client_ip}:{email}"
    attempts = _email_attempts.get(key, [])
    attempts = [t for t in attempts if now - t < 300]
    if len(attempts) >= 5:
        return jsonify({"error": "Too many attempts. Please try again in a few minutes."}), 429
    attempts.append(now)
    _email_attempts[key] = attempts

    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "No active Pro subscription found for this email. Make sure you're using the same email from checkout."}), 404

    usage = get_monthly_usage(user["license_key"])

    return jsonify({
        "license_key": user["license_key"],
        "plan": user["plan"],
        "status": user["status"],
        "email": user["email"],
        "usage": {
            "translations_this_month": usage["count"],
            "limit": 500,
        },
    })


@app.route("/api/translate", methods=["POST"])
def api_translate():
    data = request.get_json()
    license_key = data.get("license_key", "")
    terminal_text = data.get("text", "")
    mode = data.get("mode", "beginner")
    language = data.get("language", "en")

    if not terminal_text:
        return jsonify({"error": "No text provided"}), 400

    user, error = validate_license_key(license_key)
    if error:
        return jsonify({"error": error}), 401

    allowed, count = check_rate_limit(license_key)
    if not allowed:
        return jsonify({
            "error": "Monthly translation limit reached (500/month)",
            "usage": count,
            "limit": 500,
        }), 429

    try:
        explanation, tokens_used = cloud_translate(terminal_text, mode, language)
        log_usage(license_key, tokens_used, "translate")

        return jsonify({
            "explanation": explanation,
            "source": "cloud_ai",
            "tokens_used": tokens_used,
            "usage": {
                "translations_this_month": count + 1,
                "limit": 500,
            },
        })
    except Exception as e:
        return jsonify({"error": f"Translation failed: {e}"}), 500


@app.route("/api/usage", methods=["POST"])
def api_usage():
    data = request.get_json()
    license_key = data.get("license_key", "")

    user, error = validate_license_key(license_key)
    if error:
        return jsonify({"error": error}), 401

    usage = get_monthly_usage(license_key)

    return jsonify({
        "plan": user["plan"],
        "status": user["status"],
        "email": user["email"],
        "usage": {
            "translations_this_month": usage["count"],
            "tokens_this_month": usage["total_tokens"],
            "limit": 500,
        },
    })


@app.route("/api/portal", methods=["POST"])
def api_portal():
    data = request.get_json()
    license_key = data.get("license_key", "")

    user, error = validate_license_key(license_key)
    if error:
        return jsonify({"error": error}), 401

    try:
        stripe = get_stripe_client()
        host = request.headers.get("Host", "localhost:5000")
        scheme = "https" if "replit" in host or "repl" in host else request.scheme

        session = stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"],
            return_url=f"{scheme}://{host}/account",
        )
        return jsonify({"url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
