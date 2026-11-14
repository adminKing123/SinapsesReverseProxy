from flask import Blueprint, jsonify, render_template, request

from app.openapi.spec import build_openapi_spec

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/api-docs")
def api_docs():
    base = request.url_root.rstrip("/")
    return render_template("api_docs.html", openapi_url=f"{base}/openapi.json")


@docs_bp.route("/openapi.json")
def openapi_json():
    base = request.url_root.rstrip("/")
    return jsonify(build_openapi_spec(base))