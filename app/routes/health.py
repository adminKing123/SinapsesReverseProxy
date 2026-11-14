from flask import Blueprint, jsonify

from app.services.http import check_hrms_reachable

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    return jsonify({"success": True, "status": "ok"})


@health_bp.route("/health/hrms")
def health_hrms():
    from flask import current_app

    api_base = (current_app.config.get("SYN_CORE_CONFIG") or {}).get("API_BASE", "")
    if not api_base:
        return jsonify({"success": False, "error": "SYN_CORE_CONFIG.API_BASE not set"}), 503
    result = check_hrms_reachable(api_base)
    status = 200 if result.get("ok") else 502
    return jsonify({"success": result.get("ok", False), **result}), status