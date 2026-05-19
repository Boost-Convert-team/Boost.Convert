# Auth / Home -
from Blueprints.auth.autentication import auth_bp
from Blueprints.main.home import home_bp

# Subscription -
from Blueprints.main.planos import planos_bp
from Blueprints.main.webhook_routes import webhook_bp
from Blueprints.main.checkout_routes import checkout_bp

# Convertions / Tools -

# =========================================================
# DOCUMENTS -
# =========================================================

from Blueprints.converter_routes.documents.csv_to_xlsx_routes import csv_xlsx_bp

from Blueprints.converter_routes.documents.docx_to_pdf_routes import docx_pdf_bp
from Blueprints.converter_routes.documents.docx_to_txt_routes import docx_txt_bp
from Blueprints.converter_routes.documents.docx_to_xlsx_routes import docx_xlsx_bp

from Blueprints.converter_routes.documents.html_to_docx_routes import html_docx_bp
from Blueprints.converter_routes.documents.html_to_pdf_routes import html_pdf_bp

from Blueprints.converter_routes.documents.jpg_to_pdf_routes import jpg_pdf_bp

from Blueprints.converter_routes.documents.json_to_csv_routes import json_csv_bp
from Blueprints.converter_routes.documents.json_to_xlsx_routes import json_xlsx_bp

from Blueprints.converter_routes.documents.md_to_docx_routes import md_docx_bp
from Blueprints.converter_routes.documents.md_to_pdf_routes import md_pdf_bp

from Blueprints.converter_routes.documents.pdf_to_csv_routes import pdf_csv_bp
from Blueprints.converter_routes.documents.pdf_to_docx_routes import pdf_docx_bp
from Blueprints.converter_routes.documents.pdf_to_html_routes import pdf_html_bp
from Blueprints.converter_routes.documents.pdf_to_jpg_routes import pdf_jpg_bp
from Blueprints.converter_routes.documents.pdf_to_png_routes import pdf_png_bp
from Blueprints.converter_routes.documents.pdf_to_text_routes import pdf_txt_bp
from Blueprints.converter_routes.documents.pdf_to_xlsx_routes import pdf_xlsx_bp
from Blueprints.converter_routes.documents.pdf_merge_routes import pdf_merge_bp
from Blueprints.converter_routes.documents.pdf_split_routes import pdf_split_bp
from Blueprints.converter_routes.documents.pdf_compress_routes import pdf_compress_bp
from Blueprints.converter_routes.documents.pdf_edit_routes import pdf_edit_bp

from Blueprints.converter_routes.documents.pptx_to_pdf_routes import pptx_pdf_bp

from Blueprints.converter_routes.documents.txt_to_docx_routes import txt_docx_bp
from Blueprints.converter_routes.documents.txt_to_pdf_routes import txt_pdf_bp

from Blueprints.converter_routes.documents.xlsx_to_csv_routes import xlsx_csv_bp
from Blueprints.converter_routes.documents.xlsx_to_docx_routes import xlsx_docx_bp
from Blueprints.converter_routes.documents.xlsx_to_json_routes import xlsx_json_bp
from Blueprints.converter_routes.documents.xlsx_to_pdf_routes import xlsx_pdf_bp


# =========================================================
# IMAGES -
# =========================================================

from Blueprints.converter_routes.images.heic_to_jpg_routes import heic_jpg_bp
from Blueprints.converter_routes.images.heic_to_png_routes import heic_png_bp

from Blueprints.converter_routes.images.jpg_to_png_routes import jpg_png_bp
from Blueprints.converter_routes.images.jpg_to_svg_routes import jpg_svg_bp
from Blueprints.converter_routes.images.jpg_to_webp_routes import jpg_webp_bp

from Blueprints.converter_routes.images.png_to_jpg_routes import png_jpg_bp
from Blueprints.converter_routes.images.png_to_svg_routes import png_svg_bp
from Blueprints.converter_routes.images.png_to_webp_routes import png_webp_bp

from Blueprints.converter_routes.images.svg_to_jpg_routes import svg_jpg_bp
from Blueprints.converter_routes.images.svg_to_png_routes import svg_png_bp

from Blueprints.converter_routes.images.webp_to_jpg_routes import webp_jpg_bp
from Blueprints.converter_routes.images.webp_to_png_routes import webp_png_bp


# =========================================================
# VIDEOS -
# =========================================================

from Blueprints.converter_routes.videos.avi_to_mp4_routes import avi_mp4_bp

from Blueprints.converter_routes.videos.mkv_to_mp4_routes import mkv_mp4_bp

from Blueprints.converter_routes.videos.mov_to_mp4_routes import mov_mp4_bp

from Blueprints.converter_routes.videos.mp4_to_gif_routes import mp4_gif_bp
from Blueprints.converter_routes.videos.mp4_to_mkv_routes import mp4_mkv_bp
from Blueprints.converter_routes.videos.mp4_to_mov_routes import mp4_mov_bp
from Blueprints.converter_routes.videos.mp4_to_mp3_routes import mp4_mp3_bp
from Blueprints.converter_routes.videos.mp4_to_wav_routes import mp4_wav_bp
from Blueprints.converter_routes.videos.mp4_to_webm_routes import mp4_webm_bp

from Blueprints.converter_routes.videos.webm_to_mp4_routes import webm_mp4_bp


# =========================================================
# AUDIOS -
# =========================================================

from Blueprints.converter_routes.audios.aac_to_mp3_routes import aac_mp3_bp

from Blueprints.converter_routes.audios.flac_to_mp3_routes import flac_mp3_bp
from Blueprints.converter_routes.audios.flac_to_wav_routes import flac_wav_bp

from Blueprints.converter_routes.audios.mp3_to_mp4_routes import mp3_mp4_bp
from Blueprints.converter_routes.audios.mp3_to_wav_routes import mp3_wav_bp

from Blueprints.converter_routes.audios.ogg_to_mp3_routes import ogg_mp3_bp
from Blueprints.converter_routes.audios.ogg_to_wav_routes import ogg_wav_bp

from Blueprints.converter_routes.audios.wav_to_flac_routes import wav_flac_bp
from Blueprints.converter_routes.audios.wav_to_mp3_routes import wav_mp3_bp

from Blueprints.converter_routes.audios.wma_to_mp3_routes import wma_mp3_bp



def registrando_blueprints(app):

    # AUTH / HOME -

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)


    # SUBSCRIPTION -
    app.register_blueprint(planos_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(checkout_bp)

# =========================================================
# ---- CONVERTIONS ----
# =========================================================

    # DOCUMENTS -
    app.register_blueprint(csv_xlsx_bp)

    app.register_blueprint(docx_pdf_bp)
    app.register_blueprint(docx_txt_bp)
    app.register_blueprint(docx_xlsx_bp)

    app.register_blueprint(html_docx_bp)
    app.register_blueprint(html_pdf_bp)

    app.register_blueprint(jpg_pdf_bp)

    app.register_blueprint(json_csv_bp)
    app.register_blueprint(json_xlsx_bp)

    app.register_blueprint(md_docx_bp)
    app.register_blueprint(md_pdf_bp)

    app.register_blueprint(pdf_csv_bp)
    app.register_blueprint(pdf_docx_bp)
    app.register_blueprint(pdf_html_bp)
    app.register_blueprint(pdf_jpg_bp)
    app.register_blueprint(pdf_png_bp)
    app.register_blueprint(pdf_txt_bp)
    app.register_blueprint(pdf_xlsx_bp)
    app.register_blueprint(pdf_merge_bp)
    app.register_blueprint(pdf_split_bp)
    app.register_blueprint(pdf_compress_bp)
    app.register_blueprint(pdf_edit_bp)

    app.register_blueprint(pptx_pdf_bp)

    app.register_blueprint(txt_docx_bp)
    app.register_blueprint(txt_pdf_bp)

    app.register_blueprint(xlsx_csv_bp)
    app.register_blueprint(xlsx_docx_bp)
    app.register_blueprint(xlsx_json_bp)
    app.register_blueprint(xlsx_pdf_bp)


    # IMAGES -
    app.register_blueprint(heic_jpg_bp)
    app.register_blueprint(heic_png_bp)

    app.register_blueprint(jpg_png_bp)
    app.register_blueprint(jpg_svg_bp)
    app.register_blueprint(jpg_webp_bp)

    app.register_blueprint(png_jpg_bp)
    app.register_blueprint(png_svg_bp)
    app.register_blueprint(png_webp_bp)

    app.register_blueprint(svg_jpg_bp)
    app.register_blueprint(svg_png_bp)

    app.register_blueprint(webp_jpg_bp)
    app.register_blueprint(webp_png_bp)


    # VIDEOS -
    app.register_blueprint(avi_mp4_bp)

    app.register_blueprint(mkv_mp4_bp)

    app.register_blueprint(mov_mp4_bp)

    app.register_blueprint(mp4_gif_bp)
    app.register_blueprint(mp4_mkv_bp)
    app.register_blueprint(mp4_mov_bp)
    app.register_blueprint(mp4_mp3_bp)
    app.register_blueprint(mp4_wav_bp)
    app.register_blueprint(mp4_webm_bp)

    app.register_blueprint(webm_mp4_bp)


    # AUDIOS -

    app.register_blueprint(aac_mp3_bp)

    app.register_blueprint(flac_mp3_bp)
    app.register_blueprint(flac_wav_bp)

    app.register_blueprint(mp3_mp4_bp)
    app.register_blueprint(mp3_wav_bp)

    app.register_blueprint(ogg_mp3_bp)
    app.register_blueprint(ogg_wav_bp)

    app.register_blueprint(wav_flac_bp)
    app.register_blueprint(wav_mp3_bp)

    app.register_blueprint(wma_mp3_bp)
