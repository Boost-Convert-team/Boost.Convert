ToolRecord = dict[str, object]
ToolRegistry = dict[str, list[ToolRecord]]


TOOLS: ToolRegistry = {
    "Audios": [
        {"name": "AAC -> MP3", "route": "/convert/aac-to-mp3", "accept": ".aac"},
        {"name": "FLAC -> MP3", "route": "/convert/flac-to-mp3", "accept": ".flac"},
        {"name": "FLAC -> WAV", "route": "/convert/flac-to-wav", "accept": ".flac"},
        {"name": "MP3 -> MP4", "route": "/convert/mp3-to-mp4", "accept": ".mp3"},
        {"name": "MP3 -> WAV", "route": "/convert/mp3-to-wav", "accept": ".mp3"},
        {"name": "OGG -> MP3", "route": "/convert/ogg-to-mp3", "accept": ".ogg"},
        {"name": "OGG -> WAV", "route": "/convert/ogg-to-wav", "accept": ".ogg"},
        {"name": "WAV -> FLAC", "route": "/convert/wav-to-flac", "accept": ".wav"},
        {"name": "WAV -> MP3", "route": "/convert/wav-to-mp3", "accept": ".wav"},
        {"name": "WMA -> MP3", "route": "/convert/wma-to-mp3", "accept": ".wma"},
    ],
    "Documentos": [
        {"name": "Juntar PDF", "route": "/convert/pdf-merge", "accept": ".pdf", "multiple": True},
        {"name": "Dividir PDF", "route": "/convert/pdf-split", "accept": ".pdf"},
        {"name": "Comprimir PDF", "route": "/convert/pdf-compress", "accept": ".pdf"},
        {"name": "Rotacionar PDF", "route": "/convert/pdf-rotate", "accept": ".pdf", "aliases": "girar pdf virar pdf rotacionar paginas"},
        {"name": "Proteger PDF", "route": "/convert/pdf-protect", "accept": ".pdf", "aliases": "senha pdf criptografar pdf bloquear pdf"},
        {"name": "Desbloquear PDF", "route": "/convert/pdf-unlock", "accept": ".pdf", "aliases": "remover senha pdf destravar pdf unlock pdf"},
        {"name": "Extrair imagens do PDF", "route": "/convert/pdf-extract-images", "accept": ".pdf", "aliases": "extrair fotos imagens de pdf exportar imagens"},
        {"name": "Editar PDF", "route": "/convert/pdf-edit", "accept": ".pdf"},
        {"name": "CSV -> XLSX", "route": "/convert/csv-to-xlsx", "accept": ".csv"},
        {"name": "DOC -> DOCX", "route": "/convert/doc-to-docx", "accept": ".doc"},
        {"name": "DOC -> PDF", "route": "/convert/doc-to-pdf", "accept": ".doc"},
        {"name": "DOCX -> PDF", "route": "/convert/docx-to-pdf", "accept": ".docx"},
        {"name": "DOCX -> TXT", "route": "/convert/docx-to-txt", "accept": ".docx"},
        {"name": "DOCX -> XLSX", "route": "/convert/docx-to-xlsx", "accept": ".docx"},
        {"name": "Arquivos -> ZIP", "route": "/convert/files-to-zip", "accept": ".pdf,.doc,.docx,.odt,.ppt,.pptx,.odp,.xls,.xlsx,.ods,.txt,.csv,.json,.md,.html,.jpg,.jpeg,.png,.webp,.heic,.svg,.mp3,.wav,.mp4,.mov,.mkv,.avi,.webm,.zip", "multiple": True, "icon": "archive", "aliases": "zip compactar arquivos comprimir pasta arquivo pacote download"},
        {"name": "HTML -> DOCX", "route": "/convert/html-to-docx", "accept": ".html,.htm"},
        {"name": "HTML -> PDF", "route": "/convert/html-to-pdf", "accept": ".html,.htm"},
        {"name": "JPG -> PDF", "route": "/convert/jpg-to-pdf", "accept": ".jpg,.jpeg"},
        {"name": "JSON -> CSV", "route": "/convert/json-to-csv", "accept": ".json"},
        {"name": "JSON -> XLSX", "route": "/convert/json-to-xlsx", "accept": ".json"},
        {"name": "MD -> DOCX", "route": "/convert/md-to-docx", "accept": ".md"},
        {"name": "MD -> PDF", "route": "/convert/md-to-pdf", "accept": ".md"},
        {"name": "ODP -> PDF", "route": "/convert/odp-to-pdf", "accept": ".odp"},
        {"name": "ODP -> PPTX", "route": "/convert/odp-to-pptx", "accept": ".odp"},
        {"name": "ODS -> PDF", "route": "/convert/ods-to-pdf", "accept": ".ods"},
        {"name": "ODS -> XLSX", "route": "/convert/ods-to-xlsx", "accept": ".ods"},
        {"name": "ODT -> DOCX", "route": "/convert/odt-to-docx", "accept": ".odt"},
        {"name": "ODT -> PDF", "route": "/convert/odt-to-pdf", "accept": ".odt"},
        {"name": "PDF -> CSV", "route": "/convert/pdf-to-csv", "accept": ".pdf"},
        {"name": "PDF -> DOCX", "route": "/convert/pdf-to-docx", "accept": ".pdf"},
        {"name": "PDF -> HTML", "route": "/convert/pdf-to-html", "accept": ".pdf"},
        {"name": "PDF -> JPG", "route": "/convert/pdf-to-jpg", "accept": ".pdf"},
        {"name": "PDF -> PNG", "route": "/convert/pdf-to-png", "accept": ".pdf"},
        {"name": "PDF -> PPTX", "route": "/convert/pdf-to-pptx", "accept": ".pdf", "aliases": "pdf para powerpoint pdf para slides pdf para apresentacao"},
        {"name": "PDF -> TXT", "route": "/convert/pdf-to-txt", "accept": ".pdf"},
        {"name": "PDF -> XLSX", "route": "/convert/pdf-to-xlsx", "accept": ".pdf"},
        {"name": "PPT -> PDF", "route": "/convert/ppt-to-pdf", "accept": ".ppt"},
        {"name": "PPT -> PPTX", "route": "/convert/ppt-to-pptx", "accept": ".ppt"},
        {"name": "PPTX -> PDF", "route": "/convert/pptx-to-pdf", "accept": ".pptx"},
        {"name": "TXT -> DOCX", "route": "/convert/txt-to-docx", "accept": ".txt"},
        {"name": "TXT -> PDF", "route": "/convert/txt-to-pdf", "accept": ".txt"},
        {"name": "XLS -> PDF", "route": "/convert/xls-to-pdf", "accept": ".xls"},
        {"name": "XLS -> XLSX", "route": "/convert/xls-to-xlsx", "accept": ".xls"},
        {"name": "XLSX -> CSV", "route": "/convert/xlsx-to-csv", "accept": ".xlsx"},
        {"name": "XLSX -> DOCX", "route": "/convert/xlsx-to-docx", "accept": ".xlsx"},
        {"name": "XLSX -> JSON", "route": "/convert/xlsx-to-json", "accept": ".xlsx"},
        {"name": "XLSX -> PDF", "route": "/convert/xlsx-to-pdf", "accept": ".xlsx"},
    ],
    "Imagens": [
        {"name": "HEIC -> JPG", "route": "/convert/heic-to-jpg", "accept": ".heic"},
        {"name": "HEIC -> PNG", "route": "/convert/heic-to-png", "accept": ".heic"},
        {"name": "Imagens -> PDF", "route": "/convert/images-to-pdf", "accept": ".jpg,.jpeg,.png,.webp,.heic", "multiple": True, "icon": "file-image", "aliases": "imagem para pdf imagens para pdf foto para pdf jpg png webp heic scanner"},
        {"name": "JPG -> PNG", "route": "/convert/jpg-to-png", "accept": ".jpg,.jpeg"},
        {"name": "JPG -> SVG", "route": "/convert/jpg-to-svg", "accept": ".jpg,.jpeg"},
        {"name": "JPG -> WEBP", "route": "/convert/jpg-to-webp", "accept": ".jpg,.jpeg"},
        {"name": "PNG -> JPG", "route": "/convert/png-to-jpg", "accept": ".png"},
        {"name": "PNG -> SVG", "route": "/convert/png-to-svg", "accept": ".png"},
        {"name": "PNG -> WEBP", "route": "/convert/png-to-webp", "accept": ".png"},
        {"name": "SVG -> JPG", "route": "/convert/svg-to-jpg", "accept": ".svg"},
        {"name": "SVG -> PNG", "route": "/convert/svg-to-png", "accept": ".svg"},
        {"name": "WEBP -> JPG", "route": "/convert/webp-to-jpg", "accept": ".webp"},
        {"name": "WEBP -> PNG", "route": "/convert/webp-to-png", "accept": ".webp"},
    ],
    "Videos": [
        {"name": "AVI -> MP4", "route": "/convert/avi-to-mp4", "accept": ".avi"},
        {"name": "MKV -> MP4", "route": "/convert/mkv-to-mp4", "accept": ".mkv"},
        {"name": "MOV -> MP4", "route": "/convert/mov-to-mp4", "accept": ".mov"},
        {"name": "MP4 -> GIF", "route": "/convert/mp4-to-gif", "accept": ".mp4"},
        {"name": "MP4 -> MKV", "route": "/convert/mp4-to-mkv", "accept": ".mp4"},
        {"name": "MP4 -> MOV", "route": "/convert/mp4-to-mov", "accept": ".mp4"},
        {"name": "MP4 -> MP3", "route": "/convert/mp4-to-mp3", "accept": ".mp4"},
        {"name": "MP4 -> WAV", "route": "/convert/mp4-to-wav", "accept": ".mp4"},
        {"name": "MP4 -> WEBM", "route": "/convert/mp4-to-webm", "accept": ".mp4"},
        {"name": "WEBM -> MP4", "route": "/convert/webm-to-mp4", "accept": ".webm"},
    ],
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "/convert/aac-to-mp3": "Converta AAC para MP3, facil de tocar em celulares, carros e apps de musica.",
    "/convert/flac-to-mp3": "Transforme FLAC em MP3 para reduzir tamanho e abrir em mais aparelhos.",
    "/convert/flac-to-wav": "Passe FLAC para WAV quando precisar editar audio com alta fidelidade.",
    "/convert/mp3-to-mp4": "Crie um video MP4 simples a partir do audio MP3 para publicar ou enviar.",
    "/convert/mp3-to-wav": "Converta MP3 em WAV para editar o audio com mais qualidade.",
    "/convert/ogg-to-mp3": "Transforme OGG em MP3 e use o audio em apps e players comuns.",
    "/convert/ogg-to-wav": "Passe OGG para WAV para editar ou incluir o audio em projetos.",
    "/convert/wav-to-flac": "Compacte WAV em FLAC mantendo qualidade, com arquivo menor.",
    "/convert/wav-to-mp3": "Converta WAV para MP3 para diminuir o tamanho e facilitar o envio.",
    "/convert/wma-to-mp3": "Atualize audios WMA para MP3, formato mais comum e compativel.",
    "/convert/pdf-merge": "Una varios PDFs em um unico arquivo, mantendo as paginas na ordem escolhida.",
    "/convert/pdf-split": "Separe paginas de um PDF e baixe cada parte pronta para usar.",
    "/convert/pdf-compress": "Reduza o tamanho do PDF para enviar por email ou aplicativos sem pesar tanto.",
    "/convert/pdf-rotate": "Gire paginas tortas do PDF e salve tudo na orientacao correta.",
    "/convert/pdf-protect": "Adicione senha ao PDF para limitar a abertura e proteger o conteudo.",
    "/convert/pdf-unlock": "Remova a senha de um PDF que voce ja tem permissao para acessar.",
    "/convert/pdf-extract-images": "Salve as imagens dentro do PDF como arquivos separados para baixar.",
    "/convert/pdf-edit": "Abra o PDF para fazer ajustes simples antes de salvar uma nova versao.",
    "/convert/csv-to-xlsx": "Leve uma tabela CSV para Excel, com linhas e colunas organizadas.",
    "/convert/doc-to-docx": "Atualize arquivos Word antigos .doc para DOCX, melhor para edicao atual.",
    "/convert/doc-to-pdf": "Transforme um Word antigo em PDF para compartilhar sem mudar a aparencia.",
    "/convert/docx-to-pdf": "Salve seu Word moderno em PDF, preservando texto, imagens e layout.",
    "/convert/docx-to-txt": "Extraia o texto do Word para um arquivo leve, sem imagens nem formatacao.",
    "/convert/docx-to-xlsx": "Passe tabelas de um Word para uma planilha Excel editavel.",
    "/convert/files-to-zip": "Junte documentos, imagens, audios e videos em um ZIP para baixar tudo junto.",
    "/convert/html-to-docx": "Converta uma pagina HTML em Word para revisar e editar o conteudo.",
    "/convert/html-to-pdf": "Salve uma pagina HTML como PDF para imprimir ou enviar com layout fixo.",
    "/convert/jpg-to-pdf": "Transforme fotos JPG em PDF para compartilhar ou imprimir com facilidade.",
    "/convert/json-to-csv": "Converta dados JSON em CSV para abrir em planilhas e sistemas.",
    "/convert/json-to-xlsx": "Transforme dados JSON em uma planilha Excel com colunas faceis de ler.",
    "/convert/md-to-docx": "Passe textos Markdown para Word, mantendo titulos e listas editaveis.",
    "/convert/md-to-pdf": "Converta Markdown em PDF para entregar um texto pronto para leitura.",
    "/convert/odp-to-pdf": "Salve apresentacoes ODP em PDF para compartilhar sem depender do editor.",
    "/convert/odp-to-pptx": "Transforme slides ODP em PowerPoint PPTX para editar no Office.",
    "/convert/ods-to-pdf": "Converta planilhas ODS em PDF para enviar uma versao fixa e limpa.",
    "/convert/ods-to-xlsx": "Leve planilhas ODS para Excel XLSX e continue editando normalmente.",
    "/convert/odt-to-docx": "Transforme textos ODT em Word DOCX para editar no Microsoft Word.",
    "/convert/odt-to-pdf": "Salve documentos ODT em PDF com aparencia consistente para envio.",
    "/convert/pdf-to-csv": "Extraia tabelas do PDF para CSV, util para abrir em planilhas.",
    "/convert/pdf-to-docx": "Converta PDF em Word editavel para alterar texto e reorganizar conteudo.",
    "/convert/pdf-to-html": "Transforme o PDF em HTML para aproveitar o conteudo em paginas web.",
    "/convert/pdf-to-jpg": "Converta paginas do PDF em imagens JPG, boas para visualizar e compartilhar.",
    "/convert/pdf-to-png": "Transforme paginas do PDF em PNG para usar imagens com boa definicao.",
    "/convert/pdf-to-pptx": "Leve o conteudo do PDF para slides PowerPoint editaveis.",
    "/convert/pdf-to-txt": "Extraia apenas o texto do PDF em um arquivo simples e leve.",
    "/convert/pdf-to-xlsx": "Converta tabelas do PDF para Excel, facilitando filtros e edicoes.",
    "/convert/ppt-to-pdf": "Salve PowerPoint antigo .ppt em PDF para apresentar sem mudar o layout.",
    "/convert/ppt-to-pptx": "Atualize slides PPT antigos para PPTX, formato atual do PowerPoint.",
    "/convert/pptx-to-pdf": "Converta apresentacoes PPTX em PDF para enviar ou imprimir com seguranca.",
    "/convert/txt-to-docx": "Transforme texto simples em Word DOCX para formatar e editar melhor.",
    "/convert/txt-to-pdf": "Converta um arquivo TXT em PDF para leitura e envio mais organizado.",
    "/convert/xls-to-pdf": "Salve planilhas Excel antigas .xls em PDF para compartilhar sem edicao.",
    "/convert/xls-to-xlsx": "Atualize planilhas XLS para XLSX, formato atual do Excel.",
    "/convert/xlsx-to-csv": "Exporte planilhas Excel para CSV, ideal para sistemas e bases de dados.",
    "/convert/xlsx-to-docx": "Transforme dados da planilha em documento Word para relatorios simples.",
    "/convert/xlsx-to-json": "Converta planilhas Excel em JSON para usar dados em apps e APIs.",
    "/convert/xlsx-to-pdf": "Salve planilhas Excel em PDF para imprimir ou enviar com layout fixo.",
    "/convert/heic-to-jpg": "Converta fotos HEIC do iPhone para JPG, facil de abrir em qualquer aparelho.",
    "/convert/heic-to-png": "Transforme HEIC em PNG quando precisar de imagem com boa qualidade.",
    "/convert/images-to-pdf": "Junte fotos JPG, PNG, WEBP ou HEIC em um PDF organizado.",
    "/convert/jpg-to-png": "Troque JPG por PNG para usar a imagem em edicoes e fundos mais flexiveis.",
    "/convert/jpg-to-svg": "Transforme JPG em SVG para criar uma versao vetorial quando possivel.",
    "/convert/jpg-to-webp": "Converta JPG em WEBP para deixar imagens mais leves em sites.",
    "/convert/png-to-jpg": "Passe PNG para JPG quando quiser um arquivo menor e facil de compartilhar.",
    "/convert/png-to-svg": "Transforme PNG em SVG para criar uma versao vetorial simples.",
    "/convert/png-to-webp": "Converta PNG em WEBP para reduzir peso em paginas e downloads.",
    "/convert/svg-to-jpg": "Exporte SVG como JPG para abrir a imagem em apps comuns.",
    "/convert/svg-to-png": "Converta SVG para PNG mantendo boa definicao em telas e redes.",
    "/convert/webp-to-jpg": "Transforme WEBP em JPG para abrir em programas que nao aceitam WEBP.",
    "/convert/webp-to-png": "Converta WEBP em PNG para usar a imagem com melhor compatibilidade.",
    "/convert/avi-to-mp4": "Converta AVI para MP4, formato mais aceito em celulares, TVs e redes.",
    "/convert/mkv-to-mp4": "Transforme MKV em MP4 para tocar com mais facilidade em aparelhos comuns.",
    "/convert/mov-to-mp4": "Passe videos MOV, comuns no iPhone, para MP4 mais compativel.",
    "/convert/mp4-to-gif": "Crie um GIF animado a partir de um trecho de video MP4.",
    "/convert/mp4-to-mkv": "Converta MP4 em MKV quando quiser guardar video em outro container.",
    "/convert/mp4-to-mov": "Transforme MP4 em MOV para fluxos que pedem formato QuickTime.",
    "/convert/mp4-to-mp3": "Extraia o audio de um video MP4 e salve como MP3.",
    "/convert/mp4-to-wav": "Extraia o audio do MP4 em WAV, ideal para edicao com alta qualidade.",
    "/convert/mp4-to-webm": "Converta MP4 em WEBM para usar video leve em sites.",
    "/convert/webm-to-mp4": "Transforme WEBM em MP4 para abrir em mais players e dispositivos.",
}


def attach_tool_descriptions(
    tools: ToolRegistry,
    descriptions: dict[str, str],
) -> None:
    """Apply didactic card descriptions to each registered tool.

    Example: attach_tool_descriptions({"Teste": [{"route": "/x"}]}, {"/x": "Descricao"})
    """
    for category_tools in tools.values():
        for tool in category_tools:
            route = str(tool.get("route", ""))
            if route not in descriptions:
                raise KeyError(
                    f"Missing description for route '{route}'; expected TOOL_DESCRIPTIONS route key."
                )
            tool["description"] = descriptions[route]


attach_tool_descriptions(TOOLS, TOOL_DESCRIPTIONS)


def get_pdf_tool_count():
    return sum(
        1
        for tool in TOOLS["Documentos"]
        if "pdf" in tool["route"] or "PDF" in tool["name"] or ".pdf" in tool.get("accept", "")
    )


def build_tool_counts():
    categories = {category: len(tools) for category, tools in TOOLS.items()}
    total = sum(categories.values())
    visible_in_mega_menu = {
        "pdf": 5,
        "Imagens": 5,
        "Videos": 4,
        "Audios": 4,
    }
    mega_totals = {
        "pdf": get_pdf_tool_count(),
        "Imagens": categories["Imagens"],
        "Videos": categories["Videos"],
        "Audios": categories["Audios"],
    }

    return {
        "total": total,
        "categories": categories,
        "mega_totals": mega_totals,
        "mega_remaining": {
            name: max(count - visible_in_mega_menu.get(name, 0), 0)
            for name, count in mega_totals.items()
        },
    }
