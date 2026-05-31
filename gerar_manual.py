"""
Gera o Manual_BizuDeck.pdf — guia de uso do app.

Saída: assets/manual/Manual_BizuDeck.pdf
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
APP_NOME = "BizuDeck"
TAGLINE = "Bizus que você memoriza"
CANAL = "@UaiScript"
CANAL_URL = "https://www.youtube.com/@UaiScript"
ARQUIVO_SAIDA = os.path.join("assets", "manual", "Manual_BizuDeck.pdf")
LOGO_PATH = "assets/uaiscript.png"

# Paleta (mesma do app — laranja-âmbar)
COR_PRIMARIA = colors.HexColor("#f59e0b")
COR_PRIMARIA_ESCURA = colors.HexColor("#b8741b")
COR_TEXTO = colors.HexColor("#1c2128")
COR_TEXTO_DIM = colors.HexColor("#566573")
COR_FUNDO_CAIXA = colors.HexColor("#fdf4e0")
COR_BORDA = colors.HexColor("#c8d0d8")
COR_CODE_BG = colors.HexColor("#14110d")
COR_CODE_FG = colors.HexColor("#f5f1ea")

# =========================
# ESTILOS
# =========================
styles = getSampleStyleSheet()
s_titulo_capa = ParagraphStyle(
    "TC", parent=styles["Title"], fontSize=36, leading=42,
    alignment=TA_CENTER, textColor=COR_PRIMARIA, spaceAfter=8,
)
s_subtitulo_capa = ParagraphStyle(
    "SC", parent=styles["Title"], fontSize=16, leading=22,
    alignment=TA_CENTER, textColor=COR_TEXTO_DIM, spaceAfter=20,
)
s_h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontSize=22, leading=26,
    textColor=COR_PRIMARIA, spaceBefore=10, spaceAfter=10,
)
s_h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontSize=15, leading=20,
    textColor=COR_PRIMARIA_ESCURA, spaceBefore=14, spaceAfter=6,
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


def lista(itens, estilo=s_lista):
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


def caixa(titulo, texto):
    inner = [
        Paragraph(f"<b>{titulo}</b>",
                  ParagraphStyle("CT", parent=s_h3,
                                 textColor=COR_PRIMARIA_ESCURA)),
        Paragraph(texto, s_body_left),
    ]
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
                      spaceBefore=4, spaceAfter=8)


def _rodape(canv, doc):
    canv.saveState()
    canv.setStrokeColor(COR_BORDA)
    canv.setLineWidth(0.3)
    canv.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canv.setFont("Helvetica", 8)
    canv.setFillColor(COR_TEXTO_DIM)
    canv.drawString(2 * cm, 1.1 * cm, f"Manual {APP_NOME} — {CANAL}")
    canv.drawRightString(
        A4[0] - 2 * cm, 1.1 * cm, f"Página {canv.getPageNumber()}"
    )
    canv.restoreState()


def _capa(canv, doc):
    pass  # capa sem rodapé


# =========================
# SEÇÕES
# =========================
def sec_capa(story):
    story.append(Spacer(1, 3.5 * cm))
    if os.path.exists(LOGO_PATH):
        try:
            img = Image(LOGO_PATH, width=3.5 * cm, height=3.5 * cm)
            img.hAlign = "CENTER"
            story.append(img)
            story.append(Spacer(1, 0.5 * cm))
        except Exception:
            pass
    story.append(p(APP_NOME, s_titulo_capa))
    story.append(p(TAGLINE, s_subtitulo_capa))
    story.append(Spacer(1, 1 * cm))
    story.append(p(
        "Manual do Usuário",
        ParagraphStyle("MU", parent=s_body, alignment=TA_CENTER,
                       fontSize=18, textColor=COR_TEXTO),
    ))
    story.append(Spacer(1, 5 * cm))
    story.append(p(
        f"Canal: <b>{CANAL}</b>",
        ParagraphStyle("CP", parent=s_body, alignment=TA_CENTER,
                       fontSize=12),
    ))
    story.append(p(
        CANAL_URL,
        ParagraphStyle("CU", parent=s_body, alignment=TA_CENTER,
                       fontSize=11, textColor=COR_PRIMARIA),
    ))
    story.append(Spacer(1, 1.5 * cm))
    story.append(p(
        f"Edição {datetime.now().strftime('%B/%Y').capitalize()}  "
        f"•  Distribuição gratuita",
        s_small,
    ))
    story.append(PageBreak())


def sec_sumario(story):
    story.append(p("Sumário", s_h1))
    story.append(divisor())
    itens = [
        ("1.", "O que é o BizuDeck"),
        ("2.", "Como funciona — visão geral"),
        ("3.", "Gerando perguntas com uma IA externa"),
        ("4.", "O formato do arquivo de quiz (.txt)"),
        ("5.", "Importando o quiz no app"),
        ("6.", "Modo Estudar — o quiz interativo"),
        ("7.", "Exportar para Anki (.apkg)"),
        ("8.", "Exportar PDF de estudo"),
        ("9.", "Configurações (voz, velocidade)"),
        ("10.", "Perguntas frequentes"),
        ("11.", "Canal e contato"),
    ]
    dados = [[n, t] for n, t in itens]
    tab = Table(dados, colWidths=[1.5 * cm, 14.5 * cm])
    tab.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("TEXTCOLOR", (0, 0), (0, -1), COR_PRIMARIA),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (1, 0), (1, -1), COR_TEXTO),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, COR_BORDA),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.append(tab)
    story.append(PageBreak())


def sec_1_o_que_e(story):
    story.append(p("1. O que é o BizuDeck", s_h1))
    story.append(divisor())
    story.append(p(
        "BizuDeck é um aplicativo para <b>estudo ativo</b>: você "
        "transforma qualquer matéria — Escola, Faculdade, Concurso "
        "Público — em um quiz interativo com áudio em português, "
        "feedback automático e exportação para Anki ou PDF."
    ))
    story.append(p("Para quem é", s_h2))
    for it in lista([
        "Estudante de ensino médio revisando vestibular",
        "Universitário se preparando para prova",
        "Concurseiro estudando edital",
        "Quem quer fixar conteúdo ouvindo + respondendo",
    ]):
        story.append(it)
    story.append(p("O que ele faz", s_h2))
    for it in lista([
        "<b>Lê</b> um arquivo .txt com perguntas e respostas no formato P>/R>/*>",
        "<b>Gera áudio</b> em português brasileiro de cada pergunta (TTS gratuito)",
        "<b>Roda o quiz</b> com placar ao vivo e feedback imediato",
        "<b>Exporta</b> baralho Anki .apkg com áudio embutido",
        "<b>Gera PDF</b> de estudo com gabarito e espaço pra anotação",
    ]):
        story.append(it)
    story.append(caixa(
        "Importante",
        "O BizuDeck <b>não tem IA dentro dele</b>. Quem gera as "
        "perguntas é o ChatGPT, Gemini, Claude ou qualquer LLM "
        "gratuito — o app só lê o resultado e roda o quiz. Funciona "
        "offline depois que o áudio for gerado.",
    ))
    story.append(PageBreak())


def sec_2_visao_geral(story):
    story.append(p("2. Como funciona — visão geral", s_h1))
    story.append(divisor())
    story.append(p("O fluxo completo, de ponta a ponta:"))
    for it in lista_numerada([
        "Você pega um <b>tema</b> (ex: Direito Constitucional) ou um <b>texto-base</b> (capítulo, resumo, slides).",
        "Cola o conteúdo num <b>prompt pronto</b> do app no ChatGPT/Gemini/Claude.",
        "A IA devolve um quiz no formato P>/R>/*>.",
        "Você salva como <b>.txt</b> e abre no BizuDeck.",
        "O app gera os <b>áudios</b> em português (opcional).",
        "Você <b>estuda</b>: responde, ouve, recebe feedback.",
        "(Opcional) Exporta o quiz para <b>Anki</b> ou <b>PDF</b> para revisão offline.",
    ]):
        story.append(it)
    story.append(p("As 4 abas do app", s_h2))
    dados = [
        ["Aba", "Função"],
        ["▶ Criar Quiz", "Importar .txt, gerar áudios, exportar Anki/PDF"],
        ["🎓 Estudar", "Quiz interativo (perguntas + respostas + placar)"],
        ["⚙ Configurações", "Voz PT-BR, velocidade da fala, modo de feedback"],
        ["ℹ Sobre", "Informações + canal + abrir este manual"],
    ]
    tab = Table(dados, colWidths=[4.5 * cm, 11.5 * cm], repeatRows=1)
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COR_PRIMARIA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, COR_BORDA),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f6f8fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tab)
    story.append(PageBreak())


def sec_3_ia(story):
    story.append(p("3. Gerando perguntas com uma IA externa", s_h1))
    story.append(divisor())
    story.append(p(
        "O app não chama LLM por dentro — você usa a IA que preferir, "
        "de graça. Recomendado: ChatGPT (chat.openai.com), Gemini "
        "(gemini.google.com) ou Claude (claude.ai). Todos têm plano "
        "gratuito."
    ))
    story.append(p("Passo a passo", s_h2))
    for it in lista_numerada([
        "Abra o app, vá em <b>▶ Criar Quiz</b>.",
        "Clique em <b>📋 Copiar prompt para IA</b>.",
        "Cole o prompt na conversa com o ChatGPT/Gemini/Claude.",
        "Substitua <i>[TEMA]</i> pelo assunto (ex: Direito Constitucional).",
        "(Opcional) Substitua <i>[CONTEÚDO]</i> por um capítulo, resumo, lista de tópicos. Pode deixar vazio.",
        "Envie. A IA vai devolver o quiz no formato correto.",
        "Copie a resposta inteira e salve em um arquivo <b>.txt</b>.",
        "Volte ao app e clique em <b>📂 Importar arquivo .txt</b>.",
    ]):
        story.append(it)
    story.append(caixa(
        "Dica para resultado melhor",
        "Se a IA escrever com Markdown (** , ##), peça: <i>\"Sem "
        "Markdown. Use exatamente P>, R>, A) B) C) D) e *>.\"</i> "
        "Se vier pouca questão, peça mais: <i>\"Gere 25 questões.\"</i>",
    ))
    story.append(PageBreak())


def sec_4_formato(story):
    story.append(p("4. O formato do arquivo de quiz (.txt)", s_h1))
    story.append(divisor())
    story.append(p(
        "Cada questão é um <b>bloco</b> separado por uma linha em branco. "
        "Existem dois tipos."
    ))
    story.append(p("Resposta aberta", s_h2))
    story.append(code([
        "P> Qual é o princípio da legalidade?",
        "R> A administração só faz o que a lei autoriza.",
    ]))
    story.append(p("Múltipla escolha", s_h2))
    story.append(code([
        "P> Qual o prazo da licença-maternidade na CF/88?",
        "A) 90 dias",
        "B) 100 dias",
        "C) 120 dias",
        "D) 180 dias",
        "*> C",
    ]))
    story.append(p(
        "Em <code>*&gt; X</code>, X é a letra correta (A, B, C ou D)."
    ))
    story.append(p("Pode misturar os dois tipos", s_h2))
    story.append(p(
        "No mesmo arquivo você combina perguntas abertas e múltipla "
        "escolha à vontade. O app detecta o tipo automaticamente."
    ))
    story.append(caixa(
        "Erros mais comuns",
        "1) Esquecer a linha em branco entre blocos. "
        "2) Usar <i>R:</i> em vez de <i>R&gt;</i>. "
        "3) Pôr a letra correta sem o <i>*&gt;</i>. "
        "Se o app reclamar, abra o .txt e confira a indentação.",
    ))
    story.append(PageBreak())


def sec_5_importar(story):
    story.append(p("5. Importando o quiz no app", s_h1))
    story.append(divisor())
    for it in lista_numerada([
        "Abra a aba <b>▶ Criar Quiz</b>.",
        "Clique em <b>📂 Importar arquivo .txt</b>.",
        "Selecione seu arquivo. O app conta as questões e mostra "
        "no rodapé: <i>X questões • Y abertas • Z múltipla escolha</i>.",
        "Se quiser ouvir as perguntas, clique em <b>🎧 Gerar áudios "
        "das perguntas</b>. Demora alguns segundos por pergunta.",
        "Pronto: pode partir para <b>▶ Iniciar Estudo</b>, "
        "<b>📦 Exportar Anki</b> ou <b>📄 Gerar PDF</b>.",
    ]):
        story.append(it)
    story.append(caixa(
        "Gerar áudio é opcional",
        "Você pode estudar sem ter gerado áudio nenhum — o app só "
        "mostra a pergunta em texto. Se quiser gerar depois, é só "
        "clicar no botão.",
    ))
    story.append(PageBreak())


def sec_6_estudar(story):
    story.append(p("6. Modo Estudar — o quiz interativo", s_h1))
    story.append(divisor())
    story.append(p(
        "É o coração do app. Mostra uma questão por vez, com placar "
        "ao vivo, e dá feedback imediato."
    ))
    story.append(p("Elementos da tela", s_h2))
    for it in lista([
        "<b>Título</b>: nome do quiz",
        "<b>Progresso</b>: \"Questão X de N • TIPO\"",
        "<b>Placar</b>: ✓ acertos    ◐ parciais    ✗ erros",
        "<b>Pergunta</b>: texto grande no card central",
        "<b>🔊 Ouvir pergunta</b>: toca o áudio TTS (se gerado)",
        "<b>Área de resposta</b>: muda conforme o tipo",
        "<b>Verificar</b> / <b>Próxima →</b>: navegação",
    ]):
        story.append(it)
    story.append(p("Respondendo uma questão ABERTA", s_h2))
    for it in lista_numerada([
        "Digite sua resposta no textbox.",
        "Clique em <b>Verificar resposta</b>.",
        "O app compara com o gabarito (ignora caixa, acento e pontuação).",
        "Recebe um dos 3 status:",
    ]):
        story.append(it)
    story.append(p("&nbsp;&nbsp;&nbsp;&nbsp;<b>✓ Correto</b> — similaridade ≥ 80%", s_body_left))
    story.append(p("&nbsp;&nbsp;&nbsp;&nbsp;<b>◐ Parcial</b> — entre 40% e 79% (você está no caminho)", s_body_left))
    story.append(p("&nbsp;&nbsp;&nbsp;&nbsp;<b>✗ Distante</b> — abaixo de 40%", s_body_left))
    story.append(p(
        "O <b>gabarito é sempre mostrado</b> abaixo, mesmo se você "
        "acertou. Use pra confirmar."
    ))
    story.append(p("Respondendo uma questão de MÚLTIPLA ESCOLHA", s_h2))
    for it in lista_numerada([
        "Clique numa das opções (A, B, C ou D). Ela fica destacada em laranja.",
        "Clique em <b>Verificar resposta</b>.",
        "A opção correta fica verde. Se você errou, a sua escolha fica vermelha.",
    ]):
        story.append(it)
    story.append(p("Final do quiz", s_h2))
    story.append(p(
        "Ao terminar a última questão, o app mostra <b>aproveitamento "
        "em %</b> e oferece <b>🔄 Refazer este quiz</b> ou voltar "
        "para a tela inicial."
    ))
    story.append(PageBreak())


def sec_7_anki(story):
    story.append(p("7. Exportar para Anki (.apkg)", s_h1))
    story.append(divisor())
    story.append(p(
        "O <b>Anki</b> é um aplicativo gratuito de flashcards com "
        "repetição espaçada. Excelente para revisar a longo prazo. "
        "Site oficial: <font color='#f59e0b'>https://apps.ankiweb.net</font>"
    ))
    story.append(p("Exportando", s_h2))
    for it in lista_numerada([
        "Na aba <b>▶ Criar Quiz</b>, com um quiz já carregado, clique "
        "em <b>📦 Exportar para Anki (.apkg)</b>.",
        "Se você gerou áudio antes, o áudio vai embutido no baralho.",
        "Se não gerou, o app pergunta se quer exportar sem áudio — "
        "vale a pena se você só quer estudar texto.",
        "O arquivo .apkg é salvo em <i>quizzes/&lt;nome_do_quiz&gt;/</i>",
    ]):
        story.append(it)
    story.append(p("Importando no Anki", s_h2))
    for it in lista_numerada([
        "Abra o Anki Desktop.",
        "Vá em <b>Arquivo → Importar</b> (ou File → Import).",
        "Selecione o arquivo <i>.apkg</i>.",
        "O baralho aparece com o nome do quiz, áudios já embutidos, "
        "tema escuro com acento laranja.",
    ]):
        story.append(it)
    story.append(caixa(
        "Como aparece no Anki",
        "<b>Frente</b>: áudio + pergunta + (em múltipla) as alternativas. "
        "<b>Verso</b>: mostra a resposta destacada em laranja. "
        "Funciona offline no Anki Desktop, Android (AnkiDroid) e iOS.",
    ))
    story.append(PageBreak())


def sec_8_pdf(story):
    story.append(p("8. Exportar PDF de estudo", s_h1))
    story.append(divisor())
    story.append(p(
        "Para quem prefere papel ou quer revisar no celular sem o app:"
    ))
    for it in lista_numerada([
        "Na aba <b>▶ Criar Quiz</b>, clique em <b>📄 Gerar PDF de estudo</b>.",
        "O arquivo <i>&lt;nome_do_quiz&gt;_estudo.pdf</i> é salvo em "
        "<i>quizzes/&lt;nome_do_quiz&gt;/</i>.",
    ]):
        story.append(it)
    story.append(p("O que vem no PDF", s_h2))
    for it in lista([
        "<b>Capa</b> com título, total de questões e data",
        "<b>Questões numeradas</b> (001, 002…) marcadas por tipo",
        "Múltipla escolha: alternativas listadas, correta marcada com ✓ em laranja",
        "Aberta: resposta esperada + <b>3 linhas em branco</b> pra anotação à mão",
    ]):
        story.append(it)
    story.append(PageBreak())


def sec_9_config(story):
    story.append(p("9. Configurações", s_h1))
    story.append(divisor())
    story.append(p("Voz para PORTUGUÊS", s_h2))
    story.append(p(
        "3 vozes nativas do Edge TTS (gratuitas):"
    ))
    for it in lista([
        "<b>pt-BR-FranciscaNeural</b> — feminina (padrão)",
        "<b>pt-BR-AntonioNeural</b> — masculina",
        "<b>pt-BR-ThalitaMultilingualNeural</b> — feminina, multilíngue",
    ]):
        story.append(it)
    story.append(p(
        "<b>Ao trocar de voz, o app toca uma frase de demonstração</b> "
        "imediatamente. Use pra escolher a que te agradar mais."
    ))
    story.append(p("Velocidade", s_h2))
    story.append(p(
        "Slider de -50% (bem devagar) a +50% (rápido). Padrão: -10%. "
        "Recomendado deixar entre -10% e 0% para acompanhar bem."
    ))
    story.append(p("Modo de feedback (perguntas abertas)", s_h2))
    for it in lista([
        "<b>Relaxado (padrão)</b>: app calcula similaridade e dá "
        "✓/◐/✗ junto com o gabarito",
        "<b>Manual</b>: app só mostra o gabarito; você julga se acertou",
    ]):
        story.append(it)
    story.append(PageBreak())


def sec_10_faq(story):
    story.append(p("10. Perguntas frequentes", s_h1))
    story.append(divisor())

    faq = [
        ("O app precisa de internet?",
         "Apenas para <b>gerar áudio</b> (Edge TTS é um serviço "
         "online gratuito). Depois que o áudio é gerado, o estudo, "
         "exportação de Anki e PDF funcionam offline."),
        ("Tenho que pagar alguma chave de API?",
         "Não. O Edge TTS é gratuito e a IA que gera o quiz "
         "(ChatGPT, Gemini, Claude) tem plano free."),
        ("Onde os meus arquivos ficam?",
         "Em <i>quizzes/&lt;nome_do_quiz&gt;/</i>: áudios .mp3, "
         "baralho .apkg e PDF de estudo. Tudo dentro da pasta do app."),
        ("O Windows reclamou ao abrir o .exe.",
         "É falso positivo do PyInstaller. Clique em <b>Mais "
         "informações → Executar assim mesmo</b>."),
        ("O áudio falhou no meio da geração.",
         "Geralmente é instabilidade do Edge TTS. O app já tenta 3 vezes "
         "automaticamente. Se persistir, tente de novo em alguns minutos."),
        ("A comparação relaxada errou — minha resposta tava certa.",
         "Use o <b>modo manual</b> em Configurações. Aí o app só "
         "mostra o gabarito e você julga sozinho."),
        ("Posso editar o .txt à mão?",
         "Sim! É só texto. Abra no Bloco de Notas ou em qualquer editor."),
        ("Posso usar o app pra outras matérias além de Direito?",
         "Sim. Os exemplos vêm com Direito e História, mas o prompt e "
         "o app são genéricos. Use pra Termodinâmica, Anatomia, "
         "Literatura, Inglês, qualquer coisa."),
    ]

    for pergunta, resposta in faq:
        story.append(p(pergunta, s_h2))
        story.append(p(resposta))
    story.append(PageBreak())


def sec_11_canal(story):
    story.append(p("11. Canal e contato", s_h1))
    story.append(divisor())
    story.append(p(
        f"O BizuDeck é uma ferramenta gratuita criada por <b>{CANAL}</b>. "
        "No canal há tutoriais, scripts e outras automações de estudo "
        "e produtividade."
    ))
    story.append(Spacer(1, 0.4 * cm))
    story.append(p(
        f"<b>YouTube</b>:  {CANAL_URL}", s_body_left,
    ))
    story.append(Spacer(1, 0.6 * cm))
    story.append(caixa(
        "Compartilhe se ajudar",
        "Se o BizuDeck te ajudou a destravar uma matéria ou passar "
        "numa prova, marque alguém que precisa nas redes ou comente "
        "no canal. É o que mantém o projeto vivo e gratuito.",
    ))
    story.append(Spacer(1, 2 * cm))
    story.append(p("Bom estudo!",
                    ParagraphStyle("BS", parent=s_body,
                                   alignment=TA_CENTER, fontSize=14,
                                   textColor=COR_PRIMARIA)))
    story.append(p(f"— {CANAL}", s_small))


# =========================
# MAIN
# =========================
def build():
    os.makedirs(os.path.dirname(ARQUIVO_SAIDA), exist_ok=True)
    doc = SimpleDocTemplate(
        ARQUIVO_SAIDA, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.2 * cm,
        title=f"Manual {APP_NOME}", author=CANAL,
        subject=f"Manual do usuário do {APP_NOME}",
    )
    story = []
    sec_capa(story)
    sec_sumario(story)
    sec_1_o_que_e(story)
    sec_2_visao_geral(story)
    sec_3_ia(story)
    sec_4_formato(story)
    sec_5_importar(story)
    sec_6_estudar(story)
    sec_7_anki(story)
    sec_8_pdf(story)
    sec_9_config(story)
    sec_10_faq(story)
    sec_11_canal(story)
    doc.build(story, onFirstPage=_capa, onLaterPages=_rodape)
    print(f"PDF gerado: {os.path.abspath(ARQUIVO_SAIDA)}")


if __name__ == "__main__":
    build()
