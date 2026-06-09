import os

from flask import Response, stream_with_context


DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def stream_private_download(path, download_name, cleanup):
    file_size = os.path.getsize(path)

    def generate():
        try:
            with open(path, "rb") as file:
                while True:
                    chunk = file.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
        finally:
            cleanup()

    response = Response(
        stream_with_context(generate()),
        mimetype="application/octet-stream",
        direct_passthrough=True,
    )
    response.headers.set("Content-Disposition", "attachment", filename=download_name)
    response.content_length = file_size
    response.headers["Cache-Control"] = "private, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
