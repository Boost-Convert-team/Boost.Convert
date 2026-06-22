from dataclasses import dataclass
import os
import subprocess


@dataclass(frozen=True)
class FriendlyConversionError:
    title: str
    message: str
    recovery: str


DEFAULT_FRIENDLY_CONVERSION_ERROR = FriendlyConversionError(
    title="N\u00e3o foi poss\u00edvel concluir",
    message="N\u00e3o foi poss\u00edvel concluir esta convers\u00e3o. O arquivo pode estar corrompido, protegido ou incompat\u00edvel com esta ferramenta.",
    recovery="Tente abrir o arquivo no seu computador, salve uma nova c\u00f3pia e envie novamente.",
)
DEFAULT_CONVERSION_ERROR = DEFAULT_FRIENDLY_CONVERSION_ERROR.message

EXACT_MESSAGE_ERRORS: dict[str, FriendlyConversionError] = {
    "Nenhum arquivo enviado": FriendlyConversionError(
        "Nenhum arquivo selecionado",
        "Escolha um arquivo antes de iniciar a convers\u00e3o.",
        "Depois de selecionar, confirme se o nome do arquivo aparece na tela do Boost.",
    ),
    "Arquivo invalido": FriendlyConversionError(
        "Arquivo n\u00e3o identificado",
        "N\u00e3o consegui identificar o arquivo enviado.",
        "Confira se o arquivo tem nome, extens\u00e3o e conte\u00fado v\u00e1lidos antes de enviar novamente.",
    ),
    "Requisicao invalida.": FriendlyConversionError(
        "Envio n\u00e3o entendido",
        "O Boost n\u00e3o conseguiu entender os dados enviados.",
        "Volte para a ferramenta, revise os campos e tente novamente.",
    ),
    "Acesso nao permitido.": FriendlyConversionError(
        "Acesso n\u00e3o permitido",
        "Voc\u00ea n\u00e3o tem permiss\u00e3o para acessar este recurso.",
        "Entre na conta correta ou volte para as ferramentas dispon\u00edveis.",
    ),
    "Pagina nao encontrada.": FriendlyConversionError(
        "P\u00e1gina n\u00e3o encontrada",
        "O endere\u00e7o acessado n\u00e3o existe ou foi removido.",
        "Volte para a lista de ferramentas e escolha uma convers\u00e3o dispon\u00edvel.",
    ),
    "Arquivo maior que o limite geral.": FriendlyConversionError(
        "Arquivo grande demais",
        "O arquivo passou do limite aceito pelo Boost antes de chegar ao conversor.",
        "Reduza o tamanho do arquivo ou divida o envio em partes menores.",
    ),
    "Erro interno do Boost.": FriendlyConversionError(
        "Algo saiu do esperado",
        "O Boost encontrou um erro interno enquanto processava a solicita\u00e7\u00e3o.",
        "Tente novamente em alguns instantes. Se persistir, use outro arquivo ou outra ferramenta.",
    ),
    "Erro ao processar os arquivos.": FriendlyConversionError(
        "Erro ao preparar os arquivos",
        "O Boost n\u00e3o conseguiu preparar os arquivos enviados para convers\u00e3o.",
        "Confira se os arquivos abrem normalmente, salve novas c\u00f3pias e tente enviar novamente.",
    ),
    "Envie pelo menos dois arquivos PDF.": FriendlyConversionError(
        "Envie pelo menos dois PDFs",
        "Para juntar PDFs, o Boost precisa receber dois ou mais arquivos PDF.",
        "Adicione mais um PDF e tente iniciar a convers\u00e3o novamente.",
    ),
    "Envie pelo menos um arquivo.": FriendlyConversionError(
        "Envie pelo menos um arquivo",
        "O Boost n\u00e3o recebeu nenhum arquivo para processar.",
        "Selecione um arquivo e confirme se ele aparece na lista antes de converter.",
    ),
    "Todos os arquivos precisam ser PDF.": FriendlyConversionError(
        "Formato diferente no envio",
        "Essa ferramenta aceita apenas arquivos PDF.",
        "Remova os arquivos de outro formato ou escolha uma ferramenta compat\u00edvel.",
    ),
    "O tipo MIME do arquivo nao corresponde ao formato enviado.": FriendlyConversionError(
        "Tipo do arquivo n\u00e3o confere",
        "O tipo interno do arquivo n\u00e3o combina com a extens\u00e3o enviada.",
        "Abra o arquivo no aplicativo original, exporte uma nova c\u00f3pia e envie novamente.",
    ),
    "O conteudo do arquivo nao parece bater com a extensao enviada.": FriendlyConversionError(
        "Conte\u00fado e extens\u00e3o n\u00e3o conferem",
        "O conte\u00fado do arquivo n\u00e3o parece pertencer ao formato informado no nome.",
        "Confirme se a extens\u00e3o est\u00e1 correta ou gere uma nova c\u00f3pia do arquivo.",
    ),
    "Arquivo final nao foi criado.": FriendlyConversionError(
        "Arquivo final n\u00e3o foi gerado",
        "A convers\u00e3o terminou sem criar um arquivo para download.",
        "Isso costuma acontecer quando o arquivo est\u00e1 vazio, protegido ou em um formato que n\u00e3o pode ser lido.",
    ),
    "Arquivo final vazio.": FriendlyConversionError(
        "Arquivo convertido ficou vazio",
        "O Boost gerou um arquivo sem conte\u00fado aproveit\u00e1vel.",
        "Verifique se o arquivo original tem conte\u00fado vis\u00edvel, n\u00e3o est\u00e1 protegido e tente novamente.",
    ),
    "Arquivo final nao encontrado.": FriendlyConversionError(
        "Download indispon\u00edvel",
        "O arquivo convertido n\u00e3o est\u00e1 mais dispon\u00edvel para download.",
        "Converta o arquivo novamente para gerar um novo link.",
    ),
    "Conversao ainda nao finalizada.": FriendlyConversionError(
        "Convers\u00e3o ainda em andamento",
        "Seu arquivo ainda est\u00e1 sendo preparado pelo Boost.",
        "Volte para a tela de status e aguarde a conclus\u00e3o antes de baixar.",
    ),
    "Nenhum arquivo finalizado para baixar.": FriendlyConversionError(
        "Nenhum arquivo pronto",
        "Ainda n\u00e3o existe arquivo finalizado para download neste lote.",
        "Volte para a tela de status e aguarde o processamento terminar.",
    ),
    "Aguarde todas as conversoes finalizarem para baixar o lote.": FriendlyConversionError(
        "Lote ainda em processamento",
        "Nem todos os arquivos do lote terminaram de converter.",
        "Aguarde a conclus\u00e3o de todos os arquivos antes de baixar o ZIP.",
    ),
    "Arquivo final nao foi gerado": FriendlyConversionError(
        "Arquivo final n\u00e3o foi gerado",
        "O Boost n\u00e3o conseguiu gerar o arquivo final deste processamento.",
        "Tente novamente com outro arquivo ou outra qualidade.",
    ),
}

VALIDATION_MESSAGE_ERRORS: dict[str, FriendlyConversionError] = {
    "Arquivo de texto invalido.": FriendlyConversionError("Texto inv\u00e1lido", "O arquivo de texto tem conte\u00fado que n\u00e3o pode ser lido com seguran\u00e7a.", "Salve o texto novamente em UTF-8 e tente enviar outra vez."),
    "Arquivo Office invalido.": FriendlyConversionError("Arquivo Office inv\u00e1lido", "A estrutura interna do arquivo Office n\u00e3o p\u00f4de ser lida.", "Abra o arquivo no Office ou LibreOffice, salve uma nova c\u00f3pia e tente novamente."),
    "Arquivo Office sem estrutura esperada.": FriendlyConversionError("Arquivo Office incompleto", "O arquivo Office n\u00e3o tem a estrutura esperada para convers\u00e3o.", "Exporte uma nova c\u00f3pia no formato correto e tente novamente."),
    "Arquivo Office nao corresponde ao formato esperado.": FriendlyConversionError("Formato Office diferente", "O arquivo n\u00e3o corresponde ao tipo Office escolhido.", "Confirme se ele e DOCX, XLSX, PPTX, ODT, ODS ou ODP conforme a ferramenta."),
    "JSON invalido.": FriendlyConversionError("JSON inv\u00e1lido", "O arquivo JSON n\u00e3o tem uma estrutura v\u00e1lida.", "Corrija o JSON ou gere uma nova exporta\u00e7\u00e3o antes de enviar."),
    "JSON invalido para tabela.": FriendlyConversionError("JSON sem tabela leg\u00edvel", "O JSON n\u00e3o parece ter dados tabulares para converter.", "Use uma lista de objetos ou uma estrutura simples de chave e valor."),
    "SVG invalido.": FriendlyConversionError("SVG inv\u00e1lido", "O arquivo SVG n\u00e3o p\u00f4de ser lido como texto v\u00e1lido.", "Exporte o SVG novamente e tente enviar a nova vers\u00e3o."),
    "SVG sem tag principal.": FriendlyConversionError("SVG incompleto", "O arquivo n\u00e3o possui a tag principal de um SVG.", "Confirme se o arquivo enviado \u00e9 realmente um SVG."),
    "Arquivo ZIP invalido.": FriendlyConversionError("ZIP inv\u00e1lido", "O arquivo ZIP n\u00e3o p\u00f4de ser aberto com seguran\u00e7a.", "Crie um novo ZIP e tente enviar novamente."),
}

YOUTUBE_MESSAGE_ERRORS: dict[str, FriendlyConversionError] = {
    "Envie uma URL do YouTube": FriendlyConversionError("URL ausente", "Informe a URL do v\u00eddeo do YouTube antes de baixar.", "Cole o link completo do v\u00eddeo e tente novamente."),
    "Escolha uma qualidade": FriendlyConversionError("Qualidade ausente", "Escolha uma qualidade de v\u00eddeo antes de iniciar o download.", "Selecione uma op\u00e7\u00e3o dispon\u00edvel e tente novamente."),
    "Qualidade indisponivel": FriendlyConversionError("Qualidade indispon\u00edvel", "O v\u00eddeo n\u00e3o oferece a qualidade escolhida.", "Escolha outra qualidade e tente baixar novamente."),
    "Audio indisponivel para este video": FriendlyConversionError("Audio indispon\u00edvel", "N\u00e3o encontrei uma faixa de \u00e1udio compat\u00edvel para este v\u00eddeo.", "Tente outra qualidade ou outro v\u00eddeo."),
    "Nao foi possivel processar o video do YouTube.": FriendlyConversionError("V\u00eddeo n\u00e3o processado", "N\u00e3o foi poss\u00edvel processar este v\u00eddeo do YouTube no momento.", "Confira o link, tente outra qualidade ou tente novamente mais tarde."),
}


def build_friendly_conversion_error(error: BaseException) -> FriendlyConversionError:
    """Builds a safe error message for Boost conversion screens.

    Example: build_friendly_conversion_error(ValueError("Nenhum arquivo enviado"))
    """
    if isinstance(error, PermissionError):
        return build_limit_error(str(error))
    if isinstance(error, FileNotFoundError):
        return missing_file_error()
    if isinstance(error, UnicodeDecodeError):
        return text_decode_error()
    if isinstance(error, subprocess.CalledProcessError):
        return media_processing_error()
    if is_ffmpeg_error(error):
        return media_processing_error()
    return build_friendly_message_from_text(str(error))


def get_user_friendly_conversion_error(error: BaseException) -> str:
    """Returns the message saved on failed conversion jobs.

    Example: get_user_friendly_conversion_error(RuntimeError("Arquivo final vazio."))
    """
    return build_friendly_conversion_error(error).message


def build_friendly_message_from_text(raw_message: str) -> FriendlyConversionError:
    message = (raw_message or "").strip()
    if not message:
        return DEFAULT_FRIENDLY_CONVERSION_ERROR
    mapped_message = get_mapped_message(message)
    if mapped_message is not None:
        return mapped_message
    if is_safe_runtime_message(message):
        return FriendlyConversionError("N\u00e3o foi poss\u00edvel concluir", message[:300], DEFAULT_FRIENDLY_CONVERSION_ERROR.recovery)
    clean_message = clean_error_message(message)
    if clean_message == DEFAULT_CONVERSION_ERROR:
        return DEFAULT_FRIENDLY_CONVERSION_ERROR
    return FriendlyConversionError("N\u00e3o foi poss\u00edvel concluir", clean_message, DEFAULT_FRIENDLY_CONVERSION_ERROR.recovery)


def get_mapped_message(message: str) -> FriendlyConversionError | None:
    exact_message = EXACT_MESSAGE_ERRORS.get(message) or VALIDATION_MESSAGE_ERRORS.get(message) or YOUTUBE_MESSAGE_ERRORS.get(message)
    if exact_message is not None:
        return exact_message
    return get_prefix_message(message)


def get_prefix_message(message: str) -> FriendlyConversionError | None:
    if message.startswith("Formato invalido. Permitidos:"):
        return allowed_formats_error(message)
    if message.startswith("Arquivo muito grande") or message.startswith("Arquivos muito grandes"):
        return upload_size_error(message)
    if message.startswith("Voce atingiu") or message.startswith("Voce tem"):
        return build_limit_error(message)
    if message.startswith("Pagina fora do intervalo permitido:") or message.startswith("Intervalo invalido:"):
        return page_range_error(message)
    if message.startswith("Imagem invalida:") or message.startswith("Imagem vazia:"):
        return image_content_error()
    if message.startswith("Texto invalido:") or message.startswith("Texto fora de Latin-1:"):
        return text_decode_error()
    if message.startswith("Arquivo invalido:"):
        return invalid_file_detail_error()
    return dependency_error(message)


def allowed_formats_error(message: str) -> FriendlyConversionError:
    formats = message.split(":", 1)[1].strip()
    return FriendlyConversionError(
        "Formato n\u00e3o aceito",
        f"Este conversor aceita apenas estes formatos: {formats}.",
        "Escolha um arquivo compat\u00edvel ou volte para a lista de ferramentas e selecione outra convers\u00e3o.",
    )


def upload_size_error(message: str) -> FriendlyConversionError:
    return FriendlyConversionError(
        "Arquivo acima do limite",
        message[:300],
        "Reduza o tamanho do arquivo, divida o envio ou use um plano com limite maior.",
    )


def build_limit_error(message: str) -> FriendlyConversionError:
    return FriendlyConversionError(
        "Limite de uso atingido",
        clean_error_message(message),
        "Aguarde o prazo indicado ou use uma conta com mais convers\u00f5es dispon\u00edveis.",
    )


def page_range_error(message: str) -> FriendlyConversionError:
    return FriendlyConversionError(
        "P\u00e1gina fora do intervalo",
        message[:300],
        "Confira o n\u00famero das p\u00e1ginas no PDF e tente novamente com um intervalo v\u00e1lido.",
    )


def image_content_error() -> FriendlyConversionError:
    return FriendlyConversionError(
        "Imagem sem conte\u00fado v\u00e1lido",
        "A imagem enviada n\u00e3o tem dimens\u00f5es ou bytes suficientes para convers\u00e3o.",
        "Abra a imagem, exporte uma nova c\u00f3pia e envie novamente.",
    )


def invalid_file_detail_error() -> FriendlyConversionError:
    return FriendlyConversionError(
        "Arquivo incompat\u00edvel",
        "O arquivo n\u00e3o corresponde ao formato esperado por esta ferramenta.",
        "Confirme a extens\u00e3o do arquivo ou escolha uma convers\u00e3o compat\u00edvel.",
    )


def dependency_error(message: str) -> FriendlyConversionError | None:
    if message.startswith("FFmpeg nao encontrado."):
        return FriendlyConversionError("Convers\u00e3o de m\u00eddia indispon\u00edvel", "O Boost n\u00e3o encontrou o processador de \u00e1udio e v\u00eddeo.", "Tente novamente mais tarde ou use outra ferramenta enquanto isso.")
    if message.startswith("LibreOffice nao encontrado."):
        return FriendlyConversionError("Convers\u00e3o Office indispon\u00edvel", "O Boost n\u00e3o encontrou o processador de arquivos Office.", "Tente novamente mais tarde ou use outro formato de entrada.")
    return None


def missing_file_error() -> FriendlyConversionError:
    return FriendlyConversionError(
        "Arquivo enviado n\u00e3o foi encontrado",
        "N\u00e3o consegui acessar o arquivo necess\u00e1rio para concluir a opera\u00e7\u00e3o.",
        "Envie o arquivo novamente para criar uma nova convers\u00e3o.",
    )


def text_decode_error() -> FriendlyConversionError:
    return FriendlyConversionError(
        "Texto n\u00e3o leg\u00edvel",
        "N\u00e3o consegui ler o texto deste arquivo com a codifica\u00e7\u00e3o esperada.",
        "Salve o arquivo como UTF-8 ou exporte uma nova c\u00f3pia e tente novamente.",
    )


def media_processing_error() -> FriendlyConversionError:
    return FriendlyConversionError(
        "M\u00eddia n\u00e3o processada",
        "N\u00e3o foi poss\u00edvel processar o \u00e1udio ou v\u00eddeo enviado.",
        "Verifique se o arquivo abre normalmente e tente enviar uma nova c\u00f3pia.",
    )


def is_ffmpeg_error(error: BaseException) -> bool:
    error_type = type(error).__name__.lower()
    error_module = type(error).__module__.lower()
    return "ffmpeg" in error_type or "ffmpeg" in error_module


def is_safe_runtime_message(message: str) -> bool:
    safe_prefixes = ("Erro de conexao com a IA:", "Erro na IA:", "Configure OPENROUTER_API_KEY")
    safe_messages = {"A transcricao voltou vazia.", "Configure OPENROUTER_API_KEY para usar esta ferramenta.", "Informe um texto para adicionar ao PDF.", "Pagina informada nao existe no PDF.", "Informe a senha do PDF.", "Informe uma senha para proteger o PDF.", "Senha do PDF invalida.", "Rotacao invalida.", "Nao encontrei imagens incorporadas neste PDF.", "Nao foi possivel converter este arquivo com LibreOffice. Verifique se o arquivo abre normalmente e tente novamente."}
    return message in safe_messages or any(message.startswith(prefix) for prefix in safe_prefixes)


def clean_error_message(message: str) -> str:
    message = (message or "").strip()
    if not message:
        return DEFAULT_CONVERSION_ERROR
    if looks_like_technical_message(message):
        return DEFAULT_CONVERSION_ERROR
    return message[:300]


def looks_like_technical_message(message: str) -> bool:
    technical_parts = ("Traceback", "FileNotFoundError", "CalledProcessError", "ffmpeg error", "WinError", "Errno", "subprocess", "object has no attribute", "No such file or directory")
    if any(part.lower() in message.lower() for part in technical_parts):
        return True
    return has_path_like_text(message)


def has_path_like_text(message: str) -> bool:
    has_system_separator = os.sep in message
    has_url_separator = "/" in message
    has_windows_drive = ":\\" in message
    return has_system_separator or has_url_separator or has_windows_drive
