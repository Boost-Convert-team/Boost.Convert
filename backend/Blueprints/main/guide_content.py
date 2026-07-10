"""Conteúdo editorial publicável dos guias do BoostConvert.

O módulo mantém texto editorial separado do catálogo e da lógica de conversão. As
estruturas são imutáveis para que possam ser compartilhadas entre rotas, templates
e testes sem que uma requisição altere o conteúdo das demais.
"""

from types import MappingProxyType
from typing import Mapping, Optional, Sequence


GuideSection = Mapping[str, object]


def _section(
    heading: str,
    paragraphs: Sequence[str],
    *,
    bullets: Optional[Sequence[str]] = None,
    steps: Optional[Sequence[str]] = None,
) -> GuideSection:
    """Cria uma seção editorial profundamente imutável."""

    data = {
        "heading": heading,
        "paragraphs": tuple(paragraphs),
    }
    if bullets:
        data["bullets"] = tuple(bullets)
    if steps:
        data["steps"] = tuple(steps)
    return MappingProxyType(data)


_GUIDE_CONTENT = {
    "como-converter-pdf-para-word": (
        _section(
            "Quando vale a pena converter PDF para Word",
            (
                "O PDF foi criado para manter a aparência de uma página em diferentes telas e impressoras. O DOCX, por outro lado, é voltado à edição. Converter faz sentido quando você precisa corrigir um texto, reaproveitar trechos, atualizar um contrato próprio ou reorganizar um documento cujo arquivo original não está mais disponível.",
                "A conversão não transforma todo PDF em uma cópia perfeita do arquivo que lhe deu origem. Um PDF pode guardar palavras em blocos separados, fontes incorporadas, imagens e coordenadas de posicionamento, enquanto o Word trabalha com parágrafos, estilos e fluxo de página. Por isso, documentos com colunas, formulários ou muitas tabelas costumam exigir uma revisão maior.",
            ),
            bullets=(
                "Use DOCX quando a prioridade for editar e reorganizar o conteúdo.",
                "Mantenha o PDF original para comparação e para preservar uma versão de referência.",
                "Confirme que você tem permissão para modificar o documento antes de convertê-lo.",
            ),
        ),
        _section(
            "Como fazer a conversão no BoostConvert",
            (
                "A ferramenta PDF para DOCX recebe um arquivo PDF e gera um documento compatível com editores que aceitam o formato DOCX. O processo acontece no navegador e no serviço de conversão; não é necessário instalar um programa adicional. O tempo depende do tamanho, da quantidade de páginas e da complexidade do arquivo.",
            ),
            steps=(
                "Abra a ferramenta PDF para DOCX e selecione o PDF que deseja converter.",
                "Confira se o arquivo escolhido é o correto e inicie a conversão.",
                "Aguarde o processamento sem fechar a página.",
                "Baixe o DOCX concluído e abra-o em um editor compatível.",
                "Compare o resultado com o PDF original antes de compartilhar ou substituir qualquer versão.",
            ),
        ),
        _section(
            "PDF com texto e PDF escaneado não são a mesma coisa",
            (
                "Em um PDF com texto real, normalmente é possível selecionar palavras e pesquisar termos no leitor de PDF. Esse tipo de arquivo oferece à conversão elementos textuais que podem ser reconstruídos no DOCX, embora a diagramação ainda possa mudar.",
                "Já um PDF escaneado pode conter somente fotografias das páginas. A ferramenta do BoostConvert não oferece OCR nesta conversão, portanto não promete reconhecer letras dentro dessas imagens. Se você não consegue selecionar uma palavra no PDF de origem, o DOCX pode preservar páginas como conteúdo visual ou não produzir texto editável. Nesse caso, é necessário usar uma solução específica de reconhecimento óptico e revisar o resultado manualmente.",
            ),
        ),
        _section(
            "O que revisar no documento convertido",
            (
                "Abra o DOCX e percorra todas as páginas, mesmo que a primeira pareça correta. Observe títulos, listas, notas de rodapé, cabeçalhos, caracteres acentuados e mudanças inesperadas de fonte. Quebras de linha podem aparecer em lugares diferentes porque o editor recalcula o texto de acordo com a fonte disponível e a configuração da página.",
                "Tabelas, caixas de texto, gráficos e documentos em várias colunas merecem atenção especial. Confira também números, datas e cláusulas importantes diretamente no PDF original. Se a aparência final for indispensável, faça as edições no DOCX e gere um novo PDF apenas depois da conferência.",
            ),
            bullets=(
                "Verifique margens, orientação e tamanho do papel.",
                "Revise tabelas célula por célula e confirme a ordem de leitura das colunas.",
                "Procure fontes substituídas, símbolos ausentes e imagens deslocadas.",
                "Use o corretor do editor como apoio, não como substituto da comparação com o original.",
            ),
        ),
        _section(
            "Como obter um resultado mais fácil de editar",
            (
                "Prefira o PDF mais próximo da origem: arquivos exportados diretamente de um editor tendem a carregar uma estrutura mais útil do que cópias impressas e escaneadas várias vezes. Evite recomprimir ou converter o mesmo documento repetidamente antes de gerar o DOCX, pois cada etapa pode simplificar fontes, imagens ou posicionamentos.",
                "Quando você precisa apenas de um trecho curto, também pode considerar extrair o texto e refazer a formatação no Word. Para documentos longos, trabalhe em uma cópia, aplique estilos de título e parágrafo de forma consistente e salve versões intermediárias. Isso torna a revisão mais previsível sem pressupor que a conversão reconstrua o arquivo original.",
            ),
        ),
    ),
    "como-reduzir-pdf": (
        _section(
            "Por que alguns arquivos PDF ficam tão grandes",
            (
                "O tamanho de um PDF depende do que há dentro dele. Fotografias em alta resolução, páginas escaneadas, gráficos detalhados e fontes incorporadas podem ocupar muito mais espaço do que texto simples. Um único PDF também pode carregar imagens maiores do que o necessário para a leitura em tela ou manter recursos repetidos gerados pelo programa de origem.",
                "Nem todo arquivo tem a mesma margem para redução. Se as imagens e os dados internos já estiverem comprimidos, uma nova compactação pode produzir pouca diferença. Em contrapartida, um documento criado a partir de fotos grandes costuma oferecer mais oportunidades de economia, possivelmente com alguma mudança visual conforme o nível escolhido.",
            ),
        ),
        _section(
            "Como comprimir um PDF no BoostConvert",
            (
                "A ferramenta oferece os níveis leve, equilibrado e forte. Eles permitem escolher a intensidade do processamento, mas não representam uma porcentagem fixa de redução. O resultado sempre depende do conteúdo do arquivo. Para documentos importantes, comece pelo nível equilibrado e compare o arquivo gerado com o original antes de tentar uma configuração mais intensa.",
            ),
            steps=(
                "Abra a ferramenta Comprimir PDF e selecione o documento.",
                "Escolha o nível leve, equilibrado ou forte conforme a finalidade do arquivo.",
                "Inicie o processamento e aguarde a conclusão.",
                "Baixe o novo PDF e compare seu tamanho com o original.",
                "Abra páginas com texto pequeno, imagens e gráficos para confirmar que continuam legíveis.",
            ),
        ),
        _section(
            "Como escolher o nível de compressão",
            (
                "O nível leve é um ponto de partida para arquivos que já têm boa otimização ou que precisam conservar detalhes visuais. O equilibrado busca um meio-termo prático para leitura em tela e compartilhamento. O forte pode ser útil quando o limite de tamanho é mais importante, mas merece uma inspeção cuidadosa porque elementos visuais podem apresentar maior perda.",
                "Textos gerados digitalmente tendem a permanecer nítidos, enquanto fotografias, assinaturas digitalizadas e letras que já fazem parte de uma imagem podem reagir de outro modo. Não escolha apenas pelo número de megabytes: a menor versão não é necessariamente a mais adequada ao uso. Para impressão, arquivo legal ou acessibilidade, mantenha também a versão de origem.",
            ),
            bullets=(
                "Leve: priorize quando detalhes finos precisam ser preservados.",
                "Equilibrado: experimente primeiro em documentos de uso cotidiano.",
                "Forte: use quando há uma restrição relevante de tamanho e faça uma revisão visual completa.",
            ),
        ),
        _section(
            "O que conferir depois da compactação",
            (
                "Navegue pelo PDF inteiro e amplie áreas críticas. Confira números em tabelas, legendas, códigos, carimbos, assinaturas, imagens médicas ou técnicas e qualquer texto incorporado em fotografias. Teste a pesquisa e a seleção de palavras se esses recursos já existiam no original, além de verificar links e marcadores que façam parte do fluxo de leitura.",
                "Também vale abrir o resultado no aplicativo ou dispositivo em que ele será usado. Um arquivo pode parecer adequado no computador, mas exigir outra escolha para impressão ou projeção. Compare a contagem de páginas e não apague a cópia original até ter certeza de que a nova versão cumpre sua finalidade.",
            ),
        ),
        _section(
            "O que fazer quando o PDF continua grande",
            (
                "Se outra compactação não trouxer ganho útil, procure a origem do volume. Um PDF com muitas páginas pode ser dividido em partes quando o destinatário aceita vários arquivos. Também é possível remover páginas desnecessárias no documento de origem, redimensionar fotografias antes de montar o PDF ou exportá-lo novamente com configurações adequadas ao uso em tela.",
                "Juntar e separar arquivos muda a organização, não garante redução. Converter páginas para imagem e remontar o documento pode eliminar recursos como texto pesquisável e acessibilidade, por isso não deve ser a primeira opção. A melhor estratégia é ajustar a fonte do problema e preservar uma versão integral quando o conteúdo ou a qualidade tiver valor documental.",
            ),
        ),
    ),
    "como-transformar-jpg-em-pdf": (
        _section(
            "Quando reunir uma imagem em PDF",
            (
                "O JPG é adequado para fotografias e é aceito por muitos aplicativos, mas o PDF é mais conveniente quando o conteúdo precisa se comportar como uma página. Ele pode facilitar a impressão, manter uma imagem dentro de um documento e evitar que o destinatário tenha de lidar com formatos separados em determinadas plataformas.",
                "Converter não melhora a resolução da foto nem recupera detalhes ausentes. O PDF passa a conter a imagem já existente, portanto uma fotografia desfocada, pequena ou excessivamente comprimida continuará com essas características. Se você pretende enviar um comprovante, exercício ou registro fotografado, prepare o JPG antes de criar o documento.",
            ),
        ),
        _section(
            "Como preparar o JPG antes da conversão",
            (
                "Abra a imagem e confira se ela está na orientação correta, com bordas úteis visíveis e texto legível. Faça cortes somente em uma cópia, principalmente quando o original pode ser necessário mais tarde. Evite aplicar filtros fortes em documentos: contraste excessivo pode apagar traços finos, assinaturas e números.",
                "Observe também a proporção da imagem. Uma foto muito horizontal colocada em uma página vertical pode gerar margens amplas ou ficar menor para caber. Se o objetivo for impressão, considere a orientação e o tamanho de papel desejados antes de converter. A ferramenta não deve ser tratada como um editor de conteúdo ou como garantia de conformidade documental.",
            ),
            bullets=(
                "Gire a imagem antes de enviar, se necessário.",
                "Confirme foco e legibilidade ampliando as áreas com texto.",
                "Use o arquivo com resolução suficiente para o destino, sem ampliar artificialmente uma foto pequena.",
                "Remova apenas bordas que não façam parte do conteúdo relevante.",
            ),
        ),
        _section(
            "Passo a passo para transformar JPG em PDF",
            (
                "A ferramenta JPG para PDF converte uma imagem JPG ou JPEG em um arquivo PDF. Para um conjunto de várias fotos, use a ferramenta Imagens para PDF quando quiser montar o documento em uma única operação; outra alternativa é converter os arquivos individualmente e, depois, usar Juntar PDF para combinar as páginas.",
            ),
            steps=(
                "Abra a ferramenta JPG para PDF e selecione a imagem preparada.",
                "Confirme que o arquivo enviado é o correto e inicie a conversão.",
                "Aguarde a criação do PDF sem fechar a página.",
                "Baixe o resultado e confira a página em um leitor de PDF.",
                "Se houver outros PDFs, organize-os com a ferramenta de junção somente após revisar cada parte.",
            ),
        ),
        _section(
            "Ordem, orientação e legibilidade em várias páginas",
            (
                "Ao criar um documento com várias imagens, defina a sequência antes do envio. Renomear os arquivos com números — 01, 02, 03 — ajuda a identificar a ordem, embora seja importante confirmar a disposição dentro da ferramenta escolhida. Verifique se todas as páginas seguem uma orientação coerente ou se as mudanças são intencionais.",
                "Depois de gerar o PDF, percorra o arquivo página por página. Confirme se nenhuma foto foi repetida, omitida ou inserida de cabeça para baixo. Amplie textos pequenos e observe se as bordas não esconderam informações. Para materiais que serão impressos, faça um teste em uma página quando escala, margens ou fidelidade de cor forem importantes.",
            ),
        ),
        _section(
            "Como compartilhar e arquivar o PDF criado",
            (
                "Dê ao arquivo um nome que explique o conteúdo sem expor dados pessoais desnecessários. Antes de enviar, confira o tamanho final e abra o documento fora do navegador usado na conversão. Se houver uma exigência de portal, escola ou empresa, verifique também o limite de tamanho, o número de páginas e as regras de formato daquele serviço.",
                "Guardar o JPG original é útil porque futuras edições e novos formatos podem partir da melhor fonte disponível. O PDF criado não substitui automaticamente o original e não adiciona assinatura digital, autenticação ou validade jurídica. Para conteúdo confidencial, compartilhe somente com destinatários autorizados e use o canal apropriado à sensibilidade do documento.",
            ),
        ),
    ),
    "jpg-vs-png-vs-webp": (
        _section(
            "As diferenças começam no tipo de compressão",
            (
                "JPG, PNG e WebP armazenam imagens de maneiras diferentes. O JPG usa compressão com perdas e costuma funcionar bem para fotografias, nas quais pequenas variações entre pixels são menos perceptíveis. A cada nova edição e salvamento com perdas, porém, podem surgir blocos, halos e perda de detalhe, principalmente perto de texto e linhas bem definidas.",
                "O PNG é conhecido pela compressão sem perdas: ao salvar, os valores visuais podem ser preservados sem os artefatos típicos do JPG. Isso costuma favorecer capturas de tela, diagramas e interfaces, embora fotografias em PNG possam ocupar bastante espaço. O WebP aceita modos com e sem perdas, e o resultado depende das configurações usadas pelo conversor ou editor.",
            ),
        ),
        _section(
            "Transparência, texto e cores",
            (
                "PNG e WebP podem representar transparência, inclusive áreas parcialmente transparentes. O JPG não tem canal alfa; ao converter uma imagem transparente para JPG, um fundo precisa substituir essas áreas. A cor desse fundo depende do fluxo de conversão, por isso o resultado deve ser conferido antes de publicar um logotipo ou elemento de interface.",
                "Para capturas de tela com letras pequenas, ícones e regiões de cor uniforme, PNG tende a evitar as bordas borradas que podem aparecer no JPG. Para fotos, JPG ou WebP com perdas frequentemente produzem arquivos mais adequados à web. Nenhum formato garante cores idênticas em todos os dispositivos: perfis de cor, navegador, tela e aplicativo também influenciam a exibição.",
            ),
            bullets=(
                "JPG: fotografias e ampla compatibilidade, sem transparência.",
                "PNG: gráficos, capturas de tela e transparência, com possível aumento de tamanho em fotos.",
                "WebP: imagens para web com opções de compressão e transparência, dependendo do arquivo gerado.",
            ),
        ),
        _section(
            "Compatibilidade e contexto de uso",
            (
                "JPG e PNG são reconhecidos por uma grande variedade de editores, sistemas e serviços. WebP tem suporte amplo em navegadores atuais, mas fluxos antigos, equipamentos específicos e alguns programas podem exigir JPG ou PNG. A decisão deve considerar onde a imagem será aberta, editada, enviada e arquivada — não apenas o menor tamanho obtido.",
                "Para um site, confirme os formatos aceitos pelo gerenciador de conteúdo e mantenha largura e altura adequadas à área de exibição. Para impressão ou entrega a terceiros, siga a especificação recebida. Se você precisa continuar editando camadas, texto ou vetores, preserve também o arquivo de origem do programa; JPG, PNG e WebP normalmente representam a imagem já renderizada.",
            ),
        ),
        _section(
            "Como escolher o formato na prática",
            (
                "Comece pelo conteúdo. Uma fotografia sem transparência é uma candidata natural a JPG ou WebP. Um logotipo com fundo transparente, uma captura de interface ou um gráfico com linhas nítidas costuma se beneficiar de PNG ou WebP. Depois, compare compatibilidade e tamanho usando a mesma dimensão em pixels, pois reduzir largura e altura também altera muito o peso.",
                "O BoostConvert oferece ferramentas como JPG para WebP, JPG para PNG, PNG para JPG e WebP para JPG. Na conversão JPG para WebP, a saída parte de uma fonte que já pode ter perdas; mudar o formato não recupera detalhes descartados anteriormente. Guarde o original e avalie visualmente o arquivo produzido no tamanho em que ele será usado.",
            ),
            steps=(
                "Identifique se a imagem é foto, gráfico, captura de tela ou elemento com transparência.",
                "Confirme quais formatos o destino aceita.",
                "Converta uma cópia e compare tamanho, nitidez e fundo transparente.",
                "Teste a imagem no site, aplicativo ou dispositivo de destino antes de substituir o original.",
            ),
        ),
        _section(
            "Por que converter nem sempre deixa o arquivo menor",
            (
                "A extensão, sozinha, não determina o tamanho. Dimensões em pixels, quantidade de detalhes, ruído, transparência e nível de compressão têm grande influência. Uma foto convertida de JPG já compacto para PNG pode crescer bastante; um gráfico simples convertido para WebP pode ou não reduzir, conforme o modo e a configuração de saída.",
                "Evite ciclos repetidos entre formatos com perdas, porque cada recodificação pode introduzir novas alterações sem benefício proporcional. Compare arquivos equivalentes e use uma inspeção visual, não apenas o peso. Quando a imagem continua grande, redimensionar para as dimensões realmente necessárias pode ser mais efetivo do que trocar apenas a extensão, desde que você preserve uma cópia em resolução original.",
            ),
        ),
    ),
    "como-converter-mp4-para-mp3": (
        _section(
            "O que acontece ao transformar vídeo em áudio",
            (
                "MP4 é um contêiner que pode reunir vídeo, áudio, legendas e outros dados. Ao converter para MP3, a ferramenta seleciona uma faixa de áudio compatível e gera um arquivo somente de som; as imagens do vídeo não fazem parte da saída. Esse processo é útil para materiais próprios, gravações autorizadas e conteúdos cujo uso permita a extração.",
                "O MP3 usa compressão com perdas. A conversão não melhora uma gravação ruidosa nem cria frequências que não existem na fonte. Se o áudio do MP4 já estiver comprimido, ele será decodificado e codificado novamente, portanto escolher um bitrate alto pode evitar uma limitação adicional mais agressiva, mas não restaura a qualidade original.",
            ),
        ),
        _section(
            "Passo a passo no BoostConvert",
            (
                "A ferramenta MP4 para MP3 aceita um vídeo MP4 e permite escolher 128, 192, 256 ou 320 kbps para a saída. Arquivos longos ou grandes podem exigir mais tempo de envio e processamento. Mantenha a página aberta até que o resultado esteja disponível e confira se o vídeo selecionado contém a faixa que você deseja extrair.",
            ),
            steps=(
                "Abra a ferramenta MP4 para MP3 e selecione seu arquivo MP4.",
                "Escolha a qualidade de saída entre as opções de bitrate disponíveis.",
                "Inicie a conversão e aguarde a conclusão do processamento.",
                "Baixe o MP3 e escute o começo, o meio e o fim da gravação.",
                "Confirme duração, volume, sincronismo do conteúdo falado e ausência de cortes inesperados.",
            ),
        ),
        _section(
            "Como escolher o bitrate do MP3",
            (
                "Bitrate é a quantidade aproximada de dados usada por segundo de áudio. Em geral, valores maiores geram arquivos maiores e dão ao codificador mais espaço para representar o sinal. Isso não significa que 320 kbps sempre produzirá uma diferença audível, nem que seja a melhor escolha para todos os usos.",
                "Para fala, aulas e entrevistas, 128 ou 192 kbps podem atender muitos cenários, desde que o resultado seja escutado. Para música ou material com mais detalhes, 256 ou 320 kbps podem ser preferíveis quando o tamanho não é a principal restrição. Considere também o limite da plataforma de destino e compare uma amostra em fones ou caixas semelhantes às que serão usadas.",
            ),
            bullets=(
                "128 kbps: arquivo menor; avalie com atenção música e sons complexos.",
                "192 kbps: opção intermediária para muitos conteúdos falados e usos cotidianos.",
                "256 kbps: mais dados por segundo, com aumento do tamanho final.",
                "320 kbps: maior bitrate oferecido pela ferramenta, sem recuperar detalhes ausentes na fonte.",
            ),
        ),
        _section(
            "Limites da fonte e revisão do resultado",
            (
                "O MP4 pode ter mais de uma faixa de áudio, silêncio no início, volume baixo ou som em um formato pouco comum. O comportamento depende do que realmente está armazenado no arquivo. Depois da conversão, verifique se a faixa esperada foi usada e se a duração corresponde ao conteúdo necessário.",
                "Escute passagens com fala, música intensa e transições. Ruídos, distorção ou clipping presentes no vídeo não desaparecem ao gerar MP3. Se a prioridade for edição posterior, uma conversão para WAV pode ser mais apropriada em alguns fluxos, embora produza um arquivo maior; ainda assim, ela também não melhora a fonte. Preserve o MP4 enquanto o trabalho não estiver concluído.",
            ),
        ),
        _section(
            "Direitos autorais e uso responsável",
            (
                "Ter acesso a um vídeo não significa automaticamente ter permissão para copiar, extrair ou redistribuir seu áudio. Use a ferramenta em gravações próprias, materiais licenciados para essa finalidade, obras em domínio público ou situações autorizadas pelo titular. Regras de plataformas e contratos também podem estabelecer restrições adicionais.",
                "Ao compartilhar o MP3, considere direitos de autores, intérpretes e demais envolvidos, além de privacidade e dados pessoais que possam estar na gravação. O conversor apenas altera o formato técnico; ele não concede licença, remove obrigações de atribuição nem valida a legalidade do uso pretendido.",
            ),
        ),
    ),
    "como-abrir-heic": (
        _section(
            "O que é um arquivo HEIC",
            (
                "HEIC é uma extensão associada a imagens armazenadas no formato HEIF, usado por aparelhos e aplicativos para representar fotos com compressão eficiente e recursos adicionais. Ele ficou conhecido por ser adotado em dispositivos Apple, mas um arquivo HEIC não é exclusivo de um único modelo de celular.",
                "A dificuldade para abrir costuma ser uma questão de compatibilidade, não um sinal de que a foto esteja danificada. Sistemas, navegadores, editores e serviços mais antigos podem não ter o decodificador necessário. Atualizar o aplicativo ou usar um visualizador compatível pode resolver o problema sem trocar o formato.",
            ),
        ),
        _section(
            "Como tentar abrir HEIC no celular ou computador",
            (
                "Primeiro, teste a foto no aplicativo padrão de imagens e verifique se o sistema está atualizado. Em um dispositivo que criou ou recebeu o arquivo, o suporte pode já estar disponível. No computador, a compatibilidade varia conforme a versão do sistema e os componentes instalados; aplicativos confiáveis do próprio sistema ou de um fornecedor conhecido podem acrescentar suporte.",
                "Se o objetivo for apenas enviar a imagem a um site ou pessoa que não aceita HEIC, converter uma cópia para JPG costuma ser o caminho mais simples. Não renomeie apenas a extensão de .heic para .jpg: isso não altera os dados internos e pode fazer com que o aplicativo continue rejeitando o arquivo.",
            ),
            bullets=(
                "Confirme que o arquivo terminou de ser transferido antes de tentar abri-lo.",
                "Atualize o visualizador ou o sistema quando houver uma versão compatível disponível.",
                "Evite instalar pacotes de origem desconhecida apenas para abrir uma foto.",
                "Converta uma cópia quando o destino exigir JPG ou PNG.",
            ),
        ),
        _section(
            "Como converter HEIC para JPG no BoostConvert",
            (
                "A ferramenta HEIC para JPG gera uma imagem JPG, formato amplamente aceito por navegadores, redes, editores e serviços de envio. Ela oferece opções de qualidade 70, 85 e 95, apresentadas como menor arquivo, equilibrada e alta qualidade. A escolha afeta o compromisso entre tamanho e fidelidade visual, sem garantir um peso específico.",
            ),
            steps=(
                "Abra a ferramenta HEIC para JPG e selecione a foto HEIC.",
                "Escolha a qualidade JPEG de acordo com o destino da imagem.",
                "Inicie a conversão e aguarde o processamento.",
                "Baixe o JPG e abra-o no aplicativo em que pretende usá-lo.",
                "Compare enquadramento, orientação, cores e detalhes com o HEIC original.",
            ),
        ),
        _section(
            "Qualidade, transparência e metadados",
            (
                "JPG utiliza compressão com perdas. Uma configuração mais alta costuma preservar melhor os detalhes visuais, mas também tende a produzir um arquivo maior. Mesmo assim, a conversão não aumenta a resolução real nem recupera informações que não estejam disponíveis no HEIC. Amplie rostos, textos e áreas com linhas finas ao revisar.",
                "HEIC pode armazenar recursos que não têm equivalente direto em um JPG simples, como transparência, múltiplas imagens, profundidade ou informações auxiliares. Metadados de câmera, localização, data e orientação também podem não ser transferidos integralmente. Se esses dados forem importantes para seu arquivo, mantenha o original e confirme as propriedades do JPG gerado antes de organizar ou publicar a foto.",
            ),
        ),
        _section(
            "JPG ou PNG: qual saída usar",
            (
                "JPG é uma escolha prática para fotografias, compartilhamento e serviços que priorizam compatibilidade. PNG pode ser útil quando a imagem precisa de transparência ou quando o conteúdo tem texto e bordas definidas, mas fotografias em PNG podem ocupar mais espaço. O melhor formato depende das exigências do destino e dos recursos presentes no original.",
                "Se o arquivo será apenas visualizado, tente primeiro um aplicativo compatível com HEIC para evitar uma conversão desnecessária. Se precisar de uma versão universal, gere uma cópia em JPG ou PNG e teste-a onde será usada. Preserve o HEIC como fonte, porque conversões futuras devem partir do arquivo com mais informações disponível, e não de uma cópia já recomprimida.",
            ),
        ),
    ),
}


GUIDE_CONTENT: Mapping[str, tuple[GuideSection, ...]] = MappingProxyType(
    _GUIDE_CONTENT
)


__all__ = ["GUIDE_CONTENT"]
