from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from Blueprints.services.convertions_services.conversion_errors import get_user_friendly_conversion_error
from Blueprints.services.ai.document_analyzer import (
    DOCUMENT_ANALYZER_ACTIONS,
    DocumentAnalysisResult,
    analyze_uploaded_document,
    get_document_accept_attribute,
)
from Blueprints.services.ai.youtube_analyzer import analyze_youtube_video

ai_tools_bp = Blueprint("ai_tools", __name__)


@ai_tools_bp.route("/tools/ai/youtube-analyzer", methods=["GET", "POST"])
def youtube_analyzer() -> ResponseReturnValue:
    if request.method == "GET":
        return render_template("youtube_analyzer.html")

    url = (request.form.get("url") or "").strip()
    if not url:
        return render_template("youtube_analyzer.html", url=url, error="Envie uma URL do YouTube.")

    try:
        result = analyze_youtube_video(url)
        return render_template("youtube_analyzer.html", url=url, result=result)
    except Exception as exc:
        return render_template("youtube_analyzer.html", url=url, error=get_user_friendly_conversion_error(exc))


@ai_tools_bp.route("/tools/ai/document-analyzer", methods=["GET", "POST"])
def document_analyzer() -> ResponseReturnValue:
    if request.method == "GET":
        return render_document_analyzer_template()

    uploaded_file = request.files.get("file")
    action = (request.form.get("analysis_type") or "summary").strip()
    question = (request.form.get("question") or "").strip()
    if uploaded_file is None or not uploaded_file.filename:
        return render_document_analyzer_template(error="Envie um documento para analisar.")

    try:
        result = analyze_uploaded_document(uploaded_file, action, question)
        return render_document_analyzer_template(result=result, selected_action=action, question=question)
    except Exception as exc:
        error = get_user_friendly_conversion_error(exc)
        return render_document_analyzer_template(error=error, selected_action=action, question=question)


def render_document_analyzer_template(
    error: str = "",
    result: DocumentAnalysisResult | None = None,
    selected_action: str = "summary",
    question: str = "",
) -> str:
    return render_template(
        "document_analyzer.html",
        actions=DOCUMENT_ANALYZER_ACTIONS,
        accept_attribute=get_document_accept_attribute(),
        error=error,
        result=result,
        selected_action=selected_action,
        question=question,
    )

