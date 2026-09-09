"""Admin User Provisioning Module.

Safely provisions the seed administrator account from environment variables:
- ADMIN_EMAIL
- ADMIN_USERNAME
- ADMIN_PASSWORD
- ADMIN_DISPLAY_NAME
- ADMIN_ALLOW_GOOGLE_LOGIN

Behavior:
- Idempotent: Can be run repeatedly on server startup without duplicate records or side effects.
- Fail-fast: Raises descriptive RuntimeError on incomplete configurations or database identifier conflicts.
- Production enforcement: Fails fast if mandatory admin credentials are unset in production (BEHIND_HTTPS=1).
- Session revocation: Automatically revokes existing sessions if the admin password or role is updated.
- Seed protection: Provides is_seed_admin helper to prevent UI-level deletion, deactivation, or demotion.
"""

import os
import re
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


def get_seed_admin_identifiers():
    """Return normalized seed admin email and username from environment."""
    email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    username = (os.getenv("ADMIN_USERNAME") or "").strip().lower()
    return email, username


def is_seed_admin(user_or_identifier) -> bool:
    """Check if given user dict, email, or username matches the seed admin environment configuration."""
    seed_email, seed_username = get_seed_admin_identifiers()
    if not seed_email and not seed_username:
        return False

    if isinstance(user_or_identifier, dict):
        u_email = (user_or_identifier.get("email") or "").strip().lower()
        u_name = (user_or_identifier.get("username") or "").strip().lower()
        return (seed_email and u_email == seed_email) or (seed_username and u_name == seed_username)
    elif isinstance(user_or_identifier, str):
        ident = user_or_identifier.strip().lower()
        return ident in (seed_email, seed_username)
    return False


def provision_admin_user(app=None) -> dict | None:
    """Bootstrap or synchronize the seed administrator account.

    Runs after db.init() but before handling incoming HTTP requests.
    Returns the admin user dictionary, or None if skipped in dev.
    """
    admin_email_raw = os.getenv("ADMIN_EMAIL")
    admin_username_raw = os.getenv("ADMIN_USERNAME")
    admin_password_raw = os.getenv("ADMIN_PASSWORD")
    admin_display_name_raw = os.getenv("ADMIN_DISPLAY_NAME")
    behind_https = os.getenv("BEHIND_HTTPS") == "1"

    configured = {
        "ADMIN_EMAIL": bool(admin_email_raw and admin_email_raw.strip()),
        "ADMIN_USERNAME": bool(admin_username_raw and admin_username_raw.strip()),
        "ADMIN_PASSWORD": bool(admin_password_raw),
    }
    num_configured = sum(configured.values())

    # Case 1: None of the mandatory variables are configured
    if num_configured == 0:
        if behind_https:
            raise RuntimeError(
                "CRITICAL: ADMIN_EMAIL, ADMIN_USERNAME, and ADMIN_PASSWORD must be configured in production (BEHIND_HTTPS=1)."
            )
        print("Admin provisioning: Skipped (no admin credentials configured in environment).")
        return None

    # Case 2: Partial configuration (some present, some missing)
    if num_configured < 3:
        missing = [k for k, is_set in configured.items() if not is_set]
        raise RuntimeError(
            f"Admin provisioning failed: Incomplete configuration. Missing environment variable(s): {', '.join(missing)}"
        )

    # Normalize credentials
    email = admin_email_raw.strip().lower()
    username = admin_username_raw.strip().lower()
    password = admin_password_raw
    display_name = (admin_display_name_raw or "").strip() or username
    if len(display_name) > 50:
        display_name = display_name[:50]

    # Validate formatting and security standards
    if not EMAIL_REGEX.match(email) or len(email) > 100:
        raise ValueError("ADMIN_EMAIL is invalid or exceeds 100 characters.")

    if not USERNAME_REGEX.match(username):
        raise ValueError("ADMIN_USERNAME is invalid (must be 3-20 alphanumeric characters or underscores).")

    if len(password) < 10 or len(password) > 128:
        raise ValueError("ADMIN_PASSWORD must be between 10 and 128 characters.")

    # Check for existing records in SQLite
    user_by_email = db.get_user_by_email(email)
    user_by_username = db.get_user_by_username(username)

    if user_by_email and user_by_username:
        if user_by_email["id"] != user_by_username["id"]:
            raise RuntimeError(
                f"Admin provisioning conflict: ADMIN_EMAIL '{email}' and ADMIN_USERNAME '{username}' "
                f"point to different users (id={user_by_email['id']} vs id={user_by_username['id']}). "
                "Refusing to merge or elevate ambiguously."
            )
        existing_user = user_by_email
    elif user_by_email and not user_by_username:
        raise RuntimeError(
            f"Admin provisioning conflict: An account with email '{email}' already exists with a different username ('{user_by_email.get('username')}')."
        )
    elif not user_by_email and user_by_username:
        raise RuntimeError(
            f"Admin provisioning conflict: An account with username '{username}' already exists with a different email ('{user_by_username.get('email')}')."
        )
    else:
        existing_user = None

    if existing_user:
        user_id = existing_user["id"]
        needs_password_rotation = not check_password_hash(existing_user["password_hash"], password)
        needs_role_elevation = existing_user.get("role") != "admin"
        needs_activation = not existing_user.get("is_active")

        if needs_password_rotation:
            new_hash = generate_password_hash(password)
            db.update_user_password(user_id, new_hash)
            db.revoke_all_user_sessions(user_id, reason="admin_password_rotated")
            print(f"Admin provisioning: Updated password for admin '{username}' and revoked previous sessions.")

        if needs_role_elevation:
            db.update_user_role(user_id, "admin")
            db.revoke_all_user_sessions(user_id, reason="admin_role_granted")
            print(f"Admin provisioning: Elevated user '{username}' to role 'admin'.")

        if needs_activation:
            db.set_user_active(user_id, True)
            print(f"Admin provisioning: Re-activated admin account '{username}'.")

        if existing_user.get("display_name") != display_name:
            db.update_user_display_name(user_id, display_name)

        db.get_or_create_wallet(user_id)
        return db.get_user_by_id(user_id)
    else:
        # Create brand-new admin record
        pwd_hash = generate_password_hash(password)
        user_id = db.create_user(
            email=email,
            username=username,
            display_name=display_name,
            password_hash=pwd_hash,
            role="admin",
        )
        db.get_or_create_wallet(user_id)
        print(f"Admin provisioning: Successfully created initial administrator '{username}' (id={user_id}).")
        return db.get_user_by_id(user_id)
