from datetime import datetime, timedelta
import os
import shutil

from models import ConversionJob

LAST_CLEANUP_AT = None

def run_conversion_file_cleanup(app):
    global LAST_CLEANUP_AT

    now = datetime.utcnow()
    interval_minutes = get_int_config("CONVERSION_CLEANUP_INTERVAL_MINUTES", 30)

    if LAST_CLEANUP_AT is not None:
        next_cleanup_at = LAST_CLEANUP_AT + timedelta(minutes=interval_minutes)

        if now < next_cleanup_at:
            return

    LAST_CLEANUP_AT = now

    try:
        cleanup_old_conversion_files(app)
    except Exception:
        app.logger.exception("Erro ao limpar arquivos antigos de conversao")

def cleanup_old_conversion_files(app):
    retention_hours = get_int_config("CONVERSION_FILE_RETENTION_HOURS", 24)
    cutoff = datetime.utcnow() - timedelta(hours=retention_hours)

    jobs = (
        ConversionJob.query
        .filter(ConversionJob.status.in_(["done", "failed"]))
        .filter(ConversionJob.finished_at.isnot(None))
        .filter(ConversionJob.finished_at < cutoff)
        .all()
    )

    conversions_root = os.path.abspath(os.path.join(app.instance_path, "conversions"))

    for job in jobs:
        remove_job_files(job, conversions_root)

def remove_job_files(job, conversions_root):
    job_dirs = []

    if job.input_path and os.path.isdir(job.input_path):
        job_dirs.append(job.input_path)

    if job.output_path:
        output_dir = os.path.dirname(job.output_path)
        job_dirs.append(output_dir)

    removed_dir = False

    for job_dir in job_dirs:
        if remove_directory_inside_root(job_dir, conversions_root):
            removed_dir = True

    if removed_dir:
        return

    remove_file_inside_root(job.input_path, conversions_root)
    remove_file_inside_root(job.output_path, conversions_root)

def remove_directory_inside_root(path, root):
    directory = os.path.abspath(path)

    if not is_inside_root(directory, root):
        return False

    if not os.path.isdir(directory):
        return False

    try:
        shutil.rmtree(directory)
        return True
    except OSError:
        return False

def remove_file_inside_root(path, root):
    if not path:
        return

    file_path = os.path.abspath(path)

    if not is_inside_root(file_path, root):
        return

    if not os.path.isfile(file_path):
        return

    try:
        os.remove(file_path)
    except OSError:
        pass

def is_inside_root(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False

def get_int_config(name, default):
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default
