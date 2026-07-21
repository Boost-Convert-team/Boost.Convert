"""Declarative SEO catalog for BoostConvert public pages.

This module is deliberately independent from ``tools_registry`` and from every
conversion service.  It describes public SEO content, but it does not decide
whether a converter exists or how a conversion is performed.  Integrations
must validate a slug against the functional registry before using the fallback
builder for a public page.

All exported records are frozen dataclasses and all catalog mappings are read
only.  Records can be converted with :func:`dataclasses.asdict` or with the
JSON-friendly :func:`as_serializable_dict` helper.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date
import re
from types import MappingProxyType
from typing import Any, Literal, Mapping


SeoStatus = Literal["draft", "indexable", "noindex", "retired"]
UPDATED_AT = date(2026, 7, 11)


@dataclass(frozen=True, slots=True)
class BrandSeo:
    """Canonical brand identity used by the SEO layer."""

    name: str
    legal_name: str
    origin: str
    locale: str
    language: str
    country: str
    default_title: str
    default_description: str


@dataclass(frozen=True, slots=True)
class HowToStep:
    """One visible step in a converter or guide how-to section."""

    position: int
    title: str
    text: str


@dataclass(frozen=True, slots=True)
class FaqItem:
    """A visible FAQ entry; schema must reuse this exact content."""

    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class ToolSeo:
    """SEO content for one already-existing functional converter."""

    slug: str
    category: str
    title: str
    description: str
    h1: str
    intro: str
    how_to: tuple[HowToStep, ...]
    benefits: tuple[str, ...]
    technical_notes: tuple[str, ...]
    accepted_formats: tuple[str, ...]
    output_formats: tuple[str, ...]
    limitations: tuple[str, ...]
    security: tuple[str, ...]
    faq: tuple[FaqItem, ...]
    related_tools: tuple[str, ...]
    related_guides: tuple[str, ...]
    updated_at: date
    status: SeoStatus

    @property
    def path(self) -> str:
        return f"/tools/{self.slug}"

    # Public vocabulary used by the content workflow. The stored field names
    # stay backward compatible with the existing rendering layer.
    @property
    def categoria(self) -> str:
        return self.category

    @property
    def meta_description(self) -> str:
        return self.description

    @property
    def beneficios(self) -> tuple[str, ...]:
        return self.benefits

    @property
    def como_usar(self) -> tuple[HowToStep, ...]:
        return self.how_to


# Canonical name for the independent SEO content layer. ``ToolSeo`` remains
# available so current integrations do not need an architectural refactor.
ToolSEO = ToolSeo


@dataclass(frozen=True, slots=True)
class CategorySeo:
    """Metadata and editorial introduction for a topical hub."""

    key: str
    path: str
    name: str
    title: str
    description: str
    h1: str
    intro: str
    editorial_points: tuple[str, ...]
    updated_at: date
    status: SeoStatus


@dataclass(frozen=True, slots=True)
class GuideSeo:
    """Planning record for an evergreen guide."""

    slug: str
    title: str
    description: str
    h1: str
    summary: str
    primary_tool: str
    related_tools: tuple[str, ...]
    outline: tuple[str, ...]
    updated_at: date
    status: SeoStatus

    @property
    def path(self) -> str:
        return f"/guides/{self.slug}"


@dataclass(frozen=True, slots=True)
class PageSeo:
    """Metadata for a public institutional or collection page."""

    key: str
    path: str
    title: str
    description: str
    h1: str
    intro: str
    updated_at: date
    status: SeoStatus
    robots: str = "index, follow"


BRAND = BrandSeo(
    name="BoostConvert",
    legal_name="BoostConvert",
    origin="https://boostconvert.com.br",
    locale="pt_BR",
    language="pt-BR",
    country="BR",
    default_title="BoostConvert | Conversores de Arquivos Online",
    default_description=(
        "Converta documentos, imagens, vídeos e áudios online com as ferramentas "
        "do BoostConvert."
    ),
)
BRAND_ORIGIN = BRAND.origin


_CATEGORIES = {
    "pdf": CategorySeo(
        key="pdf",
        path="/pdf-tools",
        name="PDF",
        title="Ferramentas de PDF Online | BoostConvert",
        description=(
            "Converta, comprima, junte e divida arquivos PDF online. Encontre as "
            "ferramentas de PDF disponíveis no BoostConvert."
        ),
        h1="Ferramentas de PDF Online",
        intro=(
            "Reúna tarefas comuns com PDF em um só lugar: transformar documentos, "
            "gerar imagens, reduzir a estrutura do arquivo, juntar páginas ou separar "
            "intervalos. Cada ferramenta informa os formatos e as limitações do processo."
        ),
        editorial_points=(
            "Conversões de PDF para documentos e imagens",
            "Organização de páginas com união e divisão",
            "Compressão estrutural e ferramentas de proteção",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "documents": CategorySeo(
        key="documents",
        path="/document-tools",
        name="Documentos",
        title="Conversores de Documentos Online | BoostConvert",
        description=(
            "Converta Word, planilhas, apresentações, textos e outros documentos entre "
            "os formatos disponíveis no BoostConvert."
        ),
        h1="Conversores de Documentos Online",
        intro=(
            "Acesse conversores para documentos de texto, planilhas, apresentações e "
            "formatos abertos. A compatibilidade final pode variar conforme fontes, "
            "recursos e estrutura presentes no arquivo original."
        ),
        editorial_points=(
            "Word, PDF e documentos de texto",
            "Planilhas CSV, XLS, XLSX e ODS",
            "Apresentações PPT, PPTX e ODP",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "images": CategorySeo(
        key="images",
        path="/image-tools",
        name="Imagens",
        title="Conversores de Imagens Online | BoostConvert",
        description=(
            "Converta imagens JPG, PNG, WebP, HEIC e SVG online. Compare formatos e "
            "escolha a saída adequada para compatibilidade, transparência ou publicação."
        ),
        h1="Conversores de Imagens Online",
        intro=(
            "Transforme imagens entre formatos raster e formatos compatíveis com a web. "
            "Antes de converter, considere transparência, compressão e suporte do programa "
            "em que o arquivo será usado."
        ),
        editorial_points=(
            "Conversões entre JPG, PNG e WebP",
            "Compatibilidade para fotos HEIC",
            "Saídas raster para arquivos SVG",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "video": CategorySeo(
        key="video",
        path="/video-tools",
        name="Vídeos",
        title="Conversores de Vídeo Online | BoostConvert",
        description=(
            "Converta vídeos MP4, MOV, AVI, MKV e WebM ou extraia o áudio de arquivos "
            "compatíveis usando as ferramentas do BoostConvert."
        ),
        h1="Conversores de Vídeo Online",
        intro=(
            "Converta contêineres de vídeo e prepare arquivos para diferentes players, "
            "dispositivos e fluxos de publicação. O tempo de processamento depende da "
            "duração, do tamanho e dos codecs do arquivo enviado."
        ),
        editorial_points=(
            "Conversões para MP4 e WebM",
            "Extração de áudio de vídeo",
            "Criação de GIF a partir de MP4",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "audio": CategorySeo(
        key="audio",
        path="/audio-tools",
        name="Áudios",
        title="Conversores de Áudio Online | BoostConvert",
        description=(
            "Converta arquivos MP3, WAV, FLAC, AAC, OGG e WMA entre os formatos de "
            "áudio disponíveis no BoostConvert."
        ),
        h1="Conversores de Áudio Online",
        intro=(
            "Prepare áudios para reprodução, compartilhamento ou edição. Formatos com "
            "perdas, como MP3, priorizam arquivos menores; WAV e FLAC atendem fluxos em "
            "que a preservação do sinal tem maior importância."
        ),
        editorial_points=(
            "Conversões para MP3",
            "Conversões entre WAV e FLAC",
            "Compatibilidade para AAC, OGG e WMA",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
}
CATEGORIES: Mapping[str, CategorySeo] = MappingProxyType(_CATEGORIES)
HUBS = CATEGORIES


_PAGES = {
    "home": PageSeo(
        key="home",
        path="/",
        title="BoostConvert | Conversores de Arquivos Online",
        description=(
            "Converta documentos, PDFs, imagens, vídeos e áudios online com as ferramentas "
            "disponíveis no BoostConvert."
        ),
        h1="Converta seus arquivos online",
        intro=(
            "Escolha uma ferramenta, envie um formato compatível e acompanhe o processamento "
            "até o download do resultado."
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "tools": PageSeo(
        key="tools",
        path="/tools",
        title="Todas as Ferramentas Online | BoostConvert",
        description=(
            "Veja todos os conversores e utilitários de PDF, documentos, imagens, vídeos e "
            "áudios disponíveis no BoostConvert."
        ),
        h1="Todas as ferramentas",
        intro="Encontre uma ferramenta por categoria ou pelo formato que você precisa converter.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "guides": PageSeo(
        key="guides",
        path="/guides",
        title="Guias de Conversão de Arquivos | BoostConvert",
        description=(
            "Aprenda a converter arquivos e a escolher formatos com os guias práticos do "
            "BoostConvert."
        ),
        h1="Guias de conversão de arquivos",
        intro=(
            "Tutoriais objetivos sobre conversão, compatibilidade e escolha de formatos "
            "para tarefas do dia a dia."
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "blog": PageSeo(
        key="blog",
        path="/blog",
        title="Blog BoostConvert | Arquivos, Formatos e Produtividade",
        description=(
            "Leia análises, novidades e conteúdos sobre formatos de arquivo, produtividade "
            "digital e conversão online."
        ),
        h1="Blog BoostConvert",
        intro="Conteúdo editorial, estudos e novidades sobre arquivos e produtividade digital.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "about": PageSeo(
        key="about",
        path="/sobre-nos",
        title="Sobre o BoostConvert | Nossa História e Missão",
        description=(
            "Conheça o BoostConvert, sua história, sua equipe e a missão de tornar tarefas "
            "com arquivos mais acessíveis."
        ),
        h1="Sobre o BoostConvert",
        intro="Conheça a história, as pessoas e os princípios que orientam o BoostConvert.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "security": PageSeo(
        key="security",
        path="/security",
        title="Segurança de Arquivos | BoostConvert",
        description=(
            "Entenda como o BoostConvert processa, protege e remove arquivos temporários "
            "durante uma conversão."
        ),
        h1="Como protegemos seus arquivos",
        intro=(
            "Conheça o fluxo de armazenamento temporário, acesso ao download e remoção dos "
            "arquivos usados nas conversões."
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "privacy": PageSeo(
        key="privacy",
        path="/privacy",
        title="Política de Privacidade | BoostConvert",
        description=(
            "Saiba quais dados o BoostConvert trata, por que eles são usados e quais são "
            "os seus direitos de privacidade."
        ),
        h1="Política de Privacidade",
        intro="Informações sobre tratamento de dados, retenção, finalidades e direitos do usuário.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "contact": PageSeo(
        key="contact",
        path="/contact",
        title="Contato e Suporte | BoostConvert",
        description="Entre em contato com o BoostConvert para suporte, dúvidas ou solicitações.",
        h1="Entre em contato",
        intro="Use os canais oficiais informados nesta página para falar com a equipe.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "terms": PageSeo(
        key="terms",
        path="/terms",
        title="Termos de Uso | BoostConvert",
        description=(
            "Consulte as condições de uso, responsabilidades e limites aplicáveis às "
            "ferramentas do BoostConvert."
        ),
        h1="Termos de Uso",
        intro="Condições para uso responsável das ferramentas e dos serviços do BoostConvert.",
        updated_at=UPDATED_AT,
        status="indexable",
    ),
}
PAGES: Mapping[str, PageSeo] = MappingProxyType(_PAGES)
INSTITUTIONAL_PAGES: Mapping[str, PageSeo] = MappingProxyType(
    {key: _PAGES[key] for key in ("about", "security", "privacy", "contact", "terms")}
)


_GUIDES = {
    "como-converter-pdf-para-word": GuideSeo(
        slug="como-converter-pdf-para-word",
        title="Como Converter PDF para Word: Guia Prático | BoostConvert",
        description=(
            "Aprenda como converter PDF para Word, quando o DOCX fica editável e quais "
            "ajustes podem ser necessários em documentos complexos."
        ),
        h1="Como converter PDF para Word",
        summary=(
            "Um guia para transformar PDF em DOCX e revisar o resultado de acordo com o "
            "tipo de conteúdo do documento."
        ),
        primary_tool="pdf-to-docx",
        related_tools=("docx-to-pdf", "pdf-to-txt", "pdf-to-jpg"),
        outline=(
            "Quando converter PDF para Word",
            "Passo a passo da conversão",
            "PDF com texto versus PDF escaneado",
            "Como revisar fontes, tabelas e quebras de página",
            "Perguntas frequentes",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "como-reduzir-pdf": GuideSeo(
        slug="como-reduzir-pdf",
        title="Como Reduzir o Tamanho de um PDF | BoostConvert",
        description=(
            "Veja como reduzir um PDF, por que o resultado varia e o que conferir antes de "
            "enviar ou arquivar o documento."
        ),
        h1="Como reduzir o tamanho de um PDF",
        summary=(
            "Entenda o que pode ocupar espaço em um PDF e como usar a compressão sem assumir "
            "uma redução fixa para todos os arquivos."
        ),
        primary_tool="pdf-compress",
        related_tools=("pdf-merge", "pdf-split", "pdf-to-jpg"),
        outline=(
            "O que aumenta o tamanho de um PDF",
            "Como comprimir o arquivo",
            "Por que alguns PDFs reduzem mais que outros",
            "Como conferir o documento compactado",
            "Alternativas quando o arquivo continua grande",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "como-transformar-jpg-em-pdf": GuideSeo(
        slug="como-transformar-jpg-em-pdf",
        title="Como Transformar JPG em PDF | BoostConvert",
        description=(
            "Aprenda a transformar imagens JPG em PDF e organize fotos ou páginas para "
            "compartilhar em um único formato."
        ),
        h1="Como transformar JPG em PDF",
        summary="Passo a passo para criar um PDF a partir de imagens JPG e revisar o arquivo final.",
        primary_tool="jpg-to-pdf",
        related_tools=("images-to-pdf", "jpg-to-png", "pdf-merge"),
        outline=(
            "Quando usar PDF em vez de imagens separadas",
            "Como preparar as imagens JPG",
            "Passo a passo da conversão",
            "Ordem, orientação e legibilidade",
            "Como compartilhar o PDF criado",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "jpg-vs-png-vs-webp": GuideSeo(
        slug="jpg-vs-png-vs-webp",
        title="JPG vs PNG vs WebP: Qual Formato Usar? | BoostConvert",
        description=(
            "Compare JPG, PNG e WebP em transparência, compressão, compatibilidade e usos "
            "comuns antes de converter suas imagens."
        ),
        h1="JPG vs PNG vs WebP",
        summary=(
            "Uma comparação prática entre três formatos de imagem para escolher a melhor "
            "saída para fotos, interfaces e páginas web."
        ),
        primary_tool="jpg-to-webp",
        related_tools=("jpg-to-png", "png-to-jpg", "png-to-webp", "webp-to-jpg"),
        outline=(
            "Como funciona a compressão em cada formato",
            "Transparência e cores",
            "Compatibilidade com navegadores e aplicativos",
            "Melhores usos para JPG, PNG e WebP",
            "Quando uma conversão não reduz o arquivo",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "como-converter-mp4-para-mp3": GuideSeo(
        slug="como-converter-mp4-para-mp3",
        title="Como Converter MP4 para MP3 | BoostConvert",
        description=(
            "Aprenda a extrair o áudio de um vídeo MP4 em MP3 e entenda como a taxa de bits "
            "influencia o arquivo final."
        ),
        h1="Como converter MP4 para MP3",
        summary=(
            "Guia para extrair uma faixa de áudio de um MP4 e escolher uma taxa de bits "
            "compatível com o uso pretendido."
        ),
        primary_tool="mp4-to-mp3",
        related_tools=("mp4-to-wav", "wav-to-mp3", "mp3-to-wav"),
        outline=(
            "O que acontece ao converter vídeo em áudio",
            "Passo a passo da conversão",
            "Como escolher a taxa de bits do MP3",
            "Limites de qualidade da fonte",
            "Uso responsável de conteúdo protegido",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "como-abrir-heic": GuideSeo(
        slug="como-abrir-heic",
        title="Como Abrir Arquivo HEIC no Celular ou PC | BoostConvert",
        description=(
            "Entenda o formato HEIC e veja como convertê-lo para JPG quando um dispositivo "
            "ou aplicativo não consegue abrir a foto."
        ),
        h1="Como abrir arquivo HEIC",
        summary=(
            "Um guia sobre compatibilidade HEIC e conversão para formatos mais amplamente "
            "aceitos, como JPG e PNG."
        ),
        primary_tool="heic-to-jpg",
        related_tools=("heic-to-png", "jpg-to-png", "images-to-pdf"),
        outline=(
            "O que é um arquivo HEIC",
            "Onde o formato é usado",
            "Como abrir HEIC em diferentes dispositivos",
            "Como converter HEIC para JPG",
            "Metadados, transparência e qualidade",
        ),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
}
GUIDES: Mapping[str, GuideSeo] = MappingProxyType(_GUIDES)


_COMMON_SECURITY = (
    "O arquivo enviado fica temporariamente em uma área privada usada pelo fluxo de conversão.",
    "O download só é servido quando o resultado pertence à área privada de conversões; após o download, a remoção dos arquivos é acionada.",
    "Resultados concluídos ou com falha que não forem baixados ficam sujeitos à rotina automática de limpeza configurada pela plataforma.",
)


def _steps(select_text: str, result_text: str) -> tuple[HowToStep, ...]:
    return (
        HowToStep(1, "Selecione o arquivo", select_text),
        HowToStep(2, "Inicie o processamento", "Confira as opções disponíveis e clique para converter."),
        HowToStep(3, "Baixe o resultado", result_text),
    )


def _faq(*items: tuple[str, str]) -> tuple[FaqItem, ...]:
    return tuple(FaqItem(question, answer) for question, answer in items)


_TOOL_SEO = {
    "pdf-to-docx": ToolSeo(
        slug="pdf-to-docx",
        category="pdf",
        title="Converter PDF para Word Online Grátis | BoostConvert",
        description=(
            "Converta PDF para Word online e gere um arquivo DOCX editável. Documentos "
            "complexos ou escaneados podem exigir ajustes depois da conversão."
        ),
        h1="Converter PDF para Word Online",
        intro=(
            "Transforme um arquivo PDF em um documento Word no formato DOCX diretamente pelo "
            "navegador. PDFs com texto selecionável tendem a oferecer mais conteúdo editável; "
            "layouts complexos e páginas escaneadas podem ser preservados visualmente."
        ),
        how_to=_steps(
            "Escolha um arquivo PDF compatível no seu dispositivo.",
            "Abra o DOCX no Word ou em outro editor compatível e revise o conteúdo.",
        ),
        benefits=(
            "Cria um arquivo DOCX que pode ser aberto em editores de texto compatíveis.",
            "Ajuda a reaproveitar textos e estruturas presentes em PDFs digitais.",
            "Não exige instalar um conversor no dispositivo.",
            "Mantém o upload no início da página para um fluxo direto.",
        ),
        technical_notes=(
            "O formato de entrada é PDF e a saída é um único arquivo DOCX.",
            "A capacidade de editar depende de como texto, fontes, imagens e páginas foram construídos no PDF.",
            "Quando a estrutura não pode ser reconstruída com segurança, partes do documento podem ser preservadas como conteúdo visual.",
        ),
        accepted_formats=("PDF",),
        output_formats=("DOCX",),
        limitations=(
            "O processo não é um serviço dedicado de OCR para reconhecer texto em imagens.",
            "Tabelas, colunas, fontes incorporadas e quebras de página podem mudar no DOCX.",
            "PDFs protegidos, corrompidos ou com recursos não suportados podem falhar.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "O Word gerado fica totalmente editável?",
                "A editabilidade depende do PDF. Texto digital costuma ser mais fácil de reconstruir; páginas escaneadas ou muito complexas podem permanecer como elementos visuais e exigir ajustes.",
            ),
            (
                "O conversor reconhece texto de PDF escaneado?",
                "O fluxo atual não é um OCR dedicado. Em documentos escaneados, a página pode ser preservada visualmente sem transformar todo o texto da imagem em texto editável.",
            ),
            (
                "A formatação do PDF será idêntica no DOCX?",
                "Não há garantia de fidelidade total. Fontes, tabelas, colunas e elementos posicionados podem se comportar de forma diferente em um editor Word.",
            ),
        ),
        related_tools=("docx-to-pdf", "pdf-to-txt", "pdf-to-jpg", "pdf-compress", "pdf-merge"),
        related_guides=("como-converter-pdf-para-word", "como-reduzir-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "docx-to-pdf": ToolSeo(
        slug="docx-to-pdf",
        category="documents",
        title="Converter Word para PDF Online Grátis | BoostConvert",
        description=(
            "Converta um documento Word DOCX para PDF online. Revise o resultado quando o "
            "arquivo usar fontes, campos ou recursos específicos do editor original."
        ),
        h1="Converter Word para PDF Online",
        intro=(
            "Transforme documentos DOCX em PDF para compartilhar uma versão de layout fixo. "
            "A conversão interpreta o conteúdo do arquivo, por isso fontes ausentes e recursos "
            "avançados podem produzir diferenças no resultado."
        ),
        how_to=_steps(
            "Escolha um documento Word no formato DOCX.",
            "Baixe o PDF e confira páginas, fontes, imagens e quebras antes de compartilhar.",
        ),
        benefits=(
            "Gera uma versão PDF adequada para leitura e compartilhamento.",
            "Evita que o destinatário precise editar o documento para visualizá-lo.",
            "Funciona pelo navegador, sem exigir instalação local.",
            "Mantém o DOCX original separado do arquivo convertido.",
        ),
        technical_notes=(
            "A entrada aceita é DOCX e a saída é PDF.",
            "O mecanismo tenta renderizar texto, imagens, tabelas e paginação do documento.",
            "A aparência depende das fontes e dos recursos presentes no DOCX.",
        ),
        accepted_formats=("DOCX",),
        output_formats=("PDF",),
        limitations=(
            "Macros, campos dinâmicos, objetos incorporados e recursos específicos do Word podem não ser reproduzidos.",
            "Fontes indisponíveis no ambiente de conversão podem ser substituídas.",
            "Documentos corrompidos ou protegidos podem não ser processados.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Converter DOCX para PDF altera o arquivo Word original?",
                "Não. O processo gera um novo PDF e não modifica o documento DOCX armazenado no seu dispositivo.",
            ),
            (
                "As fontes do Word ficam iguais no PDF?",
                "Isso depende da disponibilidade e da incorporação das fontes. Quando uma fonte não pode ser usada, pode ocorrer substituição e mudança de espaçamento.",
            ),
            (
                "Preciso ter o Microsoft Word instalado?",
                "Não. A conversão é executada pela plataforma; você só precisa de um navegador para enviar o DOCX e baixar o PDF.",
            ),
        ),
        related_tools=("pdf-to-docx", "doc-to-pdf", "odt-to-pdf", "pdf-compress", "pdf-merge"),
        related_guides=("como-converter-pdf-para-word", "como-reduzir-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "pdf-compress": ToolSeo(
        slug="pdf-compress",
        category="pdf",
        title="Comprimir PDF Online Grátis | BoostConvert",
        description=(
            "Compacte a estrutura de um PDF online para tentar reduzir seu tamanho. O ganho "
            "varia conforme imagens, fontes e otimizações já presentes no arquivo."
        ),
        h1="Comprimir PDF Online",
        intro=(
            "Reorganize e compacte estruturas internas do PDF para criar uma nova versão que "
            "pode ocupar menos espaço. PDFs já otimizados ou compostos principalmente por "
            "imagens podem apresentar pouca redução."
        ),
        how_to=_steps(
            "Selecione o PDF cujo tamanho você deseja reduzir.",
            "Baixe o novo PDF, compare o tamanho e confira todas as páginas.",
        ),
        benefits=(
            "Remove estruturas internas sem uso e aplica compactação aos objetos compatíveis.",
            "Pode facilitar o envio de documentos por canais com limite de tamanho.",
            "Mantém o resultado no formato PDF.",
            "Permite comparar o original e a nova versão antes de descartar qualquer arquivo.",
        ),
        technical_notes=(
            "O processamento aplica limpeza de objetos e compactação deflate às estruturas compatíveis do PDF.",
            "A entrada e a saída usam o formato PDF.",
            "A redução final depende de como o documento original foi produzido.",
        ),
        accepted_formats=("PDF",),
        output_formats=("PDF",),
        limitations=(
            "Não existe uma porcentagem mínima de redução garantida.",
            "Imagens já comprimidas podem continuar representando a maior parte do tamanho do arquivo.",
            "O resultado deve ser revisado, especialmente em PDFs com formulários, assinaturas ou recursos avançados.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Quanto o tamanho do PDF será reduzido?",
                "Não há um valor fixo. A redução depende das imagens, fontes, objetos repetidos e do nível de otimização que o arquivo já possuía.",
            ),
            (
                "Comprimir PDF apaga páginas ou textos?",
                "O objetivo é compactar a estrutura sem remover páginas. Ainda assim, confira o resultado antes de usar a nova versão como arquivo definitivo.",
            ),
            (
                "Por que meu PDF quase não diminuiu?",
                "Isso pode acontecer quando o PDF já está otimizado ou quando seu tamanho é dominado por imagens e outros dados que não ganham nova redução relevante.",
            ),
        ),
        related_tools=("pdf-merge", "pdf-split", "pdf-to-docx", "pdf-to-jpg", "pdf-rotate"),
        related_guides=("como-reduzir-pdf", "como-converter-pdf-para-word"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "pdf-merge": ToolSeo(
        slug="pdf-merge",
        category="pdf",
        title="Juntar PDF Online Grátis | BoostConvert",
        description=(
            "Junte dois ou mais arquivos PDF em um único documento online e mantenha as "
            "páginas na sequência definida para o envio."
        ),
        h1="Juntar PDF Online",
        intro=(
            "Combine vários PDFs em um só arquivo para organizar documentos, capítulos, "
            "comprovantes ou anexos. A ferramenta copia as páginas de cada arquivo para um "
            "novo PDF seguindo a ordem de entrada."
        ),
        how_to=(
            HowToStep(1, "Selecione os PDFs", "Envie dois ou mais arquivos PDF compatíveis."),
            HowToStep(2, "Confira a ordem", "Organize os documentos na sequência em que devem aparecer no resultado."),
            HowToStep(3, "Junte e baixe", "Inicie o processamento e baixe o PDF combinado."),
        ),
        benefits=(
            "Reúne páginas de diferentes PDFs em um único documento.",
            "Preserva os arquivos de origem sem sobrescrevê-los.",
            "Ajuda a manter anexos relacionados em uma sequência contínua.",
            "Executa a união pelo navegador sem exigir editor de PDF instalado.",
        ),
        technical_notes=(
            "A ferramenta recebe uma coleção de arquivos PDF e produz um PDF.",
            "As páginas são inseridas integralmente no documento de saída.",
            "O resultado é salvo com limpeza e compactação das estruturas compatíveis.",
        ),
        accepted_formats=("PDF",),
        output_formats=("PDF",),
        limitations=(
            "É necessário enviar pelo menos dois PDFs.",
            "A união não corrige conteúdo, orientação ou tamanhos de página diferentes.",
            "Arquivos protegidos, danificados ou incompatíveis podem impedir o processamento.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Quantos PDFs preciso enviar para juntar?",
                "A operação exige pelo menos dois arquivos PDF. O limite total aplicável aparece no fluxo de upload conforme o plano e o tamanho dos arquivos.",
            ),
            (
                "Os PDFs originais são alterados?",
                "Não. A ferramenta cria um novo PDF combinado e não altera os arquivos que permanecem no seu dispositivo.",
            ),
            (
                "Páginas com tamanhos diferentes são redimensionadas?",
                "Não necessariamente. A ferramenta combina as páginas como elas estão, então dimensões e orientações diferentes podem continuar visíveis no resultado.",
            ),
        ),
        related_tools=("pdf-split", "pdf-compress", "pdf-rotate", "pdf-to-docx", "images-to-pdf"),
        related_guides=("como-reduzir-pdf", "como-transformar-jpg-em-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "pdf-split": ToolSeo(
        slug="pdf-split",
        category="pdf",
        title="Dividir PDF Online Grátis | BoostConvert",
        description=(
            "Separe páginas ou intervalos de um PDF online. Receba os arquivos resultantes "
            "reunidos em um pacote ZIP para download."
        ),
        h1="Dividir PDF Online",
        intro=(
            "Separe um PDF por página ou informe intervalos para criar partes específicas. "
            "Cada grupo selecionado vira um novo PDF e os resultados são entregues juntos em ZIP."
        ),
        how_to=(
            HowToStep(1, "Selecione o PDF", "Escolha um arquivo PDF compatível no seu dispositivo."),
            HowToStep(2, "Defina as páginas", "Informe páginas ou intervalos, ou deixe o campo vazio para separar todas as páginas."),
            HowToStep(3, "Baixe as partes", "Inicie a divisão e baixe o pacote ZIP com os PDFs gerados."),
        ),
        benefits=(
            "Permite separar páginas individuais ou intervalos personalizados.",
            "Mantém cada grupo selecionado em formato PDF.",
            "Entrega todas as partes em um único arquivo ZIP.",
            "Não modifica o PDF original armazenado no seu dispositivo.",
        ),
        technical_notes=(
            "Intervalos aceitam números de página e sequências como 1-3,5,8-10.",
            "Sem intervalos informados, cada página é salva em um PDF separado.",
            "A saída é um arquivo ZIP contendo os PDFs resultantes.",
        ),
        accepted_formats=("PDF",),
        output_formats=("PDF", "ZIP"),
        limitations=(
            "Os números informados precisam existir no documento.",
            "A operação separa páginas; ela não edita nem recorta o conteúdo dentro de cada página.",
            "PDFs protegidos ou danificados podem não ser divididos.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Posso escolher apenas algumas páginas do PDF?",
                "Sim. Informe páginas individuais ou intervalos. Por exemplo, 1-3,5 cria um grupo com as páginas de 1 a 3 e outro com a página 5.",
            ),
            (
                "O que acontece se eu não informar páginas?",
                "A ferramenta separa todas as páginas, criando um PDF para cada uma, e reúne os resultados em um arquivo ZIP.",
            ),
            (
                "A divisão remove páginas do arquivo original?",
                "Não. Novos PDFs são criados a partir das páginas selecionadas; o original no seu dispositivo não é alterado.",
            ),
        ),
        related_tools=("pdf-merge", "pdf-compress", "pdf-rotate", "pdf-to-jpg", "pdf-extract-images"),
        related_guides=("como-reduzir-pdf",),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "pdf-to-jpg": ToolSeo(
        slug="pdf-to-jpg",
        category="pdf",
        title="Converter PDF para JPG Online Grátis | BoostConvert",
        description=(
            "Converta cada página de um PDF em uma imagem JPG online e baixe todas as páginas "
            "em um arquivo ZIP."
        ),
        h1="Converter PDF para JPG Online",
        intro=(
            "Renderize as páginas de um PDF como imagens JPG para visualizar, inserir ou "
            "compartilhar o conteúdo em aplicativos que trabalham com imagens. Cada página "
            "gera um JPG separado."
        ),
        how_to=_steps(
            "Escolha o arquivo PDF que contém as páginas a transformar.",
            "Baixe o ZIP e extraia as imagens JPG numeradas por página.",
        ),
        benefits=(
            "Gera uma imagem JPG para cada página do documento.",
            "Mantém a sequência das páginas nos nomes dos arquivos.",
            "Agrupa todas as imagens em um único pacote ZIP.",
            "Facilita o uso visual de páginas em programas sem suporte a PDF.",
        ),
        technical_notes=(
            "As páginas são renderizadas em pixels antes de serem codificadas como JPEG.",
            "A saída contém arquivos JPG nomeados pela ordem das páginas.",
            "O download final usa ZIP quando o PDF possui uma ou mais páginas.",
        ),
        accepted_formats=("PDF",),
        output_formats=("JPG", "ZIP"),
        limitations=(
            "Texto e elementos vetoriais deixam de ser editáveis e passam a fazer parte da imagem.",
            "A nitidez depende da renderização e das dimensões da página original.",
            "JPEG não oferece transparência e usa compressão com perdas.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "O PDF inteiro vira uma única imagem?",
                "Não. Cada página é convertida em um JPG separado, e as imagens são reunidas em um arquivo ZIP.",
            ),
            (
                "O texto continuará selecionável no JPG?",
                "Não. O conteúdo da página é renderizado como imagem; para reaproveitar texto, use uma conversão apropriada para DOCX ou TXT.",
            ),
            (
                "Por que recebo um arquivo ZIP?",
                "O ZIP permite entregar todas as imagens de página em um único download e preservar a numeração dos arquivos.",
            ),
        ),
        related_tools=("pdf-to-png", "pdf-to-docx", "pdf-split", "pdf-compress", "jpg-to-png"),
        related_guides=("como-converter-pdf-para-word", "como-reduzir-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "jpg-to-png": ToolSeo(
        slug="jpg-to-png",
        category="images",
        title="Converter JPG para PNG Online Grátis | BoostConvert",
        description=(
            "Converta imagens JPG ou JPEG para PNG online. A conversão muda o formato, mas "
            "não recupera detalhes já perdidos nem cria transparência automaticamente."
        ),
        h1="Converter JPG para PNG Online",
        intro=(
            "Transforme uma imagem JPG em PNG para usar um formato sem perdas em edições e "
            "aplicativos compatíveis. Os pixels visíveis do JPG são mantidos, inclusive "
            "eventuais artefatos que já existiam na imagem de origem."
        ),
        how_to=_steps(
            "Selecione uma imagem com extensão JPG ou JPEG.",
            "Baixe o arquivo PNG e confira dimensões e cores no aplicativo de destino.",
        ),
        benefits=(
            "Gera um PNG a partir dos pixels decodificados do JPG.",
            "Evita uma nova etapa de compressão JPEG no arquivo de saída.",
            "Amplia a compatibilidade com fluxos que exigem PNG.",
            "Funciona no navegador sem instalar editor de imagens.",
        ),
        technical_notes=(
            "JPG/JPEG usa compressão com perdas; PNG usa compactação sem perdas.",
            "A conversão não vetoriza a imagem nem aumenta sua resolução real.",
            "Um JPG não contém canal alfa, portanto o PNG gerado não ganha fundo transparente automaticamente.",
        ),
        accepted_formats=("JPG", "JPEG"),
        output_formats=("PNG",),
        limitations=(
            "Converter para PNG não recupera qualidade perdida na criação do JPG.",
            "O PNG pode ficar maior que o JPG, especialmente em fotografias.",
            "Metadados específicos do arquivo original podem não aparecer na saída.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Converter JPG para PNG perde qualidade?",
                "O PNG é salvo sem uma nova compressão com perdas, mas só pode preservar os pixels que já existem no JPG; detalhes anteriormente descartados não são recuperados.",
            ),
            (
                "O fundo fica transparente depois da conversão?",
                "Não automaticamente. JPG não armazena transparência, então é necessário remover o fundo em uma ferramenta de edição se você precisar de canal alfa.",
            ),
            (
                "Por que o PNG pode ficar maior?",
                "Fotografias costumam compactar melhor em JPEG. Como PNG usa outra estratégia e preserva os pixels sem perdas, o arquivo pode ocupar mais espaço.",
            ),
        ),
        related_tools=("png-to-jpg", "jpg-to-webp", "png-to-webp", "webp-to-png", "jpg-to-pdf"),
        related_guides=("jpg-vs-png-vs-webp", "como-transformar-jpg-em-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "png-to-jpg": ToolSeo(
        slug="png-to-jpg",
        category="images",
        title="Converter PNG para JPG Online Grátis | BoostConvert",
        description=(
            "Converta PNG para JPG online e escolha a qualidade disponível. Áreas transparentes "
            "são aplicadas sobre fundo branco porque JPEG não aceita canal alfa."
        ),
        h1="Converter PNG para JPG Online",
        intro=(
            "Transforme uma imagem PNG em JPG para maior compatibilidade com aplicativos e "
            "fluxos voltados a fotografias. Como JPEG não suporta transparência, pixels "
            "transparentes são compostos sobre branco no resultado."
        ),
        how_to=_steps(
            "Escolha uma imagem PNG no seu dispositivo.",
            "Baixe o JPG e confira principalmente áreas que eram transparentes.",
        ),
        benefits=(
            "Cria um JPG amplamente aceito por visualizadores e serviços.",
            "Oferece opções de qualidade JPEG no fluxo da ferramenta.",
            "Pode produzir arquivos menores para conteúdo fotográfico.",
            "Converte automaticamente a imagem para o espaço de cor compatível com JPEG.",
        ),
        technical_notes=(
            "A saída JPEG usa compressão com perdas e não suporta transparência.",
            "O canal alfa, quando existe, é composto sobre um fundo branco.",
            "A ferramenta preserva o perfil ICC quando ele está disponível para o processamento.",
        ),
        accepted_formats=("PNG",),
        output_formats=("JPG",),
        limitations=(
            "Transparência é substituída por fundo branco.",
            "Linhas, textos e gráficos podem apresentar artefatos de compressão JPEG.",
            "A conversão não aumenta resolução nem recupera detalhes ausentes.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "O que acontece com a transparência do PNG?",
                "Como JPG não tem canal alfa, as áreas transparentes são compostas sobre um fundo branco.",
            ),
            (
                "Converter PNG para JPG sempre deixa o arquivo menor?",
                "Não. Fotografias frequentemente ficam menores, mas o resultado depende das dimensões, cores, conteúdo e qualidade escolhida.",
            ),
            (
                "JPG é indicado para logos e textos?",
                "Nem sempre. A compressão JPEG pode criar artefatos em bordas nítidas; para logos, interfaces e transparência, PNG pode ser mais adequado.",
            ),
        ),
        related_tools=("jpg-to-png", "png-to-webp", "jpg-to-webp", "webp-to-jpg", "images-to-pdf"),
        related_guides=("jpg-vs-png-vs-webp", "como-transformar-jpg-em-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "jpg-to-webp": ToolSeo(
        slug="jpg-to-webp",
        category="images",
        title="Converter JPG para WebP Online Grátis | BoostConvert",
        description=(
            "Converta JPG para WebP online. A saída é codificada em WebP sem perdas a partir "
            "dos pixels do JPG, sem recuperar detalhes já descartados na origem."
        ),
        h1="Converter JPG para WebP Online",
        intro=(
            "Transforme imagens JPG em WebP para usar um formato moderno em navegadores e "
            "aplicativos compatíveis. O BoostConvert gera WebP sem perdas a partir da imagem "
            "decodificada; por isso, o tamanho final não é necessariamente menor."
        ),
        how_to=_steps(
            "Selecione uma imagem JPG ou JPEG.",
            "Baixe o WebP e valide sua abertura no navegador ou aplicativo em que será usado.",
        ),
        benefits=(
            "Gera WebP com codificação sem perdas a partir dos pixels de origem.",
            "Mantém as dimensões da imagem durante a troca de formato.",
            "Preserva o perfil ICC quando ele está disponível para o processamento.",
            "Atende páginas e fluxos que aceitam o formato WebP.",
        ),
        technical_notes=(
            "O JPG é decodificado e salvo como WebP lossless.",
            "A conversão não adiciona transparência a uma imagem JPG.",
            "O ganho de tamanho varia porque a saída prioriza preservação dos pixels decodificados.",
        ),
        accepted_formats=("JPG", "JPEG"),
        output_formats=("WEBP",),
        limitations=(
            "O arquivo WebP pode não ficar menor que o JPG original.",
            "Detalhes perdidos na compressão JPEG não são recuperados.",
            "Programas antigos podem não oferecer suporte completo ao WebP.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "O WebP gerado usa compressão com perdas?",
                "Nesta ferramenta, a imagem decodificada do JPG é salva como WebP sem perdas. Isso evita nova perda, mas não restaura detalhes já ausentes no JPG.",
            ),
            (
                "Converter JPG para WebP sempre reduz o tamanho?",
                "Não. Como a saída é WebP sem perdas, o resultado depende do conteúdo e pode até ficar maior que um JPG já bem compactado.",
            ),
            (
                "WebP funciona em qualquer aplicativo?",
                "O suporte é amplo em navegadores modernos, mas alguns aplicativos antigos podem exigir JPG ou PNG.",
            ),
        ),
        related_tools=("jpg-to-png", "png-to-webp", "webp-to-jpg", "webp-to-png", "png-to-jpg"),
        related_guides=("jpg-vs-png-vs-webp",),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "webp-to-jpg": ToolSeo(
        slug="webp-to-jpg",
        category="images",
        title="Converter WebP para JPG Online Grátis | BoostConvert",
        description=(
            "Converta imagens WebP para JPG online e escolha a qualidade JPEG. Crie uma "
            "saída compatível com aplicativos e formulários que ainda não aceitam WebP."
        ),
        h1="Converter WebP para JPG Online",
        intro=(
            "Transforme uma imagem WebP em JPG quando o programa, formulário ou dispositivo "
            "de destino não aceitar o formato original. A ferramenta gera uma nova imagem e "
            "mantém o arquivo WebP original inalterado."
        ),
        how_to=_steps(
            "Selecione uma imagem com extensão WebP.",
            "Baixe o JPG e confira cores, fundo e nível de detalhe antes de compartilhar.",
        ),
        benefits=(
            "Cria uma imagem JPG aceita por uma ampla variedade de aplicativos.",
            "Mantém as dimensões visuais durante a troca de formato.",
            "Permite escolher a qualidade JPEG disponível na ferramenta.",
            "Preserva o perfil de cores quando ele está disponível para o processamento.",
        ),
        technical_notes=(
            "A imagem WebP é decodificada e salva como JPEG.",
            "JPG não oferece transparência e usa compressão com perdas.",
            "Áreas transparentes são compostas sobre um fundo sólido na saída.",
        ),
        accepted_formats=("WEBP",),
        output_formats=("JPG",),
        limitations=(
            "Animações WebP não podem ser representadas em uma única imagem JPG.",
            "Transparência não existe no formato JPG e será substituída por um fundo sólido.",
            "A conversão não aumenta a resolução nem recupera detalhes ausentes.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Por que converter WebP para JPG?",
                "JPG ainda é exigido por alguns aplicativos, editores e formulários. A conversão ajuda quando o destino não aceita WebP.",
            ),
            (
                "O que acontece com a transparência do WebP?",
                "JPG não suporta canal alfa. As áreas transparentes precisam ser compostas sobre um fundo sólido na imagem resultante.",
            ),
            (
                "Um WebP animado continua animado em JPG?",
                "Não. JPG representa uma imagem estática e não preserva a animação do arquivo WebP.",
            ),
        ),
        related_tools=("jpg-to-webp", "webp-to-png", "png-to-jpg", "jpg-to-png", "images-to-pdf"),
        related_guides=("jpg-vs-png-vs-webp", "como-transformar-jpg-em-pdf"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "heic-to-jpg": ToolSeo(
        slug="heic-to-jpg",
        category="images",
        title="Converter HEIC para JPG Online Grátis | BoostConvert",
        description=(
            "Converta fotos HEIC para JPG online e escolha a qualidade JPEG disponível. "
            "A saída facilita a abertura em aplicativos sem suporte a HEIC."
        ),
        h1="Converter HEIC para JPG Online",
        intro=(
            "Transforme fotos HEIC, comuns em dispositivos Apple, em imagens JPG para ampliar "
            "a compatibilidade com visualizadores, editores e formulários. A conversão cria "
            "um novo arquivo e não altera a foto original no dispositivo."
        ),
        how_to=_steps(
            "Escolha uma foto com extensão HEIC.",
            "Baixe o JPG e confira orientação, cores e detalhes antes de compartilhar.",
        ),
        benefits=(
            "Gera um JPG aceito por uma ampla variedade de aplicativos.",
            "Oferece opções de qualidade JPEG no fluxo da ferramenta.",
            "Preserva o perfil ICC quando ele está disponível para o processamento.",
            "Não exige instalar um codec HEIC no dispositivo para realizar a conversão.",
        ),
        technical_notes=(
            "A ferramenta decodifica HEIC e salva a imagem visível como JPEG.",
            "JPEG usa compressão com perdas e não oferece canal alfa.",
            "Quando há transparência, a imagem é composta sobre fundo branco antes de salvar.",
        ),
        accepted_formats=("HEIC",),
        output_formats=("JPG",),
        limitations=(
            "Sequências, profundidade e outros recursos específicos do contêiner HEIC podem não ser representados em um único JPG.",
            "Metadados específicos, como dados de captura, podem não ser preservados na saída.",
            "Arquivos HEIC inválidos ou com codificação não suportada podem falhar.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Por que converter HEIC para JPG?",
                "JPG é aceito por mais aplicativos e formulários. A conversão é útil quando o programa de destino não consegue abrir HEIC.",
            ),
            (
                "A foto original é modificada?",
                "Não. Um novo JPG é gerado; o arquivo HEIC que permanece no seu dispositivo não é alterado.",
            ),
            (
                "Os metadados da foto serão mantidos?",
                "Não há garantia de preservação de todos os metadados. Se data, localização ou informações de captura forem importantes, verifique o JPG antes de descartar qualquer cópia.",
            ),
        ),
        related_tools=("heic-to-png", "jpg-to-png", "jpg-to-webp", "images-to-pdf", "png-to-jpg"),
        related_guides=("como-abrir-heic", "jpg-vs-png-vs-webp"),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "mp4-to-mp3": ToolSeo(
        slug="mp4-to-mp3",
        category="video",
        title="Converter MP4 para MP3 Online Grátis | BoostConvert",
        description=(
            "Extraia o áudio de um vídeo MP4 e converta para MP3 online. Escolha entre as "
            "taxas de bits disponíveis antes do processamento."
        ),
        h1="Converter MP4 para MP3 Online",
        intro=(
            "Crie um arquivo MP3 a partir da faixa de áudio de um vídeo MP4. O vídeo é "
            "descartado na saída e o áudio é codificado no bitrate escolhido para reprodução "
            "e compartilhamento em aplicativos compatíveis."
        ),
        how_to=_steps(
            "Selecione um vídeo MP4 que contenha uma faixa de áudio compatível.",
            "Baixe o MP3 e confira duração, volume e reprodução.",
        ),
        benefits=(
            "Extrai o áudio sem manter as imagens do vídeo no resultado.",
            "Oferece opções de bitrate de 128, 192, 256 e 320 kbps.",
            "Gera MP3 compatível com muitos players e dispositivos.",
            "Executa o processamento sem exigir editor de vídeo local.",
        ),
        technical_notes=(
            "O fluxo ignora o vídeo e codifica a faixa de áudio com o codec MP3 LAME.",
            "A qualidade de saída pode ser configurada entre os bitrates oferecidos pela interface.",
            "O MP3 contém apenas áudio; imagens, legendas e demais faixas não fazem parte do resultado.",
        ),
        accepted_formats=("MP4",),
        output_formats=("MP3",),
        limitations=(
            "O MP4 precisa conter uma faixa de áudio compatível.",
            "A conversão para MP3 é com perdas e não melhora a qualidade da fonte.",
            "Arquivos longos, grandes ou com codecs incomuns podem levar mais tempo ou falhar.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "O arquivo MP3 mantém o vídeo?",
                "Não. A saída contém apenas o áudio extraído; imagens, legendas e a faixa de vídeo são descartadas.",
            ),
            (
                "Qual bitrate devo escolher?",
                "Bitrates maiores preservam mais dados, mas geram arquivos maiores. Eles não recuperam qualidade que já não existe na faixa de áudio original.",
            ),
            (
                "Posso converter um MP4 sem áudio?",
                "Não há áudio para extrair nesse caso, portanto o processamento não consegue gerar um MP3 útil.",
            ),
        ),
        related_tools=("mp4-to-wav", "wav-to-mp3", "mp3-to-wav", "mp4-to-webm", "mp4-to-gif"),
        related_guides=("como-converter-mp4-para-mp3",),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
    "wav-to-mp3": ToolSeo(
        slug="wav-to-mp3",
        category="audio",
        title="Converter WAV para MP3 Online Grátis | BoostConvert",
        description=(
            "Converta áudio WAV para MP3 online e escolha entre as taxas de bits disponíveis "
            "para equilibrar tamanho e qualidade."
        ),
        h1="Converter WAV para MP3 Online",
        intro=(
            "Transforme um arquivo WAV em MP3 para obter uma saída amplamente compatível e, "
            "em muitos casos, menor. O áudio é recodificado com perdas no bitrate escolhido, "
            "portanto o resultado não é uma cópia sem perdas do WAV."
        ),
        how_to=_steps(
            "Escolha um arquivo de áudio WAV compatível.",
            "Baixe o MP3 e compare a reprodução e o tamanho com o arquivo original.",
        ),
        benefits=(
            "Gera MP3 compatível com muitos players, celulares e sistemas de áudio.",
            "Oferece opções de bitrate de 128, 192, 256 e 320 kbps.",
            "Pode reduzir de forma relevante o tamanho de arquivos WAV sem compressão.",
            "Não exige instalar um programa de edição de áudio.",
        ),
        technical_notes=(
            "O WAV é decodificado e recodificado com o codec MP3 LAME.",
            "A interface oferece bitrates constantes entre 128 e 320 kbps.",
            "A redução de tamanho depende da duração, dos canais, da taxa de amostragem e do WAV de origem.",
        ),
        accepted_formats=("WAV",),
        output_formats=("MP3",),
        limitations=(
            "MP3 usa compressão com perdas e descarta parte dos dados de áudio.",
            "Escolher bitrate acima da qualidade da fonte não recupera detalhes.",
            "WAVs danificados, muito grandes ou com codificações incomuns podem falhar.",
        ),
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                "Converter WAV para MP3 perde qualidade?",
                "Sim, MP3 usa compressão com perdas. Um bitrate maior pode reduzir perdas perceptíveis, mas não torna o processo sem perdas.",
            ),
            (
                "O MP3 sempre fica menor que o WAV?",
                "Em WAVs sem compressão, normalmente fica menor, mas o tamanho exato depende da duração e das características dos dois arquivos.",
            ),
            (
                "Qual bitrate gera o menor arquivo?",
                "Entre as opções disponíveis, 128 kbps produz o menor arquivo. Bitrates maiores retêm mais dados e aumentam o tamanho.",
            ),
        ),
        related_tools=("mp3-to-wav", "wav-to-flac", "flac-to-mp3", "mp4-to-mp3", "ogg-to-mp3"),
        related_guides=("como-converter-mp4-para-mp3",),
        updated_at=UPDATED_AT,
        status="indexable",
    ),
}
TOOL_SEO: Mapping[str, ToolSeo] = MappingProxyType(_TOOL_SEO)
TOOLS_SEO = TOOL_SEO
PRIORITY_TOOL_SLUGS = tuple(_TOOL_SEO)


_FORMAT_LABELS = MappingProxyType(
    {
        "aac": "AAC",
        "avi": "AVI",
        "csv": "CSV",
        "doc": "DOC",
        "docx": "DOCX",
        "files": "arquivos",
        "flac": "FLAC",
        "gif": "GIF",
        "heic": "HEIC",
        "html": "HTML",
        "images": "imagens",
        "jpg": "JPG",
        "jpeg": "JPEG",
        "json": "JSON",
        "md": "Markdown",
        "mkv": "MKV",
        "mov": "MOV",
        "mp3": "MP3",
        "mp4": "MP4",
        "odp": "ODP",
        "ods": "ODS",
        "odt": "ODT",
        "ogg": "OGG",
        "pdf": "PDF",
        "png": "PNG",
        "ppt": "PPT",
        "pptx": "PPTX",
        "svg": "SVG",
        "txt": "TXT",
        "wav": "WAV",
        "webm": "WebM",
        "webp": "WebP",
        "wma": "WMA",
        "xls": "XLS",
        "xlsx": "XLSX",
        "zip": "ZIP",
    }
)

_IMAGE_FORMATS = frozenset({"heic", "images", "jpeg", "jpg", "png", "svg", "webp"})
_VIDEO_FORMATS = frozenset({"avi", "mkv", "mov", "mp4", "webm", "gif"})
_AUDIO_FORMATS = frozenset({"aac", "flac", "mp3", "ogg", "wav", "wma"})

_CATEGORY_RELATED = MappingProxyType(
    {
        "pdf": ("pdf-compress", "pdf-merge", "pdf-split", "pdf-to-docx", "pdf-to-jpg"),
        "documents": ("pdf-to-docx", "docx-to-pdf", "pdf-compress", "pdf-merge"),
        "images": ("jpg-to-png", "png-to-jpg", "jpg-to-webp", "heic-to-jpg"),
        "video": ("mp4-to-mp3", "mp4-to-wav", "mp4-to-webm", "mov-to-mp4"),
        "audio": ("wav-to-mp3", "mp4-to-mp3", "flac-to-mp3", "mp3-to-wav"),
    }
)

_CATEGORY_GUIDES = MappingProxyType(
    {
        "pdf": ("como-converter-pdf-para-word", "como-reduzir-pdf", "como-transformar-jpg-em-pdf"),
        "documents": ("como-converter-pdf-para-word", "como-transformar-jpg-em-pdf"),
        "images": ("jpg-vs-png-vs-webp", "como-abrir-heic", "como-transformar-jpg-em-pdf"),
        "video": ("como-converter-mp4-para-mp3",),
        "audio": ("como-converter-mp4-para-mp3",),
    }
)

_SPECIAL_ACTIONS = MappingProxyType(
    {
        "pdf-rotate": ("Girar PDF", "Gire as páginas de um arquivo PDF e gere uma nova versão."),
        "pdf-protect": ("Proteger PDF com Senha", "Adicione uma senha a um PDF que você tem autorização para proteger."),
        "pdf-unlock": ("Desbloquear PDF", "Remova a senha de um PDF quando você tem autorização e conhece a credencial necessária."),
        "pdf-extract-images": ("Extrair Imagens do PDF", "Extraia imagens incorporadas em um PDF e baixe os arquivos resultantes."),
        "pdf-edit": ("Editar PDF", "Faça os ajustes simples oferecidos pela ferramenta e gere uma nova versão do PDF."),
    }
)


def normalize_slug(value: str) -> str:
    """Return a validated converter slug from a slug or public/processing path."""

    slug = str(value or "").strip().lower().split("?", 1)[0].split("#", 1)[0]
    for prefix in ("/tools/", "/convert/"):
        if slug.startswith(prefix):
            slug = slug[len(prefix) :]
            break
    slug = slug.strip("/")
    if not slug or re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) is None:
        raise ValueError(f"Invalid SEO tool slug: {value!r}")
    return slug


def public_url(path: str = "") -> str:
    """Build a public URL without depending on Flask, a request, or app config."""

    clean_path = str(path or "").strip()
    if not clean_path:
        return BRAND.origin
    return f"{BRAND.origin}/{clean_path.lstrip('/')}"


def _format_label(value: str) -> str:
    key = value.strip().lower()
    return _FORMAT_LABELS.get(key, key.replace("-", " ").upper())


def _infer_category(slug: str, source: str | None, target: str | None) -> str:
    formats = {item for item in (source, target) if item}
    if slug.startswith("pdf-") or "pdf" in formats:
        return "pdf"
    if formats & _IMAGE_FORMATS:
        return "images"
    if source in _VIDEO_FORMATS:
        return "video"
    if formats & _AUDIO_FORMATS:
        return "audio"
    if formats & _VIDEO_FORMATS:
        return "video"
    return "documents"


def _parse_accept(accept: str | None, source: str | None) -> tuple[str, ...]:
    if accept:
        formats = tuple(
            dict.fromkeys(
                _format_label(part.strip().lstrip("."))
                for part in str(accept).split(",")
                if part.strip().lstrip(".")
            )
        )
        if formats:
            return formats
    return (_format_label(source),) if source else ("Consulte a ferramenta",)


def _fallback_related(slug: str, category: str) -> tuple[str, ...]:
    return tuple(item for item in _CATEGORY_RELATED[category] if item != slug)[:5]


def build_fallback_tool_seo(
    slug: str,
    *,
    name: str | None = None,
    accept: str | None = None,
) -> ToolSeo:
    """Build restrained SEO copy for a slug validated by the functional catalog.

    The function does not verify that a converter exists.  Callers must perform
    that check before exposing the returned record on an indexable page.
    """

    normalized = normalize_slug(slug)
    source: str | None = None
    target: str | None = None
    if "-to-" in normalized:
        source, target = normalized.split("-to-", 1)

    category = _infer_category(normalized, source, target)
    accepted_formats = _parse_accept(accept, source)

    if source and target:
        source_label = _format_label(source)
        target_label = _format_label(target)
        h1 = f"Converter {source_label} para {target_label} Online"
        title = f"{h1} | BoostConvert"
        description = (
            f"Converta arquivos {source_label} para {target_label} online usando a ferramenta "
            "do BoostConvert. Confira o resultado antes de substituir o arquivo original."
        )
        intro = (
            f"Transforme um arquivo {source_label} em {target_label} diretamente pelo navegador. "
            "O resultado depende da estrutura, dos recursos e da integridade do arquivo enviado."
        )
        output_formats = (target_label,)
        action = f"converter {source_label} para {target_label}"
        technical_notes = (
            f"A ferramenta recebe {', '.join(accepted_formats)} e gera uma saída {target_label}.",
            "A conversão cria um novo arquivo e não altera a cópia que permanece no dispositivo.",
            "Compatibilidade, aparência e tamanho final dependem dos dados presentes na origem.",
        )
        limitations = (
            "Arquivos protegidos, corrompidos ou com recursos não suportados podem falhar.",
            "A troca de formato não aumenta a qualidade ou a resolução real do conteúdo original.",
            "Revise o resultado no aplicativo em que ele será usado.",
        )
    else:
        action_name, action_description = _SPECIAL_ACTIONS.get(
            normalized,
            (
                str(name or normalized.replace("-", " ")).replace("->", " para ").strip().title(),
                "Use a ferramenta online e gere um novo arquivo a partir de uma entrada compatível.",
            ),
        )
        h1 = f"{action_name} Online"
        title = f"{h1} | BoostConvert"
        description = f"{action_description} Confira o resultado antes de substituir o arquivo original."
        intro = (
            f"{action_description} O processamento cria um novo resultado e mantém separado "
            "o arquivo que permanece no seu dispositivo."
        )
        output_formats = ("Consulte a ferramenta",)
        action = action_name.lower()
        technical_notes = (
            f"Formatos aceitos: {', '.join(accepted_formats)}.",
            "As opções exibidas pela própria ferramenta definem o processamento disponível.",
            "O resultado deve ser conferido antes de substituir ou descartar o arquivo original.",
        )
        limitations = (
            "Arquivos protegidos, corrompidos ou com recursos não suportados podem falhar.",
            "Os resultados dependem da estrutura e da integridade do arquivo enviado.",
            "A ferramenta não corrige automaticamente problemas existentes no conteúdo original.",
        )

    return ToolSeo(
        slug=normalized,
        category=category,
        title=title,
        description=description,
        h1=h1,
        intro=intro,
        how_to=_steps(
            f"Escolha um dos formatos aceitos: {', '.join(accepted_formats)}.",
            "Baixe o novo arquivo e confira o conteúdo no aplicativo de destino.",
        ),
        benefits=(
            "Executa o processamento diretamente pelo fluxo online da plataforma.",
            "Gera um novo arquivo sem alterar a cópia mantida no dispositivo.",
            "Informa os formatos aceitos antes do envio.",
        ),
        technical_notes=technical_notes,
        accepted_formats=accepted_formats,
        output_formats=output_formats,
        limitations=limitations,
        security=_COMMON_SECURITY,
        faq=_faq(
            (
                f"Como {action} online?",
                "Selecione um arquivo aceito, inicie o processamento e baixe o resultado quando a conversão terminar.",
            ),
            (
                "O arquivo original é alterado?",
                "Não. A plataforma cria um novo resultado; a cópia que está no seu dispositivo permanece separada.",
            ),
            (
                "O resultado será idêntico ao original?",
                "Não há garantia de identidade entre formatos. Estrutura, codecs, fontes, transparência ou outros recursos podem se comportar de forma diferente.",
            ),
        ),
        related_tools=_fallback_related(normalized, category),
        related_guides=_CATEGORY_GUIDES[category],
        updated_at=UPDATED_AT,
        status="indexable",
    )


def get_tool_seo(
    slug: str,
    *,
    name: str | None = None,
    accept: str | None = None,
) -> ToolSeo:
    """Return explicit priority content or a restrained functional-tool fallback."""

    normalized = normalize_slug(slug)
    return TOOL_SEO.get(normalized) or build_fallback_tool_seo(
        normalized,
        name=name,
        accept=accept,
    )


def get_hub_seo(key: str) -> CategorySeo:
    """Return hub metadata by category key."""

    return CATEGORIES[str(key).strip().lower()]


def get_page_seo(key: str) -> PageSeo:
    """Return institutional or collection-page metadata by key."""

    return PAGES[str(key).strip().lower()]


def as_serializable_dict(record: Any) -> dict[str, Any]:
    """Convert a catalog dataclass to a JSON-friendly dictionary."""

    if not is_dataclass(record) or isinstance(record, type):
        raise TypeError("Expected a catalog dataclass instance.")

    def serialize(value: Any) -> Any:
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [serialize(item) for item in value]
        return value

    data = serialize(asdict(record))
    if isinstance(record, (ToolSeo, GuideSeo)):
        data["path"] = record.path
        data["url"] = public_url(record.path)
    elif hasattr(record, "path"):
        data["url"] = public_url(record.path)
    return data


to_dict = as_serializable_dict


__all__ = (
    "BRAND",
    "BRAND_ORIGIN",
    "CATEGORIES",
    "GUIDES",
    "HUBS",
    "INSTITUTIONAL_PAGES",
    "PAGES",
    "PRIORITY_TOOL_SLUGS",
    "TOOL_SEO",
    "TOOLS_SEO",
    "BrandSeo",
    "CategorySeo",
    "FaqItem",
    "GuideSeo",
    "HowToStep",
    "PageSeo",
    "SeoStatus",
    "ToolSeo",
    "as_serializable_dict",
    "build_fallback_tool_seo",
    "get_hub_seo",
    "get_page_seo",
    "get_tool_seo",
    "normalize_slug",
    "public_url",
    "to_dict",
)
