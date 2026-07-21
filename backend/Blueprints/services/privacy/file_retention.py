from datetime import timedelta
import os
from pathlib import Path
import shutil

from extensions import db
from models import ConversionJob, utc_now


REMOVED_INPUT_FILENAME = "arquivo_removido"
REMOVED_OUTPUT_FILENAME = "arquivo_convertido_removido"


def get_config_int(app, name, default):
    try:
        return max(1, int(app.config.get(name, default)))
    except (TypeError, ValueError):
        return default


def get_cleanup_interval_minutes(app):
    return get_config_int(app, "CONVERSION_CLEANUP_INTERVAL_MINUTES", 5)


def get_conversion_retention_minutes(app):
    return get_config_int(app, "CONVERSION_FILE_RETENTION_MINUTES", 15)


def get_conversions_root(app):
    root = os.path.abspath(os.path.join(app.instance_path, "conversions"))
    os.makedirs(root, exist_ok=True)
    return root


def cleanup_expired_conversion_files(app):
    cutoff = utc_now() - timedelta(minutes=get_conversion_retention_minutes(app))
    conversions_root = get_conversions_root(app)

    jobs = (
        ConversionJob.query.filter(ConversionJob.status.in_(["done", "failed"]))
        .filter(ConversionJob.finished_at.isnot(None))
        .filter(ConversionJob.finished_at < cutoff)
        .all()
    )

    changed = False
    for job in jobs:
        changed = remove_and_anonymize_job_files(job, conversions_root) or changed

    changed = cleanup_orphan_conversion_directories(conversions_root, cutoff) or changed
    if changed:
        db.session.commit()


def expire_conversion_job_files(app, job_id):
    with app.app_context():
        job = db.session.get(ConversionJob, job_id)
        if job is None:
            return

        if remove_and_anonymize_job_files(job, get_conversions_root(app)):
            db.session.commit()


def remove_and_anonymize_job_files(job, conversions_root):
    removed = remove_job_files(job, conversions_root)
    if not removed and not has_file_metadata(job):
        return False

    anonymize_job_file_metadata(job)
    return True


def has_file_metadata(job):
    return any(
        [
            job.input_path,
            job.output_path,
            job.original_filename != REMOVED_INPUT_FILENAME,
            not str(job.output_filename or "").startswith(REMOVED_OUTPUT_FILENAME),
            bool(job.options),
        ]
    )


def remove_job_files(job, conversions_root):
    removed = False
    job_dirs = []

    if job.input_path and os.path.isdir(job.input_path):
        job_dirs.append(job.input_path)
    if job.output_path:
        job_dirs.append(os.path.dirname(job.output_path))

    for job_dir in job_dirs:
        removed = remove_directory_inside_root(job_dir, conversions_root) or removed

    if removed:
        return True

    return (
        remove_file_inside_root(job.input_path, conversions_root)
        or remove_file_inside_root(job.output_path, conversions_root)
    )


def anonymize_job_file_metadata(job):
    output_extension = os.path.splitext(job.output_filename or "")[1]
    job.input_path = ""
    job.output_path = ""
    job.original_filename = REMOVED_INPUT_FILENAME
    job.output_filename = f"{REMOVED_OUTPUT_FILENAME}{output_extension}"
    job.options = {}


def cleanup_orphan_conversion_directories(conversions_root, cutoff):
    root = Path(conversions_root)
    if not root.exists():
        return False

    referenced_dirs = get_referenced_conversion_dirs(conversions_root)
    cutoff_timestamp = cutoff.timestamp()
    removed = False

    for path in root.iterdir():
        if not path.is_dir():
            continue
        directory = os.path.abspath(path)
        if directory in referenced_dirs:
            continue
        try:
            if path.stat().st_mtime < cutoff_timestamp:
                shutil.rmtree(path)
                removed = True
        except OSError:
            pass

    return removed


def get_referenced_conversion_dirs(conversions_root):
    referenced = set()
    jobs = ConversionJob.query.filter(
        (ConversionJob.input_path != "") | (ConversionJob.output_path != "")
    ).all()

    for job in jobs:
        for path in (job.input_path, job.output_path):
            if not path:
                continue
            directory = path if os.path.isdir(path) else os.path.dirname(path)
            directory = os.path.abspath(directory)
            if is_inside_root(directory, conversions_root):
                referenced.add(directory)

    return referenced


def remove_directory_inside_root(path, root):
    if not path:
        return False

    directory = os.path.abspath(path)
    if not is_inside_root(directory, root) or not os.path.isdir(directory):
        return False

    try:
        shutil.rmtree(directory)
        return True
    except OSError:
        return False


def remove_file_inside_root(path, root):
    if not path:
        return False

    file_path = os.path.abspath(path)
    if not is_inside_root(file_path, root) or not os.path.isfile(file_path):
        return False

    try:
        os.remove(file_path)
        return True
    except OSError:
        return False


def is_inside_root(path, root):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False
