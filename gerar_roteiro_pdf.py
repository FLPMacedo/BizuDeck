"""
Gera o PDF "Roteiro de Vídeo — BizuDeck" do canal @UaiScript.

Saída: Roteiro_Video.pdf
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# =========================
# IDENTIDADE
# =========================
CANAL = "@UaiScript"
CANAL_URL = "https://www.youtube.com/@UaiScript"
TITULO = "Roteiro de Vídeo"
SUBTITULO = "BizuDeck — Quiz interativo grátis para Provas & Concursos"
ARQUIVO_SAIDA = "Roteiro_Video.pdf"
LOGO_PATH = "assets/uaiscript.png"

# Paleta (mesma do app — laranja-âmbar)
COR_PRIMARIA = colors.HexColor("#f59e0b")
COR_PRIMARIA_ESCURA = colors.HexColor("#b8741b")
COR_TEXTO = colors.HexColor("#1c2128")
COR_TEXTO_DIM = colors.HexColor("#566573")
COR_FUNDO_CAIXA = colors.HexColor("#fdf4e0")
COR_BORDA = colors.HexColor("#c8d0d8")
COR_TEMPO = colors.HexColor("#b8741b")
COR_CODE_BG = colors.HexColor("#14110d")
COR_CODE_FG = colors.HexColor("#f5f1ea")

# =========================
# ESTILOS
# =========================
styles = getSampleStyleSheet()
s_titulo_capa = ParagraphStyle(
    "TC", parent=styles["Title"], fontSize=34, leading=40,
    alignment=TA_CENTER, textColor=COR_PRIMARIA, spaceAfter=10,
)
s_subtitulo_capa = ParagraphStyle(
    "SC", parent=styles["Title"], fontSize=16, leading=22,
    alignment=TA_CENTER, textColor=COR_TEXTO_DIM, spaceAfter=20,
)
s_h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontSize=22, leading=26,
    textColor=COR_PRIMARIA, spaceBefore=8, spaceAfter=10,
)
s_h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontSize=15, leading=20,
    textColor=COR_PRIMARIA_ESCURA, spaceBefore=12, spaceAfter=6,
)
s_h3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontSize=12, leading=16,
    textColor=COR_TEXTO, spaceBefore=8, spaceAfter=4,
    fontName="Helvetica-Bold",
)
s_body = ParagraphStyle(
    "B", parent=styles["BodyText"], fontSize=11, leading=16,
    alignment=TA_JUSTIFY, textColor=COR_TEXTO, spaceAfter=6,
)
s_body_left = ParagraphStyle("BL", parent=s_body, alignment=TA_LEFT)
s_fala = ParagraphStyle(
    "F", parent=s_body_left, fontSize=11.5, leading=17,
    leftIndent=14, rightIndent=4,
)
s_broll = ParagraphStyle(
    "BR", parent=s_body_left, fontSize=10, leading=14,
    leftIndent=14, textColor=COR_TEXTO_DIM,
    fontName="Helvetica-Oblique",
)
s_tempo = ParagraphStyle(
    "T", parent=styles["Heading2"], fontSize=13, leading=16,
    textColor=COR_TEMPO, spaceBefore=10, spaceAfter=4,
    fontName="Helvetica-Bold",
)
s_lista = ParagraphStyle(
    "L", parent=s_body, leftIndent=14, bulletIndent=2, spaceAfter=4,
)
s_code = ParagraphStyle(
    "C", parent=styles["BodyText"], fontSize=9.5, leading=13,
    fontName="Courier", textColor=COR_CODE_FG,
    backColor=COR_CODE_BG, borderColor=COR_CODE_BG,
    borderPadding=10, leftIndent=8, rightIndent=8,
    spaceBefore=4, spaceAfter=10,
)
s_small = ParagraphStyle(
    "S", parent=styles["BodyText"], fontSize=9, leading=12,
    textColor=COR_TEXTO_DIM, alignment=TA_CENTER,
)


def p(texto, estilo=s_body):
    return Paragraph(texto, estilo)


def lista_marcador(itens, estilo=s_lista):
    return [Paragraph(f"• {it}", estilo) for it in itens]


def lista_numerada(itens, estilo=s_lista):
    return [
        Paragraph(f"<b>{i}.</b> {it}", estilo)
        for i, it in enumerate(itens, start=1)
    ]


def code(linhas):
    if isinstance(linhas, list):
        linhas = "\n".join(linhas)
    return Preformatted(linhas, s_code)


def caixa(titulo, conteudo):
    inner = [
        Paragraph(f"<b>{titulo}</b>",
                  ParagraphStyle("CT", parent=s_h3,
                                 textColor=COR_PRIMARIA_ESCURA)),
    ]
    if isinstance(conteudo, list):
        inner += conteudo
    else:
        inner.append(Paragraph(conteudo, s_body_left))
    t = Table([[inner]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COR_FUNDO_CAIXA),
        ("BOX", (0, 0), (-1, -1), 1, COR_PRIMARIA),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return KeepTogether([t, Spacer(1, 0.3 * cm)])


def divisor():
    return HRFlowable(width="100%", thickness=0.5, color=COR_BORDA,
                      spaceBefore=6, spaceAfter=10)


def _rodape(canv, doc):
    canv.saveState()
    canv.setStrokeColor(COR_BORDA)
    canv.setLineWidth(0.3)
    canv.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canv.setFont("Helvetica", 8)
    canv.setFillColor(COR_TEXTO_DIM)
    canv.drawString(2 * cm, 1.1 * cm, f"Roteiro BizuDeck — {CANAL}")
    canv.drawRightString(
        A4[0] - 2 * cm, 1.1 * cm, f"Página {canv.getPageNumber()}"
    )
    canv.restoreState()


def _capa(canv, doc):
    pass


# =========================
# DADOS
# =========================
BLOCOS = [
    {
        "num": 1, "tempo": "0:00 – 0:15", "titulo": "HOOK",
        "subtitulo": "Quem nunca cansou de só ler resumo",
        "fala": [
            "Você lê o resumo, acha que sabe, na hora da prova trava. "
            "Estudar passivo não funciona. Eu fiz um app gratuito que te "
            "coloca pra <b>responder em vez de só ler</b> — pergunta com "
            "áudio, feedback na hora, e ainda exporta pro Anki.",
        ],
        "broll": [
            "Pessoa lendo resumo, cara cansada",
            "Tela do app com pergunta tocando",
            "Pop-up: \"BIZUDECK — quiz interativo grátis\"",
        ],
    },
    {
        "num": 2, "tempo": "0:15 – 0:45", "titulo": "APRESENTAÇÃO",
        "subtitulo": "Quem é + o que o app entrega em 1 frase",
        "fala": [
            "Eu sou do canal <b>UaiScript</b>, e aqui a gente automatiza "
            "estudo, trabalho e produtividade. Hoje eu te entrego o "
            "<b>BizuDeck</b> — software gratuito pra estudar Escola, "
            "Faculdade e Concurso no modo ativo. Você vai sair com:",
            "<b>1.</b> O .exe pra baixar e usar agora",
            "<b>2.</b> Um manual em PDF dentro do app",
            "<b>3.</b> 4 exemplos prontos pra testar antes de gerar o seu",
            "Tudo nos links da descrição.",
        ],
        "broll": [
            "Texto na tela: 🎁 BizuDeck — software grátis",
            "Texto na tela: 📖 Manual em PDF dentro do app",
            "Texto na tela: 📁 4 exemplos prontos",
        ],
    },
    {
        "num": 3, "tempo": "0:45 – 2:00",
        "titulo": "POR QUE ESTUDAR LENDO NÃO FUNCIONA",
        "subtitulo": "Diagnóstico em três armadilhas",
        "fala": [
            "Antes do app, o <b>diagnóstico</b>. Quem estuda lendo resumo "
            "cai em três armadilhas:",
            "<b>Uma</b> — você confunde <b>reconhecer</b> com "
            "<b>lembrar</b>. Bate o olho no texto, parece familiar, seu "
            "cérebro fala 'sei isso'. Na prova, sem o texto na frente, "
            "você trava. É a <b>falsa sensação de domínio</b>.",
            "<b>Duas</b> — você não tem <b>feedback</b>. Lê, fecha o "
            "livro, e não sabe se entendeu. Descobre só no dia da prova.",
            "<b>Três</b> — você não tem <b>repetição inteligente</b>. "
            "Gasta o mesmo tempo no que sabe e no que ainda não fixou.",
            "O BizuDeck resolve os três: você responde, recebe feedback "
            "na hora, e exporta pro Anki pra repetição espaçada.",
        ],
        "broll": [
            "Livro fechado com cara de dúvida",
            "Tela do app com ✓/✗ piscando",
            "Logo do Anki",
        ],
    },
    {
        "num": 4, "tempo": "2:00 – 4:00", "titulo": "O MÉTODO",
        "subtitulo": "IA externa + áudio PT-BR + quiz/Anki/PDF",
        "fala": [
            "<b>Pilar 1 — Conteúdo gerado por IA externa.</b> Você cola "
            "seu material (capítulo, resumo, edital) num prompt pronto. "
            "Cola no ChatGPT, Gemini ou Claude — <b>de graça</b>. "
            "A IA devolve um .txt com perguntas no formato do app. "
            "<b>Sem chave de API.</b>",
            "<b>Pilar 2 — Áudio em português.</b> O app gera o áudio de "
            "cada pergunta com a <b>Francisca</b> e da resposta com o "
            "<b>Antonio</b> — vozes nativas grátis da Microsoft Edge. "
            "Você estuda olhando ou só ouvindo.",
            "<b>Pilar 3 — Múltiplos caminhos.</b> O conteúdo vira "
            "três coisas ao mesmo tempo: quiz interativo no app, "
            "baralho .apkg pro Anki, e PDF de estudo. Você escolhe.",
        ],
        "broll": [
            "Pilar 1: IA EXTERNA GERA O CONTEÚDO",
            "Pilar 2: ÁUDIO EM PORTUGUÊS",
            "Pilar 3: QUIZ + ANKI + PDF",
        ],
    },
    {
        "num": 5, "tempo": "4:00 – 7:30", "titulo": "DEMONSTRAÇÃO",
        "subtitulo": "Tela compartilhada — abrir BizuDeck.exe",
        "fala": [
            "Sidebar com <b>Criar Quiz</b>, <b>Estudar</b>, "
            "<b>Configurações</b> e <b>Sobre</b>.",
            "Clico em <b>📁 Abrir exemplos</b> — 4 quizzes prontos: "
            "Direito Constitucional, História, Matemática, Português. "
            "Vou importar o de Direito: <b>10 questões</b>, 5 abertas e "
            "5 múltipla escolha.",
            "O conteúdo aparece num <b>editor</b> — posso trocar "
            "pergunta, gabarito, adicionar ou remover questão. Mudo o "
            "nome do baralho aqui em cima.",
            "Clico em <b>🎧 Gerar áudios</b>. Gera dois áudios por "
            "questão: pergunta na Francisca, resposta no Antonio.",
            "<b>▶ Iniciar Estudo</b>: placar ao vivo no topo, pergunta "
            "no card, botão Ouvir. Aberta: digito e o app compara por "
            "similaridade (✓ correto / ◐ parcial / ✗ distante) e mostra "
            "o gabarito. Múltipla: clico em A B C D, app destaca a "
            "correta em verde.",
            "Mas o melhor é exportar: <b>📦 Exportar para Anki</b> gera "
            "um .apkg com áudio em frente E verso. E <b>📄 Gerar PDF "
            "de estudo</b> abre automaticamente um documento com todas "
            "as questões, gabarito em laranja e linhas em branco pra "
            "anotação.",
            "Em <b>Sobre</b>, o manual completo do app — 11 capítulos "
            "explicando tudo.",
        ],
        "broll": [
            "Zoom nos botões",
            "Acelerar 1.5x as esperas",
            "Mostrar .apkg abrindo no Anki Desktop",
            "Mostrar PDF de estudo aberto",
        ],
    },
    {
        "num": 6, "tempo": "7:30 – 9:00", "titulo": "ONDE ENCAIXA",
        "subtitulo": "Escola, Faculdade, Concurso",
        "fala": [
            "<b>Estudante de ensino médio</b> — cola o resumo de Biologia, "
            "gera as perguntas, treina no fim de semana.",
            "<b>Universitário</b> — pega o slide do professor, transforma "
            "em quiz na noite anterior à prova. Em uma hora você "
            "responde 30 questões com feedback.",
            "<b>Concurseiro</b> — abre o edital, cola um trecho da lei, "
            "gera 20 questões. Roda no Anki 20 minutos por dia. "
            "Repetição espaçada na fórmula que funciona pra concurso.",
            "A diferença: aqui você gera o conteúdo da matéria que "
            "<b>VOCÊ</b> precisa. Não tem 'lição 1 da apostila X'. "
            "Custa zero.",
        ],
        "broll": [
            "3 personagens diferentes usando o app",
            "Edital, slide e livro passando",
        ],
    },
    {
        "num": 7, "tempo": "9:00 – 10:00", "titulo": "DOWNLOAD E MANUAL",
        "subtitulo": "Link da Release + manual embarcado",
        "fala": [
            "Link na descrição. Vai pro GitHub do BizuDeck, aba "
            "<b>Releases</b>. Baixa o .exe, dois cliques, abre. "
            "Não precisa instalar nada.",
            "Se o Windows reclamar: <b>Mais informações → Executar assim "
            "mesmo</b>. Código aberto no repositório.",
            "Manual: aba <b>Sobre</b> → <b>📖 Abrir Manual</b> → PDF de "
            "11 capítulos. Era pra ser produto pago. Tá embarcado de "
            "graça.",
        ],
        "broll": [
            "Mostrar página de Releases do GitHub",
            "Pop-up: 📥 BizuDeck.exe",
            "Manual aberto",
        ],
    },
    {
        "num": 8, "tempo": "10:00 – 11:00", "titulo": "CTA + ENCERRAMENTO",
        "subtitulo": "Curtida, inscrição, compartilhamento",
        "fala": [
            "Se esse vídeo te ajudou, faz três coisas:",
            "<b>1.</b> <b>Curte</b> o vídeo",
            "<b>2.</b> <b>Se inscreve no canal</b> — ferramenta nova "
            "toda semana, várias delas voltadas pra automatizar estudo",
            "<b>3.</b> <b>Manda o vídeo</b> pra quem tá estudando agora "
            "pra uma prova",
            "E se você usar e funcionar, <b>volta aqui</b> e me conta "
            "nos comentários qual matéria você estudou. Eu leio tudo.",
            "Valeu, e até a próxima.",
        ],
        "broll": [
            "Card final + inscrever-se piscando",
            "Logo do canal",
        ],
    },
]

DESCRICAO_YT = """\
Software gratuito pra transformar qualquer matéria em quiz com áudio
e exportar pro Anki. Funciona pra Escola, Faculdade e Concurso Público.

Mostro nesse vídeo o BizuDeck, um app que eu criei: você cola conteúdo
no ChatGPT (ou Gemini/Claude), gera um arquivo de quiz, importa no
app, e ele faz o resto — gera os áudios, roda o quiz com feedback
imediato, exporta baralho .apkg pro Anki e um PDF de estudo.

→ Baixar BizuDeck.exe: https://github.com/FLPMacedo/BizuDeck/releases
→ Código-fonte:        https://github.com/FLPMacedo/BizuDeck
→ Anki (oficial):      https://apps.ankiweb.net/

Capítulos
00:00 Por que estudar lendo não funciona
00:45 O que você vai receber
02:00 Como o método funciona
04:00 Demonstração do app
07:30 Onde encaixa (Escola, Faculdade, Concurso)
09:00 Como baixar
10:00 Encerramento

Canal: youtube.com/@UaiScript\
"""

TITULOS = [
    "Criei um app pra estudar prova respondendo (não lendo)",
    "Estudei concurso com esse app que eu criei — agora é grátis",
    "App grátis pra transformar qualquer matéria em quiz com áudio",
]

CHECKLIST = [
    "Reler o roteiro 1x em voz alta",
    "BizuDeck.exe rodando em pasta limpa, com exemplos/ ao lado",
    "Anki Desktop aberto pra mostrar a importação",
    "Leitor de PDF default funcionando (pra demo do PDF abre)",
    "Microfone testado",
    "Iluminação ok",
    "Câmera enquadrada",
    "Telefone no silencioso",
    "Aba de browser fechada (nada vaze no compartilhamento)",
]


# =========================
# SEÇÕES
# =========================
def sec_capa(story):
    story.append(Spacer(1, 3 * cm))
    if os.path.exists(LOGO_PATH):
        try:
            img = Image(LOGO_PATH, width=3.5 * cm, height=3.5 * cm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.6 * cm))
        except Exception:
            pass
    story.append(p(TITULO, s_titulo_capa))
    story.append(p(SUBTITULO, s_subtitulo_capa))
    story.append(Spacer(1, 1.5 * cm))
    story.append(p(
        f"Documento de gravação — Canal <b>{CANAL}</b>",
        ParagraphStyle("CapaT", parent=s_body, alignment=TA_CENTER,
                       fontSize=12),
    ))
    story.append(p(
        CANAL_URL,
        ParagraphStyle("CapaUrl", parent=s_body, alignment=TA_CENTER,
                       fontSize=11, textColor=COR_PRIMARIA),
    ))
    story.append(Spacer(1, 4 * cm))
    story.append(p(
        f"Edição {datetime.now().strftime('%B/%Y').capitalize()}  "
        f"•  Duração-alvo: 10–12 min  •  Formato: câmera + tela",
        s_small,
    ))
    story.append(PageBreak())


def sec_visao_geral(story):
    story.append(p("Visão geral do vídeo", s_h1))
    story.append(divisor())
    story.append(p(
        "Vídeo em <b>8 blocos cronometrados</b>, duração-alvo entre 10 e "
        "12 minutos. Estrutura: hook → diagnóstico → método → produto → "
        "casos de uso → download → CTA."
    ))
    story.append(Spacer(1, 0.4 * cm))

    dados = [["Bloco", "Tempo", "Título", "Função"]]
    for b in BLOCOS:
        dados.append([
            f"#{b['num']}", b["tempo"], b["titulo"], b["subtitulo"],
        ])
    t = Table(dados, colWidths=[1.2 * cm, 2.6 * cm, 4.8 * cm, 8.2 * cm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, COR_BORDA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 1), (1, -1), COR_TEMPO),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())


def sec_blocos(story):
    story.append(p("Roteiro bloco a bloco", s_h1))
    story.append(divisor())
    for b in BLOCOS:
        story.append(p(f"⏱ {b['tempo']}", s_tempo))
        story.append(p(f"Bloco {b['num']} — {b['titulo']}", s_h1))
        story.append(p(f"<i>{b['subtitulo']}</i>", s_body_left))
        story.append(Spacer(1, 0.2 * cm))

        story.append(p("Fala", s_h3))
        for linha in b["fala"]:
            story.append(p(linha, s_fala))
        story.append(Spacer(1, 0.2 * cm))

        story.append(p("B-roll / Visual", s_h3))
        for it in b["broll"]:
            story.append(p(f"• {it}", s_broll))
        story.append(Spacer(1, 0.5 * cm))
        story.append(divisor())


def sec_demo(story):
    story.append(PageBreak())
    story.append(p("Texto de demonstração (Bloco 5)", s_h1))
    story.append(divisor())
    story.append(p(
        "Use <b>exemplos/exemplo_misto.txt</b> — já vem embarcado no "
        ".exe. <b>10 questões</b> de Direito Constitucional, mistura de "
        "abertas e múltipla escolha. Gera áudios em 1–2 minutos."
    ))
    story.append(p(
        "<b>Nome do baralho sugerido pra digitar na hora:</b> "
        "<font color='#f59e0b'>Constitucional_Lição_01</font>",
        s_body_left,
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(caixa(
        "Cuidado nos cortes",
        "A geração de áudio leva alguns segundos por questão. Use cortes "
        "em <b>jump cuts</b> ou acelere 1.5x para não ficar lento. "
        "Mostre só o início e o fim da barra de progresso.",
    ))


def sec_descricao(story):
    story.append(PageBreak())
    story.append(p("Descrição do vídeo (YouTube)", s_h1))
    story.append(divisor())
    story.append(p(
        "Cole exatamente esse bloco na descrição do vídeo. Sem hashtags, "
        "sem call-to-action agressivo, sem links de venda."
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(code(DESCRICAO_YT))


def sec_titulos(story):
    story.append(PageBreak())
    story.append(p("Sugestões de título", s_h1))
    story.append(divisor())
    story.append(p(
        "Teste 2 títulos em paralelo (recurso de A/B do YouTube) ou "
        "escolha 1 e meça por 48h antes de trocar. Os 3 abaixo "
        "seguem a mesma linha — sem clickbait."
    ))
    for it in lista_numerada(TITULOS, ParagraphStyle(
        "TIT", parent=s_body, fontSize=13, leading=20, leftIndent=14,
        spaceAfter=8,
    )):
        story.append(it)

    story.append(Spacer(1, 0.5 * cm))
    story.append(p("Recomendação", s_h2))
    story.append(p(
        "<b>Título #1</b> é o mais direto e desperta curiosidade pelo "
        "contraste 'respondendo, não lendo'. Bom hook pra thumbnail."
    ))

    story.append(p("Tags", s_h2))
    story.append(p(
        "bizudeck, concurso, estudo ativo, anki, quiz, edge tts, "
        "automação estudo, uaiscript, faculdade, escola"
    ))


def sec_thumbnail(story):
    story.append(PageBreak())
    story.append(p("Thumbnail", s_h1))
    story.append(divisor())
    story.append(p("Elementos", s_h2))
    for it in lista_marcador([
        "Texto curto: <b>BIZUS PRA PROVA</b> (4 palavras no máximo)",
        "Print do app aparecendo (tema escuro + laranja-âmbar)",
        "Sua foto opcional, centrada e neutra",
        "Fundo escuro com acento laranja (identidade do app)",
        "Sem setinhas vermelhas, sem cara de espanto, sem all-caps",
    ]):
        story.append(it)
    story.append(p("About do repositório", s_h2))
    story.append(p(
        "No GitHub do BizuDeck, canto direito → ⚙ Settings do About:"
    ))
    for it in lista_marcador([
        "<b>Description</b>: Quiz interativo com áudio para Escola, "
        "Faculdade e Concurso. Importa .txt, gera baralho Anki + PDF "
        "de estudo. Grátis.",
        "<b>Website</b>: https://www.youtube.com/@UaiScript",
        "<b>Topics</b>: python, anki, tts, edge-tts, quiz, "
        "concurso-publico, estudo-ativo, flashcards, customtkinter",
    ]):
        story.append(it)


def sec_checklist(story):
    story.append(PageBreak())
    story.append(p("Checklist antes de gravar", s_h1))
    story.append(divisor())
    story.append(p(
        "Marque cada item à mão antes de ligar a câmera. "
        "Produção limpa = vídeo melhor."
    ))
    story.append(Spacer(1, 0.4 * cm))
    dados = [["☐", "Item"]]
    for it in CHECKLIST:
        dados.append(["☐", it])
    t = Table(dados, colWidths=[1.2 * cm, 15.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (0, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, COR_BORDA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 1.2 * cm))
    story.append(p(
        f"— {CANAL} · {CANAL_URL}",
        ParagraphStyle("Sig", parent=s_small, alignment=TA_CENTER),
    ))


# =========================
# MAIN
# =========================
def build():
    doc = SimpleDocTemplate(
        ARQUIVO_SAIDA, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.2 * cm,
        title=f"{TITULO} — {SUBTITULO}", author=CANAL,
        subject="Roteiro de produção do vídeo do BizuDeck",
    )
    story = []
    sec_capa(story)
    sec_visao_geral(story)
    sec_blocos(story)
    sec_demo(story)
    sec_descricao(story)
    sec_titulos(story)
    sec_thumbnail(story)
    sec_checklist(story)
    doc.build(story, onFirstPage=_capa, onLaterPages=_rodape)
    print(f"PDF gerado: {os.path.abspath(ARQUIVO_SAIDA)}")


if __name__ == "__main__":
    build()
