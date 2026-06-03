import os
import subprocess

DEFAULT_CONVERSION_ERROR = "Nao foi possivel concluir a conversao deste arquivo. Tente enviar outro arquivo ou escolha outra configuracao."

def get_user_friendly_conversion_error(error):
    if isinstance(error, ValueError): return clean_error_message(str(error))
    if isinstance(error, FileNotFoundError): return "Nao foi possivel acessar o arquivo enviado. Envie o arquivo novamente."
    if isinstance(error, UnicodeDecodeError): return "Nao foi possivel ler o texto deste arquivo. Verifique a codificacao e tente novamente."
    if isinstance(error, subprocess.CalledProcessError): return "Nao foi possivel processar a midia enviada. Verifique se o arquivo abre normalmente e tente novamente."
    if is_ffmpeg_error(error): return "Nao foi possivel processar o audio ou video enviado. Verifique o arquivo e tente novamente."
    
    message = clean_error_message(str(error))
    if is_safe_runtime_message(message): return message
    return DEFAULT_CONVERSION_ERROR

def is_ffmpeg_error(error):
    error_type = type(error).__name__.lower()
    error_module = type(error).__module__.lower()
    return "ffmpeg" in error_type or "ffmpeg" in error_module

def is_safe_runtime_message(message):
    safe_prefixes = ("Pagina fora do intervalo permitido:", "Intervalo invalido:", "Erro de conexao com a IA:", "Erro de conexao com OCR:", "Erro na IA:", "Erro no OCR:", "Erro na transcricao:", "FFmpeg nao encontrado.", "LibreOffice nao encontrado.")
    safe_messages = {"Arquivo final nao foi criado.", "Arquivo final vazio.", "A transcricao voltou vazia.", "Configure OPENAI_API_KEY para usar esta ferramenta.", "Configure OPENAI_API_KEY para usar OCR.", "Nao encontrei audio disponivel para este video.", "OCR nao encontrou texto.", "Envie pelo menos dois PDFs para juntar.", "Informe um texto para adicionar ao PDF.", "Pagina informada nao existe no PDF.", "Informe a senha do PDF.", "Informe uma senha para proteger o PDF.", "Senha do PDF invalida.", "Rotacao invalida.", "Nao encontrei imagens incorporadas neste PDF.", "Nao foi possivel converter este arquivo com LibreOffice. Verifique se o arquivo abre normalmente e tente novamente."}
    return message in safe_messages or any(message.startswith(prefix) for prefix in safe_prefixes)

def clean_error_message(message):
    message = (message or "").strip()
    if not message: return DEFAULT_CONVERSION_ERROR
    if looks_like_technical_message(message): return DEFAULT_CONVERSION_ERROR
    return message[:300]

def looks_like_technical_message(message):
    technical_parts = ("Traceback", "FileNotFoundError", "CalledProcessError", "ffmpeg error", "WinError", "Errno", "subprocess", "object has no attribute", "No such file or directory")
    if any(part.lower() in message.lower() for part in technical_parts): return True
    return has_path_like_text(message)

def has_path_like_text(message): return os.sep in message or "/" in message or ":\\" in message
