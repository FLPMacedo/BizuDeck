"""
BizuDeck — Bizus que você memoriza.
Quiz interativo com áudio para estudo ativo (Escola, Faculdade,
Concursos Públicos).

Lê arquivos .txt no formato P>/R>/*> (perguntas abertas + múltipla
escolha), gera áudio das perguntas com Edge TTS e roda o quiz com
feedback imediato (sem precisar de IA dentro do app).

Canal: @UaiScript — https://www.youtube.com/@UaiScript
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import sys
import threading
import tkinter as tk
import unicodedata
import webbrowser
from datetime import datetime
from difflib import SequenceMatcher
from tkinter import filedialog, messagebox

import time

import customtkinter as ctk
import edge_tts
import genanki
import pygame

import podcast as podcast_mod
from reportlab.lib import colors as pdf_colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def resource_path(relative: str) -> str:
    """Resolve caminhos rodando .py e empacotado pelo PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative)


# =========================
# CONFIGURAÇÕES GLOBAIS
# =========================
APP_NOME = "BizuDeck"
AUTOR = "@UaiScript"
CANAL_URL = "https://www.youtube.com/@UaiScript"
OUTPUT_DIR = "quizzes"
LOGS_DIR = "logs"
CONFIG_FILE = "config_bizudeck.json"

DEFAULT_CONFIG = {
    "voice_pergunta": "pt-BR-FranciscaNeural",  # Francisca (feminina)
    "voice_resposta": "pt-BR-AntonioNeural",     # Antonio (masculino)
    "rate": -10,
    "modo_feedback": "relaxado",  # "relaxado" | "manual"
    "autor": AUTOR,
}

VOICES_PT = [
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
    "pt-BR-ThalitaMultilingualNeural",
]

# Paleta — laranja-âmbar (diferencia do verde-água do app de inglês)
COLOR_BG = "#14110d"
COLOR_SIDEBAR = "#1c1812"
COLOR_CARD = "#241f17"
COLOR_CARD_HOVER = "#2c261c"
COLOR_ACCENT = "#f59e0b"
COLOR_ACCENT_HOVER = "#fbbf24"
COLOR_DANGER = "#e5534b"
COLOR_SUCCESS = "#22c55e"
COLOR_WARN = "#facc15"
COLOR_TEXT = "#f5f1ea"
COLOR_TEXT_DIM = "#a39682"
COLOR_BORDER = "#3a3024"

FONT_TITLE = ("Segoe UI Semibold", 22)
FONT_H2 = ("Segoe UI Semibold", 16)
FONT_QUESTION = ("Segoe UI", 18)
FONT_LABEL = ("Segoe UI", 12)
FONT_INPUT = ("Segoe UI", 13)
FONT_BTN = ("Segoe UI Semibold", 13)
FONT_SIDEBAR = ("Segoe UI", 14)


# =========================
# LOGGING
# =========================
os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "bizudeck.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("bizudeck")


# =========================
# CONFIG PERSISTENTE
# =========================
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = {**DEFAULT_CONFIG, **data}
            # Migração de formato antigo: 1 voz só -> 2 vozes
            if "voice_pt" in cfg:
                voz_antiga = cfg.pop("voice_pt")
                if voz_antiga and "voice_pergunta" not in data:
                    cfg["voice_pergunta"] = voz_antiga
                if voz_antiga and "voice_resposta" not in data:
                    cfg["voice_resposta"] = voz_antiga
            return cfg
        except Exception as e:
            log.warning(f"Falha ao ler config: {e}. Usando padrão.")
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# =========================
# HELPERS
# =========================
def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", name.replace(" ", "_"))


def format_rate(rate_int: int) -> str:
    sign = "+" if rate_int >= 0 else ""
    return f"{sign}{rate_int}%"


def normalizar_texto(s: str) -> str:
    """Lowercase + sem acento + sem pontuação + espaços normalizados."""
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def calcular_similaridade(resposta: str, gabarito: str) -> float:
    """Retorna ratio [0..1] entre duas strings normalizadas."""
    a = normalizar_texto(resposta)
    b = normalizar_texto(gabarito)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def avaliar_resposta(resposta: str, gabarito: str) -> tuple[str, float]:
    """Retorna ('correto'|'parcial'|'incorreto', similaridade)."""
    sim = calcular_similaridade(resposta, gabarito)
    if sim >= 0.8:
        return "correto", sim
    if sim >= 0.4:
        return "parcial", sim
    return "incorreto", sim


# =========================
# PARSER DO FORMATO P>/R>/*>
# =========================
def parse_quiz(texto: str) -> list[dict]:
    """Parseia texto em lista de blocos.
    Cada bloco vira: {
        'tipo': 'aberta' | 'multipla',
        'pergunta': str,
        'resposta_correta': str,
        'opcoes': [{'letra': str, 'texto': str}, ...]  # só múltipla
    }
    """
    blocos = []
    atual = None

    def finalizar(b):
        if not b or "pergunta" not in b:
            return
        if "tipo" not in b:
            b["tipo"] = "multipla" if b.get("opcoes") else "aberta"
        if b["tipo"] == "multipla":
            letra = b.get("letra_correta", "")
            for opc in b.get("opcoes", []):
                if opc["letra"] == letra:
                    b["resposta_correta"] = opc["texto"]
                    break
            else:
                b["resposta_correta"] = ""
        b.setdefault("resposta_correta", "")
        b.setdefault("opcoes", [])
        blocos.append(b)

    for linha in texto.splitlines():
        s = linha.rstrip()
        if not s.strip():
            if atual:
                finalizar(atual)
                atual = None
            continue
        if s.startswith("P>"):
            if atual:
                finalizar(atual)
            atual = {"pergunta": s[2:].strip(), "opcoes": []}
        elif atual is None:
            continue  # texto fora de bloco
        elif s.startswith("R>"):
            atual["tipo"] = "aberta"
            atual["resposta_correta"] = s[2:].strip()
        elif s.startswith("*>"):
            atual["tipo"] = "multipla"
            atual["letra_correta"] = s[2:].strip().upper()
        elif re.match(r"^[A-Ja-j]\)", s):
            letra = s[0].upper()
            texto_opc = s[2:].strip()
            atual.setdefault("opcoes", []).append(
                {"letra": letra, "texto": texto_opc}
            )

    if atual:
        finalizar(atual)
    return blocos


# =========================
# TTS
# =========================
async def gerar_audio_async(
    texto: str, voz: str, caminho: str, rate: str,
    cancel: threading.Event, max_retries: int = 3,
) -> None:
    for tentativa in range(1, max_retries + 1):
        if cancel.is_set():
            raise asyncio.CancelledError()
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate=rate)
            await tts.save(caminho)
            return
        except Exception as e:
            log.warning(f"TTS tentativa {tentativa} falhou: {e}")
            if tentativa == max_retries:
                raise
            await asyncio.sleep(1.5 * tentativa)


def _texto_audio_resposta(bloco: dict) -> str:
    """Texto que o TTS vai falar como áudio da resposta.
    - Aberta: o próprio texto da resposta.
    - Múltipla: 'Letra X. Texto da opção correta.'
    """
    if bloco.get("tipo") == "multipla":
        letra = bloco.get("letra_correta", "")
        texto = bloco.get("resposta_correta", "")
        if letra and texto:
            return f"Letra {letra}. {texto}."
        if letra:
            return f"Letra {letra}."
        return texto or "Sem resposta."
    return bloco.get("resposta_correta", "") or "Sem resposta."


# =========================
# EXPORTAR PARA ANKI (.apkg)
# =========================
ANKI_MODEL_ID = 7894561233  # bumpado: campos novos (AudioResposta)
ANKI_CSS = """
.card { font-family: Segoe UI, Arial, sans-serif; font-size: 20px;
        text-align: center; color: #f5f1ea; background: #14110d;
        padding: 18px; }
.opcoes { color: #a39682; font-size: 17px; text-align: left;
          margin-top: 14px; line-height: 1.6; }
.resposta { color: #f59e0b; font-size: 20px; margin-top: 12px;
            font-weight: bold; }
.letra { color: #f59e0b; font-size: 26px; font-weight: bold;
         margin-bottom: 6px; }
.autor { color: #a39682; font-size: 11px; margin-top: 16px; }
"""


def exportar_apkg(
    blocos: list[dict],
    audios_pergunta: dict[int, str],
    audios_resposta: dict[int, str],
    nome_deck: str, pasta_destino: str, autor: str,
) -> str:
    """Gera um .apkg com áudio na pergunta e áudio na resposta."""
    deck_id = int(hashlib.md5(nome_deck.encode()).hexdigest()[:10], 16)
    model = genanki.Model(
        ANKI_MODEL_ID, "BizuDeck Q&A v2",
        fields=[
            {"name": "Pergunta"},
            {"name": "Opcoes"},
            {"name": "Resposta"},
            {"name": "AudioPergunta"},
            {"name": "AudioResposta"},
            {"name": "Tipo"},
            {"name": "Autor"},
        ],
        templates=[{
            "name": "Pergunta -> Resposta",
            "qfmt": "{{AudioPergunta}}<br><br>{{Pergunta}}"
                    "{{#Opcoes}}<div class='opcoes'>{{Opcoes}}</div>"
                    "{{/Opcoes}}",
            "afmt": "{{FrontSide}}<hr>"
                    "<div class='resposta'>{{Resposta}}</div>"
                    "{{AudioResposta}}"
                    "<div class='autor'>{{Autor}}</div>",
        }],
        css=ANKI_CSS,
    )
    deck = genanki.Deck(deck_id, nome_deck)
    media_files = []

    for i, bloco in enumerate(blocos):
        # Áudio da pergunta
        ap_field = ""
        ap_path = audios_pergunta.get(i)
        if ap_path and os.path.isfile(ap_path):
            ap_field = f"[sound:{os.path.basename(ap_path)}]"
            media_files.append(ap_path)

        # Áudio da resposta
        ar_field = ""
        ar_path = audios_resposta.get(i)
        if ar_path and os.path.isfile(ar_path):
            ar_field = f"[sound:{os.path.basename(ar_path)}]"
            media_files.append(ar_path)

        # Opções (só múltipla)
        opcoes_html = ""
        if bloco["tipo"] == "multipla":
            linhas = [
                f"{opc['letra']}) {opc['texto']}"
                for opc in bloco.get("opcoes", [])
            ]
            opcoes_html = "<br>".join(linhas)

        # Resposta formatada
        if bloco["tipo"] == "multipla":
            letra = bloco.get("letra_correta", "")
            texto = bloco.get("resposta_correta", "")
            resposta_html = (
                f"<div class='letra'>{letra}</div>"
                f"<div>{texto}</div>"
            )
        else:
            resposta_html = bloco.get("resposta_correta", "")

        note = genanki.Note(
            model=model,
            fields=[
                bloco["pergunta"],
                opcoes_html,
                resposta_html,
                ap_field,
                ar_field,
                bloco["tipo"],
                autor,
            ],
        )
        deck.add_note(note)

    pacote = genanki.Package(deck)
    pacote.media_files = media_files
    out = os.path.join(pasta_destino, f"{safe_name(nome_deck)}.apkg")
    pacote.write_to_file(out)
    return out


# =========================
# EXPORTAR PDF DE ESTUDO
# =========================
_PDF_COR_ACCENT = pdf_colors.HexColor("#f59e0b")
_PDF_COR_TEXTO = pdf_colors.HexColor("#1c2128")
_PDF_COR_DIM = pdf_colors.HexColor("#566573")
_PDF_COR_BORDER = pdf_colors.HexColor("#c8d0d8")


def exportar_pdf(
    blocos: list[dict], nome_quiz: str, pasta_destino: str, autor: str,
) -> str:
    """Gera PDF de estudo com perguntas, opções, gabarito e linhas
    para anotação."""
    out = os.path.join(pasta_destino, f"{safe_name(nome_quiz)}_estudo.pdf")
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=nome_quiz, author=autor,
    )
    styles = getSampleStyleSheet()
    s_title = ParagraphStyle(
        "T", parent=styles["Title"], fontSize=28, alignment=TA_CENTER,
        textColor=_PDF_COR_ACCENT, spaceAfter=14,
    )
    s_h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=14,
        textColor=_PDF_COR_ACCENT, spaceBefore=10, spaceAfter=6,
    )
    s_body = ParagraphStyle(
        "B", parent=styles["BodyText"], fontSize=11, leading=15,
        alignment=TA_LEFT, textColor=_PDF_COR_TEXTO,
    )
    s_pergunta = ParagraphStyle(
        "P", parent=s_body, fontName="Helvetica-Bold", fontSize=12,
        spaceBefore=6, spaceAfter=4,
    )
    s_opcao = ParagraphStyle(
        "O", parent=s_body, leftIndent=14, spaceAfter=2,
    )
    s_gab = ParagraphStyle(
        "G", parent=s_body, leftIndent=14, textColor=_PDF_COR_ACCENT,
        fontName="Helvetica-Bold", spaceBefore=6,
    )
    s_small = ParagraphStyle(
        "S", parent=styles["BodyText"], fontSize=9,
        textColor=_PDF_COR_DIM, alignment=TA_CENTER,
    )

    story = []
    # Capa
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph(nome_quiz, s_title))
    story.append(Paragraph("Guia de Estudo — BizuDeck",
                            ParagraphStyle("Sub", parent=s_body,
                                           alignment=TA_CENTER, fontSize=14,
                                           textColor=_PDF_COR_DIM)))
    story.append(Spacer(1, 6 * cm))

    abertas = sum(1 for b in blocos if b["tipo"] == "aberta")
    multiplas = sum(1 for b in blocos if b["tipo"] == "multipla")
    story.append(Paragraph(
        f"<b>Total:</b> {len(blocos)} questões  •  "
        f"{abertas} abertas  •  {multiplas} múltipla escolha",
        ParagraphStyle("Cnt", parent=s_body, alignment=TA_CENTER, fontSize=12),
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"<b>Autor:</b> {autor}     "
        f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y')}",
        ParagraphStyle("Da", parent=s_body, alignment=TA_CENTER, fontSize=11),
    ))
    story.append(PageBreak())

    # Questões com gabarito e linhas pra anotação
    story.append(Paragraph("Questões", s_title))
    story.append(HRFlowable(width="100%", color=_PDF_COR_BORDER,
                             spaceAfter=10))

    for i, b in enumerate(blocos, start=1):
        tag = "MÚLTIPLA ESCOLHA" if b["tipo"] == "multipla" else "ABERTA"
        story.append(Paragraph(
            f"<font color='#a39682'>{i:03}  •  {tag}</font>",
            ParagraphStyle("Tg", parent=s_body, fontSize=9),
        ))
        story.append(Paragraph(b["pergunta"], s_pergunta))

        if b["tipo"] == "multipla":
            for opc in b.get("opcoes", []):
                eh_correta = opc["letra"] == b.get("letra_correta", "")
                marca = " ✓" if eh_correta else ""
                cor = "#f59e0b" if eh_correta else "#1c2128"
                story.append(Paragraph(
                    f"<font color='{cor}'>{opc['letra']}) "
                    f"{opc['texto']}{marca}</font>",
                    s_opcao,
                ))
            story.append(Paragraph(
                f"Gabarito: {b.get('letra_correta', '')}", s_gab,
            ))
        else:
            story.append(Paragraph(
                f"Resposta esperada: {b.get('resposta_correta', '')}",
                s_gab,
            ))
            # 3 linhas para anotações
            for _ in range(3):
                story.append(HRFlowable(
                    width="100%", color=_PDF_COR_BORDER, thickness=0.3,
                    spaceBefore=6, spaceAfter=2,
                ))

        story.append(Spacer(1, 0.4 * cm))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(f"Gerado por BizuDeck — {autor}", s_small))

    doc.build(story)
    return out


# =========================
# APP
# =========================
class QuizApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.title(f"{APP_NOME} — Provas & Concursos")
        self.geometry("1180x780")
        self.minsize(1050, 720)
        self.configure(fg_color=COLOR_BG)
        ctk.set_appearance_mode("dark")

        try:
            ico = resource_path("assets/uaiscript.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception as e:
            log.warning(f"Falha ao definir ícone: {e}")

        # Estado
        self.cancel_event = threading.Event()
        self.quiz_blocos: list[dict] = []
        self.quiz_audios_pergunta: dict[int, str] = {}  # idx -> .mp3
        self.quiz_audios_resposta: dict[int, str] = {}  # idx -> .mp3
        self.idx_atual = 0
        self.acertos = 0
        self.parciais = 0
        self.erros = 0
        self.nome_quiz = ""

        try:
            pygame.mixer.init()
        except Exception as e:
            log.warning(f"pygame.mixer falhou: {e}")

        self._build_layout()
        self._show_view("criar")

        # Extrai exemplos do bundle pra pasta acessível (lateral ao .exe ou
        # Documentos). Feedback no status pro usuário saber onde ficou.
        try:
            pasta_exemplos = self._garantir_pasta_exemplos()
            if pasta_exemplos:
                # Usa after pra rodar depois do layout pronto
                self.after(
                    200,
                    lambda p=pasta_exemplos: self._status(
                        f"📁 Pasta de exemplos pronta: {p}"
                    ),
                )
                log.info(f"Pasta de exemplos disponível em: {pasta_exemplos}")
            else:
                log.warning("Não foi possível disponibilizar pasta de exemplos")
        except Exception as e:
            log.warning(f"Falha ao preparar exemplos: {e}")

    # -------- Layout --------
    def _build_layout(self):
        self.sidebar = ctk.CTkFrame(
            self, fg_color=COLOR_SIDEBAR, corner_radius=0, width=240
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="BIZUDECK",
            font=("Segoe UI Semibold", 20), text_color=COLOR_ACCENT,
        ).pack(pady=(30, 4), padx=20, anchor="w")
        ctk.CTkLabel(
            self.sidebar, text="Provas & Concursos",
            font=("Segoe UI", 11), text_color=COLOR_TEXT_DIM,
        ).pack(padx=20, anchor="w")
        ctk.CTkFrame(self.sidebar, height=1, fg_color=COLOR_BORDER).pack(
            fill="x", padx=20, pady=22
        )

        self.nav_buttons = {}
        for key, label, icon in [
            ("criar", "Criar Quiz", "▶"),
            ("estudar", "Estudar", "🎓"),
            ("podcast", "Podcast", "🎙"),
            ("config", "Configurações", "⚙"),
            ("sobre", "Sobre", "ℹ"),
        ]:
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {icon}   {label}", anchor="w",
                font=FONT_SIDEBAR, fg_color="transparent",
                hover_color=COLOR_CARD_HOVER, text_color=COLOR_TEXT,
                corner_radius=8, height=42,
                command=lambda k=key: self._show_view(k),
            )
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = btn

        rodape = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        rodape.pack(side="bottom", fill="x", pady=14, padx=12)
        ctk.CTkButton(
            rodape, text=f"▶  {AUTOR}",
            font=("Segoe UI Semibold", 12), fg_color="transparent",
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            anchor="w", height=34, corner_radius=8,
            command=lambda: webbrowser.open(CANAL_URL),
        ).pack(fill="x")
        ctk.CTkLabel(
            rodape, text="Inscreva-se no YouTube",
            font=("Segoe UI", 9), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=10)

        self.main = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main.pack(side="right", fill="both", expand=True)

        self.views = {
            "criar": self._build_view_criar(),
            "estudar": self._build_view_estudar(),
            "podcast": self._build_view_podcast(),
            "config": self._build_view_config(),
            "sobre": self._build_view_sobre(),
        }

    def _show_view(self, key: str):
        for v in self.views.values():
            v.pack_forget()
        self.views[key].pack(fill="both", expand=True, padx=24, pady=20)
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=COLOR_CARD, text_color=COLOR_ACCENT)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT)
        if key == "estudar":
            self._renderizar_questao_atual()

    def _card(self, parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, fg_color=COLOR_CARD, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER,
        )

    # -------- View: CRIAR QUIZ --------
    def _build_view_criar(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main, fg_color="transparent")

        header = ctk.CTkFrame(view, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            header, text="Criar Quiz", font=FONT_TITLE, text_color=COLOR_TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Importe um arquivo .txt no formato P>/R>/*>. "
                 "Use o prompt abaixo para gerar com ChatGPT, Gemini ou Claude.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(2, 0))

        # Card: ações
        card_acoes = self._card(view)
        card_acoes.pack(fill="x", pady=8)
        linha = ctk.CTkFrame(card_acoes, fg_color="transparent")
        linha.pack(fill="x", padx=14, pady=14)
        ctk.CTkButton(
            linha, text="📂  Importar arquivo .txt",
            font=FONT_BTN, height=44, width=240,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=10,
            command=self._importar_quiz,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            linha, text="📋  Copiar prompt para IA",
            font=FONT_BTN, height=44, width=220,
            fg_color="transparent", border_width=1,
            border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            corner_radius=10,
            command=self._mostrar_prompt_ia,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            linha, text="📁  Abrir exemplos",
            font=FONT_BTN, height=44, width=160,
            fg_color="transparent", border_width=1,
            border_color=COLOR_BORDER,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_TEXT,
            corner_radius=10,
            command=self._abrir_exemplos,
        ).pack(side="left", padx=4)

        # Card: preview do conteúdo
        card_preview = self._card(view)
        card_preview.pack(fill="both", expand=True, pady=8)
        ctk.CTkLabel(
            card_preview, text="Quiz",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(14, 4))

        # Linha do nome do baralho
        linha_nome = ctk.CTkFrame(card_preview, fg_color="transparent")
        linha_nome.pack(fill="x", padx=18, pady=(2, 6))
        ctk.CTkLabel(
            linha_nome, text="Nome do baralho:",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        ).pack(side="left", padx=(0, 8))
        self.entry_nome_quiz = ctk.CTkEntry(
            linha_nome, font=FONT_INPUT, height=32,
            border_color=COLOR_BORDER,
            placeholder_text="(será preenchido ao importar)",
        )
        self.entry_nome_quiz.pack(side="left", fill="x", expand=True)

        # Resumo + indicador de modificação
        linha_resumo = ctk.CTkFrame(card_preview, fg_color="transparent")
        linha_resumo.pack(fill="x", padx=18, pady=(0, 6))
        self.lbl_resumo = ctk.CTkLabel(
            linha_resumo,
            text="Nenhum arquivo carregado ainda.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        )
        self.lbl_resumo.pack(side="left")
        self.lbl_modificado = ctk.CTkLabel(
            linha_resumo, text="", font=FONT_LABEL,
            text_color=COLOR_WARN,
        )
        self.lbl_modificado.pack(side="right")

        # Editor de texto (editável)
        self.txt_preview = ctk.CTkTextbox(
            card_preview, font=("Consolas", 11), fg_color=COLOR_BG,
            border_color=COLOR_BORDER, border_width=1, corner_radius=8,
            wrap="word", undo=True,
        )
        self.txt_preview.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        self._modificado = False
        self.txt_preview.bind(
            "<KeyRelease>", lambda e: self._marcar_modificado()
        )

        # Linha de botões do editor
        editor_btns = ctk.CTkFrame(card_preview, fg_color="transparent")
        editor_btns.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(
            editor_btns, text="✓  Atualizar / Validar",
            font=("Segoe UI Semibold", 12), height=34, width=170,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=8,
            command=self._validar_editor,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            editor_btns, text="➕  Adicionar questão",
            font=("Segoe UI", 12), height=34, width=160,
            fg_color=COLOR_CARD_HOVER, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, corner_radius=8,
            command=self._adicionar_questao_template,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            editor_btns, text="💾  Salvar como…",
            font=("Segoe UI", 12), height=34, width=140,
            fg_color=COLOR_CARD_HOVER, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, corner_radius=8,
            command=self._salvar_quiz_como,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            editor_btns, text="📄  Novo em branco",
            font=("Segoe UI", 12), height=34, width=160,
            fg_color="transparent", border_width=1,
            border_color=COLOR_BORDER,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_TEXT_DIM,
            corner_radius=8,
            command=self._novo_quiz_em_branco,
        ).pack(side="right", padx=4)

        # Card: gerar áudio + iniciar
        card_iniciar = self._card(view)
        card_iniciar.pack(fill="x", pady=8)
        self.progress = ctk.CTkProgressBar(
            card_iniciar, height=10, progress_color=COLOR_ACCENT,
            fg_color=COLOR_BG, corner_radius=6,
        )
        self.progress.set(0)
        self.progress.pack(fill="x", padx=18, pady=(14, 4))
        self.lbl_status = ctk.CTkLabel(
            card_iniciar, text="Aguardando…",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        )
        self.lbl_status.pack(anchor="w", padx=18)

        # Linha 1: gerar áudios + iniciar estudo
        botoes = ctk.CTkFrame(card_iniciar, fg_color="transparent")
        botoes.pack(fill="x", padx=14, pady=(14, 6))
        self.btn_gerar = ctk.CTkButton(
            botoes, text="🎧  Gerar áudios das perguntas",
            font=FONT_BTN, height=46,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=10,
            command=self._gerar_audios_clicado, state="disabled",
        )
        self.btn_gerar.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_iniciar = ctk.CTkButton(
            botoes, text="▶  Iniciar Estudo",
            font=FONT_BTN, height=46, width=200,
            fg_color="transparent", border_width=1,
            border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            corner_radius=10,
            command=self._iniciar_estudo, state="disabled",
        )
        self.btn_iniciar.pack(side="right", padx=4)

        # Linha 2: exportar Anki + PDF de estudo
        exporta = ctk.CTkFrame(card_iniciar, fg_color="transparent")
        exporta.pack(fill="x", padx=14, pady=(0, 14))
        self.btn_anki = ctk.CTkButton(
            exporta, text="📦  Exportar para Anki (.apkg)",
            font=FONT_BTN, height=40,
            fg_color=COLOR_CARD_HOVER, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, corner_radius=10,
            command=self._exportar_anki_clicado, state="disabled",
        )
        self.btn_anki.pack(side="left", fill="x", expand=True, padx=4)
        self.btn_pdf = ctk.CTkButton(
            exporta, text="📄  Gerar PDF de estudo",
            font=FONT_BTN, height=40,
            fg_color=COLOR_CARD_HOVER, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT, corner_radius=10,
            command=self._exportar_pdf_clicado, state="disabled",
        )
        self.btn_pdf.pack(side="left", fill="x", expand=True, padx=4)

        return view

    def _importar_quiz(self):
        path = filedialog.askopenfilename(
            title="Selecione um quiz .txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                conteudo = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as f:
                conteudo = f.read()

        blocos = parse_quiz(conteudo)
        if not blocos:
            messagebox.showerror(
                "Formato inválido",
                "Nenhuma questão reconhecida.\n\n"
                "Verifique se cada bloco tem 'P>' e ('R>' ou '*>').",
            )
            return

        abertas = sum(1 for b in blocos if b["tipo"] == "aberta")
        multiplas = sum(1 for b in blocos if b["tipo"] == "multipla")

        self.quiz_blocos = blocos
        self.quiz_audios_pergunta = {}
        self.quiz_audios_resposta = {}
        self.nome_quiz = os.path.splitext(os.path.basename(path))[0]

        self.entry_nome_quiz.delete(0, "end")
        self.entry_nome_quiz.insert(0, self.nome_quiz)

        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", conteudo)
        self._modificado = False
        self.lbl_modificado.configure(text="")
        self.lbl_resumo.configure(
            text=f"{len(blocos)} questões  •  {abertas} abertas  •  "
                 f"{multiplas} múltipla escolha",
            text_color=COLOR_ACCENT,
        )
        self.btn_gerar.configure(state="normal")
        self.btn_iniciar.configure(state="normal")  # pode estudar sem áudio
        self.btn_anki.configure(state="normal")
        self.btn_pdf.configure(state="normal")
        self._status("Quiz carregado. Você já pode iniciar o estudo, "
                     "exportar para Anki ou gerar PDF.")

    # -------- Editor inline --------
    def _marcar_modificado(self):
        if not self._modificado:
            self._modificado = True
            self.lbl_modificado.configure(
                text="● modificado — clique em Atualizar"
            )

    def _nome_atual(self) -> str:
        """Nome do baralho que o usuário editou (cai pra self.nome_quiz)."""
        if hasattr(self, "entry_nome_quiz"):
            n = self.entry_nome_quiz.get().strip()
            if n:
                return n
        return self.nome_quiz or "BizuDeck"

    def _validar_editor(self):
        """Reroda o parser sobre o texto atual do editor."""
        conteudo = self.txt_preview.get("1.0", "end")
        blocos = parse_quiz(conteudo)
        if not blocos:
            messagebox.showerror(
                "Nada para validar",
                "Nenhuma questão reconhecida no editor.\n\n"
                "Cada bloco precisa ter 'P>' e ('R>' ou '*>'), "
                "separados por linha em branco.",
            )
            return

        abertas = sum(1 for b in blocos if b["tipo"] == "aberta")
        multiplas = sum(1 for b in blocos if b["tipo"] == "multipla")

        # Detectar problemas
        avisos = []
        for i, b in enumerate(blocos, start=1):
            if b["tipo"] == "multipla":
                if not b.get("letra_correta"):
                    avisos.append(f"#{i}: múltipla sem letra correta (*>)")
                elif len(b.get("opcoes", [])) < 2:
                    avisos.append(f"#{i}: múltipla com menos de 2 opções")
            else:
                if not b.get("resposta_correta"):
                    avisos.append(f"#{i}: pergunta aberta sem resposta (R>)")

        # Aplica o novo conteúdo
        self.quiz_blocos = blocos
        # Invalida áudios — texto pode ter mudado
        if self._modificado:
            self.quiz_audios_pergunta = {}
            self.quiz_audios_resposta = {}

        self._modificado = False
        self.lbl_modificado.configure(text="")
        self.lbl_resumo.configure(
            text=f"{len(blocos)} questões  •  {abertas} abertas  •  "
                 f"{multiplas} múltipla escolha",
            text_color=COLOR_ACCENT,
        )
        self.btn_gerar.configure(state="normal")
        self.btn_iniciar.configure(state="normal")
        self.btn_anki.configure(state="normal")
        self.btn_pdf.configure(state="normal")

        if avisos:
            msg = "Quiz atualizado, mas com avisos:\n\n" + "\n".join(avisos)
            messagebox.showwarning("Avisos", msg)
            self._status(f"Atualizado com {len(avisos)} aviso(s).")
        else:
            self._status(f"Quiz atualizado: {len(blocos)} questões.")

    def _adicionar_questao_template(self):
        """Insere um template ao final do editor."""
        # Pergunta: qual tipo?
        win = ctk.CTkToplevel(self)
        win.title("Adicionar questão")
        win.geometry("400x180")
        win.configure(fg_color=COLOR_BG)
        win.transient(self)
        win.grab_set()

        ctk.CTkLabel(
            win, text="Que tipo de questão?",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(pady=(24, 16))

        def insere(tipo: str):
            if tipo == "aberta":
                tpl = "\n\nP> \nR> "
            else:
                tpl = "\n\nP> \nA) \nB) \nC) \nD) \n*> A"
            self.txt_preview.insert("end", tpl)
            self.txt_preview.see("end")
            self._marcar_modificado()
            # posiciona o cursor logo após "P> " do template inserido
            try:
                idx = self.txt_preview.search("P> ", "end-100c", "end")
                if idx:
                    self.txt_preview.mark_set("insert", f"{idx}+3c")
                    self.txt_preview.focus_set()
            except Exception:
                pass
            win.destroy()

        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(pady=8)
        ctk.CTkButton(
            botoes, text="Aberta (P>/R>)",
            font=FONT_BTN, height=42, width=160,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207",
            command=lambda: insere("aberta"),
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            botoes, text="Múltipla escolha",
            font=FONT_BTN, height=42, width=160,
            fg_color="transparent", border_width=1, border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            command=lambda: insere("multipla"),
        ).pack(side="left", padx=6)

    def _salvar_quiz_como(self):
        """Salva o texto do editor em um .txt."""
        conteudo = self.txt_preview.get("1.0", "end").rstrip() + "\n"
        if not conteudo.strip():
            messagebox.showinfo("Vazio", "Não há nada para salvar.")
            return
        nome_sugerido = safe_name(self._nome_atual()) + ".txt"
        dest = filedialog.asksaveasfilename(
            title="Salvar quiz como…",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
            initialfile=nome_sugerido,
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(conteudo)
            self._status(f"Quiz salvo: {os.path.basename(dest)}")
            log.info(f"Quiz salvo manualmente: {dest}")
            if messagebox.askyesno(
                "Salvo",
                f"Quiz salvo em:\n{dest}\n\nAbrir a pasta?",
            ):
                try:
                    os.startfile(os.path.dirname(dest))
                except Exception:
                    pass
        except Exception as e:
            log.exception("Erro ao salvar quiz")
            messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    def _novo_quiz_em_branco(self):
        """Limpa tudo e injeta um template para começar do zero."""
        if self._modificado or self.quiz_blocos:
            if not messagebox.askyesno(
                "Novo quiz",
                "Isso vai apagar o conteúdo atual do editor "
                "(o arquivo original em disco não é afetado).\n\n"
                "Continuar?",
            ):
                return

        template = (
            "P> Sua primeira pergunta aberta vai aqui?\n"
            "R> Resposta esperada.\n"
            "\n"
            "P> Sua primeira pergunta de múltipla escolha?\n"
            "A) Primeira opção\n"
            "B) Segunda opção\n"
            "C) Terceira opção\n"
            "D) Quarta opção\n"
            "*> B\n"
        )
        self.txt_preview.delete("1.0", "end")
        self.txt_preview.insert("1.0", template)
        self.entry_nome_quiz.delete(0, "end")
        self.entry_nome_quiz.insert(0, "Novo_Quiz")
        self.nome_quiz = "Novo_Quiz"
        self.quiz_blocos = []
        self.quiz_audios_pergunta = {}
        self.quiz_audios_resposta = {}
        self._modificado = True
        self.lbl_modificado.configure(text="● novo — clique em Atualizar")
        self.lbl_resumo.configure(
            text="Editor em branco. Edite e clique em Atualizar.",
            text_color=COLOR_TEXT_DIM,
        )
        self.btn_gerar.configure(state="disabled")
        self.btn_iniciar.configure(state="disabled")
        self.btn_anki.configure(state="disabled")
        self.btn_pdf.configure(state="disabled")
        self._status("Editor em branco — preencha e clique em Atualizar.")

    def _diretorio_app(self) -> str:
        """Pasta onde o .exe (ou .py em dev) está."""
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.abspath(".")

    def _candidatos_pasta_exemplos(self) -> list[str]:
        """Lista de pastas candidatas onde os exemplos podem viver,
        em ordem de preferência."""
        candidatos = []
        # 1. Ao lado do .exe / .py
        candidatos.append(os.path.join(self._diretorio_app(), "exemplos"))
        # 2. Documentos do usuário
        try:
            docs = os.path.join(
                os.path.expanduser("~"), "Documents", "BizuDeck", "exemplos",
            )
            candidatos.append(docs)
        except Exception:
            pass
        # 3. CWD legado
        candidatos.append(os.path.abspath("exemplos"))
        return candidatos

    def _garantir_pasta_exemplos(self) -> str | None:
        """Garante que a pasta 'exemplos/' está acessível ao usuário,
        copiando do bundle se necessário. Tenta vários caminhos."""
        # 1. Já existe alguma com conteúdo?
        for pasta in self._candidatos_pasta_exemplos():
            try:
                if os.path.isdir(pasta) and os.listdir(pasta):
                    return pasta
            except Exception:
                continue

        # 2. Tenta extrair do bundle pra cada candidato em ordem
        pasta_bundle = resource_path("exemplos")
        if not os.path.isdir(pasta_bundle):
            log.warning("Pasta de exemplos não encontrada no bundle")
            return None

        import shutil
        for pasta in self._candidatos_pasta_exemplos():
            try:
                os.makedirs(pasta, exist_ok=True)
                arquivos_copiados = 0
                for nome in os.listdir(pasta_bundle):
                    src = os.path.join(pasta_bundle, nome)
                    dst = os.path.join(pasta, nome)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        arquivos_copiados += 1
                log.info(
                    f"Exemplos extraídos para {pasta} "
                    f"({arquivos_copiados} arquivos novos)"
                )
                return pasta
            except (PermissionError, OSError) as e:
                log.warning(f"Sem permissão em {pasta}: {e}")
                continue
        return None

    def _abrir_exemplos(self):
        pasta = self._garantir_pasta_exemplos()
        if not pasta:
            messagebox.showerror(
                "Exemplos",
                "Não foi possível localizar nem extrair a pasta de "
                "exemplos. Reinstale o app ou baixe o .exe novamente.",
            )
            return
        try:
            os.startfile(pasta)
        except Exception as e:
            messagebox.showerror(
                "Erro ao abrir",
                f"Não consegui abrir a pasta no Explorer:\n{pasta}\n\n{e}",
            )

    def _mostrar_prompt_ia(self):
        win = ctk.CTkToplevel(self)
        win.title("Prompt para IA externa")
        win.geometry("760x600")
        win.configure(fg_color=COLOR_BG)
        win.transient(self)

        ctk.CTkLabel(
            win, text="Prompt para ChatGPT / Gemini / Claude",
            font=FONT_TITLE, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=20, pady=(20, 4))
        ctk.CTkLabel(
            win,
            text="1. Copie esse prompt   2. Cole na IA   3. Substitua "
                 "[TEMA] e [CONTEÚDO]   4. Salve a saída como .txt e "
                 "importe aqui.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        txt = ctk.CTkTextbox(
            win, font=("Consolas", 11), fg_color=COLOR_CARD,
            border_color=COLOR_BORDER, border_width=1, wrap="word",
        )
        txt.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        txt.insert("1.0", PROMPT_IA_TEXTO)
        txt.configure(state="normal")

        botoes = ctk.CTkFrame(win, fg_color="transparent")
        botoes.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(
            botoes, text="📋  Copiar para área de transferência",
            font=FONT_BTN, height=40,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207",
            command=lambda: self._copiar(txt, win),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            botoes, text="Fechar", font=FONT_BTN, height=40, width=100,
            fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_TEXT,
            command=win.destroy,
        ).pack(side="right", padx=4)

    def _copiar(self, textbox, parent):
        conteudo = textbox.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(conteudo)
        messagebox.showinfo(
            "Copiado", "Prompt copiado para a área de transferência.",
            parent=parent,
        )

    def _gerar_audios_clicado(self):
        if not self.quiz_blocos:
            return
        self._aviso_modificado_se_necessario()
        self.nome_quiz = self._nome_atual()
        self.cancel_event.clear()
        self.btn_gerar.configure(state="disabled")
        self.btn_iniciar.configure(state="disabled")
        threading.Thread(target=self._gerar_audios_thread, daemon=True).start()

    def _aviso_modificado_se_necessario(self):
        """Mostra aviso se o editor foi mexido e ainda não foi validado."""
        if self._modificado:
            messagebox.showinfo(
                "Conteúdo modificado",
                "Você editou o conteúdo mas não clicou em "
                "✓ Atualizar / Validar. A operação vai usar a "
                "última versão validada.",
            )

    def _gerar_audios_thread(self):
        try:
            voz_pergunta = self.config_data["voice_pergunta"]
            voz_resposta = self.config_data["voice_resposta"]
            rate = format_rate(self.config_data["rate"])
            pasta = os.path.join(OUTPUT_DIR, safe_name(self.nome_quiz))
            os.makedirs(pasta, exist_ok=True)
            n_blocos = len(self.quiz_blocos)
            total = n_blocos * 2  # pergunta + resposta para cada bloco
            self.quiz_audios_pergunta = {}
            self.quiz_audios_resposta = {}
            done = 0

            async def pipeline():
                nonlocal done
                for i, bloco in enumerate(self.quiz_blocos):
                    # ----- Áudio da PERGUNTA -----
                    if self.cancel_event.is_set():
                        raise asyncio.CancelledError()
                    c_perg = os.path.join(pasta, f"{i:03}_pergunta.mp3")
                    await gerar_audio_async(
                        bloco["pergunta"], voz_pergunta, c_perg, rate,
                        self.cancel_event,
                    )
                    self.quiz_audios_pergunta[i] = c_perg
                    done += 1
                    self._set_progress(
                        done, total,
                        f"Pergunta {i + 1}/{n_blocos}",
                    )

                    # ----- Áudio da RESPOSTA -----
                    if self.cancel_event.is_set():
                        raise asyncio.CancelledError()
                    texto_resp = _texto_audio_resposta(bloco)
                    c_resp = os.path.join(pasta, f"{i:03}_resposta.mp3")
                    await gerar_audio_async(
                        texto_resp, voz_resposta, c_resp, rate,
                        self.cancel_event,
                    )
                    self.quiz_audios_resposta[i] = c_resp
                    done += 1
                    self._set_progress(
                        done, total,
                        f"Resposta {i + 1}/{n_blocos}",
                    )

            asyncio.run(pipeline())
            self._set_progress(total, total, "Áudios prontos!")
            log.info(f"Áudios gerados em {pasta} (perguntas + respostas)")
        except asyncio.CancelledError:
            self._status("Cancelado.")
        except Exception as e:
            log.exception("Erro ao gerar áudios")
            self._status(f"Erro: {e}")
            self.after(0, lambda: messagebox.showerror("Erro", str(e)))
        finally:
            self.after(0, lambda: self.btn_gerar.configure(state="normal"))
            self.after(0, lambda: self.btn_iniciar.configure(state="normal"))

    def _iniciar_estudo(self):
        if not self.quiz_blocos:
            messagebox.showinfo(
                "Sem quiz",
                "Importe um arquivo .txt antes de iniciar o estudo.",
            )
            return
        self._aviso_modificado_se_necessario()
        self.nome_quiz = self._nome_atual()
        self.idx_atual = 0
        self.acertos = 0
        self.parciais = 0
        self.erros = 0
        self._show_view("estudar")

    # -------- Exportações: Anki e PDF --------
    def _pasta_projeto(self) -> str:
        pasta = os.path.join(OUTPUT_DIR, safe_name(self.nome_quiz or "quiz"))
        os.makedirs(pasta, exist_ok=True)
        return pasta

    def _exportar_anki_clicado(self):
        if not self.quiz_blocos:
            return
        self._aviso_modificado_se_necessario()
        self.nome_quiz = self._nome_atual()
        tem_pergunta = bool(self.quiz_audios_pergunta)
        tem_resposta = bool(self.quiz_audios_resposta)
        if not (tem_pergunta and tem_resposta):
            faltando = []
            if not tem_pergunta:
                faltando.append("perguntas")
            if not tem_resposta:
                faltando.append("respostas")
            msg = (
                f"Áudios de {' e '.join(faltando)} ainda não foram "
                f"gerados. O baralho será criado sem esses áudios.\n\n"
                "Continuar mesmo assim?\n\n"
                "(Dica: clique em \"🎧 Gerar áudios das perguntas\" antes "
                "de exportar para ter áudio em frente e verso dos cards.)"
            )
            if not messagebox.askyesno("Sem áudio", msg):
                return
        threading.Thread(target=self._exportar_anki_thread,
                          daemon=True).start()

    def _exportar_anki_thread(self):
        try:
            self._status("Gerando baralho Anki…")
            pasta = self._pasta_projeto()
            autor = self.config_data.get("autor", AUTOR)
            out = exportar_apkg(
                self.quiz_blocos,
                self.quiz_audios_pergunta,
                self.quiz_audios_resposta,
                self.nome_quiz or "BizuDeck", pasta, autor,
            )
            log.info(f"Baralho Anki criado: {out}")
            self._status(f"Baralho criado: {os.path.basename(out)}")
            self.after(0, lambda: messagebox.showinfo(
                "Anki criado",
                f"Baralho salvo em:\n{os.path.abspath(out)}\n\n"
                "Para importar: abra o Anki, vá em Arquivo > Importar, "
                "selecione o .apkg.",
            ))
        except Exception as e:
            log.exception("Erro ao exportar Anki")
            self._status(f"Erro: {e}")
            self.after(0, lambda: messagebox.showerror(
                "Erro ao gerar Anki", str(e),
            ))

    def _exportar_pdf_clicado(self):
        if not self.quiz_blocos:
            return
        self._aviso_modificado_se_necessario()
        self.nome_quiz = self._nome_atual()
        threading.Thread(target=self._exportar_pdf_thread,
                          daemon=True).start()

    def _exportar_pdf_thread(self):
        try:
            self._status("Gerando PDF de estudo…")
            pasta = self._pasta_projeto()
            autor = self.config_data.get("autor", AUTOR)
            out = exportar_pdf(
                self.quiz_blocos, self.nome_quiz or "BizuDeck",
                pasta, autor,
            )
            log.info(f"PDF de estudo criado: {out}")
            self._status(f"PDF criado e aberto: {os.path.basename(out)}")
            # Abre o PDF automaticamente no leitor padrão
            try:
                os.startfile(os.path.abspath(out))
                log.info(f"PDF aberto no leitor padrão: {out}")
            except Exception as e:
                # Se falhar, mostra popup com caminho
                log.warning(f"Falha ao abrir PDF automaticamente: {e}")
                self.after(0, lambda: messagebox.showinfo(
                    "PDF criado",
                    f"PDF salvo em:\n{os.path.abspath(out)}\n\n"
                    f"Não consegui abrir automaticamente "
                    f"(nenhum leitor PDF associado?).",
                ))
        except Exception as e:
            log.exception("Erro ao exportar PDF")
            self._status(f"Erro: {e}")
            self.after(0, lambda: messagebox.showerror(
                "Erro ao gerar PDF", str(e),
            ))

    # -------- View: ESTUDAR --------
    def _build_view_estudar(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main, fg_color="transparent")

        # Cabeçalho com placar
        head = ctk.CTkFrame(view, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        self.lbl_titulo_estudo = ctk.CTkLabel(
            head, text="Estudo", font=FONT_TITLE, text_color=COLOR_TEXT,
        )
        self.lbl_titulo_estudo.pack(side="left")
        self.lbl_placar = ctk.CTkLabel(
            head, text="", font=("Segoe UI", 13), text_color=COLOR_TEXT_DIM,
        )
        self.lbl_placar.pack(side="right")

        self.lbl_progresso = ctk.CTkLabel(
            view, text="", font=FONT_LABEL, text_color=COLOR_ACCENT,
        )
        self.lbl_progresso.pack(anchor="w", pady=(0, 8))

        # Card da pergunta
        self.card_pergunta = self._card(view)
        self.card_pergunta.pack(fill="x", pady=8)
        self.lbl_pergunta = ctk.CTkLabel(
            self.card_pergunta, text="", font=FONT_QUESTION,
            text_color=COLOR_TEXT, wraplength=820, justify="left",
            anchor="w",
        )
        self.lbl_pergunta.pack(anchor="w", padx=22, pady=(18, 8), fill="x")
        botoes_audio = ctk.CTkFrame(self.card_pergunta, fg_color="transparent")
        botoes_audio.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(
            botoes_audio, text="🔊  Ouvir pergunta",
            font=("Segoe UI", 12), height=32, width=160,
            fg_color=COLOR_CARD_HOVER, hover_color=COLOR_BORDER,
            text_color=COLOR_TEXT,
            command=self._tocar_pergunta,
        ).pack(side="left", padx=4)

        # Container que muda conforme o tipo (aberta/múltipla)
        self.area_resposta = ctk.CTkFrame(view, fg_color="transparent")
        self.area_resposta.pack(fill="both", expand=True, pady=8)

        # Botões de navegação
        nav = ctk.CTkFrame(view, fg_color="transparent")
        nav.pack(fill="x", pady=(8, 0))
        self.btn_verificar = ctk.CTkButton(
            nav, text="Verificar resposta",
            font=FONT_BTN, height=42, width=200,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=10,
            command=self._verificar_resposta,
        )
        self.btn_verificar.pack(side="left", padx=4)
        self.btn_proxima = ctk.CTkButton(
            nav, text="Próxima  →",
            font=FONT_BTN, height=42, width=160,
            fg_color="transparent", border_width=1,
            border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            corner_radius=10,
            command=self._proxima_questao, state="disabled",
        )
        self.btn_proxima.pack(side="right", padx=4)

        return view

    def _renderizar_questao_atual(self):
        if not self.quiz_blocos:
            self.lbl_titulo_estudo.configure(text="Nenhum quiz carregado")
            self.lbl_progresso.configure(text="")
            self.lbl_placar.configure(text="")
            self.lbl_pergunta.configure(text="Importe um arquivo .txt na "
                                              "aba Criar Quiz.")
            for w in self.area_resposta.winfo_children():
                w.destroy()
            self.btn_verificar.configure(state="disabled")
            self.btn_proxima.configure(state="disabled")
            return

        total = len(self.quiz_blocos)
        if self.idx_atual >= total:
            self._mostrar_resultado_final()
            return

        bloco = self.quiz_blocos[self.idx_atual]
        self.lbl_titulo_estudo.configure(text=self.nome_quiz or "Estudo")
        self.lbl_progresso.configure(
            text=f"Questão {self.idx_atual + 1} de {total}  •  "
                 f"{bloco['tipo'].upper()}"
        )
        self.lbl_placar.configure(
            text=f"✓ {self.acertos}    ◐ {self.parciais}    ✗ {self.erros}",
            text_color=COLOR_TEXT_DIM,
        )
        self.lbl_pergunta.configure(text=bloco["pergunta"])

        for w in self.area_resposta.winfo_children():
            w.destroy()

        self._estado_atual = {
            "respondeu": False,
            "letra_escolhida": None,
            "feedback_label": None,
        }

        if bloco["tipo"] == "aberta":
            self._render_resposta_aberta(bloco)
        else:
            self._render_resposta_multipla(bloco)

        self.btn_verificar.configure(state="normal")
        self.btn_proxima.configure(state="disabled")

    def _render_resposta_aberta(self, bloco):
        card = self._card(self.area_resposta)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(
            card, text="Sua resposta", font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(14, 4))
        self.txt_resposta = ctk.CTkTextbox(
            card, font=FONT_INPUT, height=120,
            fg_color=COLOR_BG, border_color=COLOR_BORDER, border_width=1,
            wrap="word",
        )
        self.txt_resposta.pack(fill="x", padx=18, pady=(0, 10))
        self.txt_resposta.focus_set()

        self.lbl_feedback = ctk.CTkLabel(
            card, text="", font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
            wraplength=820, justify="left", anchor="w",
        )
        self.lbl_feedback.pack(anchor="w", padx=18, pady=(0, 12), fill="x")

    def _render_resposta_multipla(self, bloco):
        card = self._card(self.area_resposta)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(
            card, text="Escolha uma opção",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(14, 8))

        self._botoes_opcoes = []
        for opc in bloco.get("opcoes", []):
            b = ctk.CTkButton(
                card, text=f"{opc['letra']})  {opc['texto']}",
                font=FONT_INPUT, height=44, anchor="w",
                fg_color=COLOR_BG, hover_color=COLOR_CARD_HOVER,
                text_color=COLOR_TEXT, corner_radius=8,
                border_width=1, border_color=COLOR_BORDER,
                command=lambda letra=opc["letra"]: self._selecionar_opcao(letra),
            )
            b.pack(fill="x", padx=18, pady=4)
            self._botoes_opcoes.append((opc["letra"], b))

        self.lbl_feedback = ctk.CTkLabel(
            card, text="", font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
            wraplength=820, justify="left", anchor="w",
        )
        self.lbl_feedback.pack(anchor="w", padx=18, pady=(8, 12), fill="x")

    def _selecionar_opcao(self, letra: str):
        if self._estado_atual.get("respondeu"):
            return
        self._estado_atual["letra_escolhida"] = letra
        for l, b in self._botoes_opcoes:
            if l == letra:
                b.configure(fg_color=COLOR_ACCENT, text_color="#1a1207")
            else:
                b.configure(fg_color=COLOR_BG, text_color=COLOR_TEXT)

    def _tocar_pergunta(self):
        if self.idx_atual >= len(self.quiz_blocos):
            return
        caminho = self.quiz_audios_pergunta.get(self.idx_atual)
        if caminho and os.path.exists(caminho):
            self._tocar(caminho)
        else:
            # Gera on-demand se ainda não tem áudio
            threading.Thread(
                target=self._gerar_e_tocar_pergunta,
                args=(self.idx_atual,), daemon=True,
            ).start()

    def _gerar_e_tocar_pergunta(self, idx: int):
        try:
            bloco = self.quiz_blocos[idx]
            voz = self.config_data["voice_pergunta"]
            rate = format_rate(self.config_data["rate"])
            pasta = os.path.join(
                OUTPUT_DIR, safe_name(self.nome_quiz or "quiz")
            )
            os.makedirs(pasta, exist_ok=True)
            caminho = os.path.join(pasta, f"{idx:03}_pergunta.mp3")
            ev = threading.Event()
            asyncio.run(gerar_audio_async(
                bloco["pergunta"], voz, caminho, rate, ev, max_retries=2,
            ))
            self.quiz_audios_pergunta[idx] = caminho
            self._tocar(caminho)
        except Exception as e:
            log.warning(f"Falha ao gerar/tocar pergunta: {e}")

    def _tocar(self, caminho: str):
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            pygame.mixer.music.load(caminho)
            pygame.mixer.music.play()
        except Exception as e:
            log.warning(f"Falha ao tocar áudio: {e}")
            try:
                os.startfile(caminho)
            except Exception:
                pass

    def _verificar_resposta(self):
        if self._estado_atual.get("respondeu"):
            return
        bloco = self.quiz_blocos[self.idx_atual]

        if bloco["tipo"] == "aberta":
            resposta = self.txt_resposta.get("1.0", "end").strip()
            if not resposta:
                self.lbl_feedback.configure(
                    text="Digite sua resposta antes de verificar.",
                    text_color=COLOR_WARN,
                )
                return
            status, sim = avaliar_resposta(
                resposta, bloco["resposta_correta"]
            )
            self._aplicar_feedback_aberta(status, sim, bloco)
        else:
            letra = self._estado_atual.get("letra_escolhida")
            if not letra:
                self.lbl_feedback.configure(
                    text="Selecione uma opção antes de verificar.",
                    text_color=COLOR_WARN,
                )
                return
            correta = bloco.get("letra_correta", "")
            acertou = letra == correta
            self._aplicar_feedback_multipla(acertou, letra, bloco)

        self._estado_atual["respondeu"] = True
        self.btn_verificar.configure(state="disabled")
        self.btn_proxima.configure(state="normal")
        self.lbl_placar.configure(
            text=f"✓ {self.acertos}    ◐ {self.parciais}    ✗ {self.erros}"
        )

    def _aplicar_feedback_aberta(self, status: str, sim: float, bloco: dict):
        gabarito = bloco["resposta_correta"]
        pct = int(sim * 100)
        if status == "correto":
            self.acertos += 1
            cor = COLOR_SUCCESS
            icone = "✓"
            texto = (f"{icone}  Correto! ({pct}% de similaridade)\n\n"
                     f"Gabarito: {gabarito}")
        elif status == "parcial":
            self.parciais += 1
            cor = COLOR_WARN
            icone = "◐"
            texto = (f"{icone}  Parcial ({pct}%) — sua resposta está no "
                     f"caminho.\n\nGabarito: {gabarito}")
        else:
            self.erros += 1
            cor = COLOR_DANGER
            icone = "✗"
            texto = (f"{icone}  Distante ({pct}%) — revise o conceito.\n\n"
                     f"Gabarito: {gabarito}")
        self.lbl_feedback.configure(text=texto, text_color=cor)

    def _aplicar_feedback_multipla(self, acertou: bool, letra: str,
                                    bloco: dict):
        correta = bloco.get("letra_correta", "")
        gab_texto = bloco.get("resposta_correta", "")
        if acertou:
            self.acertos += 1
            self.lbl_feedback.configure(
                text=f"✓  Correto! Letra {correta}.\n{correta}) {gab_texto}",
                text_color=COLOR_SUCCESS,
            )
        else:
            self.erros += 1
            self.lbl_feedback.configure(
                text=f"✗  Você marcou {letra}. Correta: {correta}.\n"
                     f"{correta}) {gab_texto}",
                text_color=COLOR_DANGER,
            )
        # destaca botões
        for l, b in self._botoes_opcoes:
            if l == correta:
                b.configure(fg_color=COLOR_SUCCESS, text_color="#0f1f12")
            elif l == letra and not acertou:
                b.configure(fg_color=COLOR_DANGER, text_color="#1f0e0d")

    def _proxima_questao(self):
        self.idx_atual += 1
        self._renderizar_questao_atual()

    def _mostrar_resultado_final(self):
        total = len(self.quiz_blocos)
        respondidas = self.acertos + self.parciais + self.erros
        pct = int(((self.acertos + 0.5 * self.parciais) / total) * 100) if total else 0

        self.lbl_titulo_estudo.configure(text="Quiz concluído!")
        self.lbl_progresso.configure(
            text=f"{respondidas} de {total} questões respondidas",
            text_color=COLOR_ACCENT,
        )
        self.lbl_placar.configure(text="")
        self.lbl_pergunta.configure(
            text=f"Aproveitamento: {pct}%\n\n"
                 f"✓ {self.acertos} corretas    "
                 f"◐ {self.parciais} parciais    "
                 f"✗ {self.erros} erradas"
        )

        for w in self.area_resposta.winfo_children():
            w.destroy()
        card = self._card(self.area_resposta)
        card.pack(fill="x")
        botoes = ctk.CTkFrame(card, fg_color="transparent")
        botoes.pack(fill="x", padx=18, pady=18)
        ctk.CTkButton(
            botoes, text="🔄  Refazer este quiz", font=FONT_BTN, height=42,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207",
            command=self._refazer_quiz,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            botoes, text="◀  Voltar para Criar Quiz", font=FONT_BTN, height=42,
            fg_color="transparent", border_width=1, border_color=COLOR_BORDER,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_TEXT,
            command=lambda: self._show_view("criar"),
        ).pack(side="left", padx=4)

        self.btn_verificar.configure(state="disabled")
        self.btn_proxima.configure(state="disabled")

    def _refazer_quiz(self):
        self.idx_atual = 0
        self.acertos = 0
        self.parciais = 0
        self.erros = 0
        self._renderizar_questao_atual()

    # -------- View: PODCAST --------
    def _build_view_podcast(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main, fg_color="transparent")

        # Cabeçalho
        ctk.CTkLabel(
            view, text="🎙  Modo Podcast",
            font=FONT_TITLE, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            view,
            text=(
                "Cole ou edite um script de podcast no formato E>/C> e gere "
                "um único MP3 com duas vozes alternadas. Ótimo pra ouvir "
                "revisão durante a caminhada, no carro etc."
            ),
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
            wraplength=820, justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Formato (caixinha de ajuda colapsável simples)
        ajuda = ctk.CTkFrame(view, fg_color=COLOR_CARD, corner_radius=10)
        ajuda.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            ajuda,
            text=(
                "Formato:  T> Título   |   TEMA> Tema do episódio   |   "
                "E> Fala do Entrevistador   |   C> Fala do Convidado"
            ),
            font=("Consolas", 11), text_color=COLOR_ACCENT,
            wraplength=820, justify="left",
        ).pack(anchor="w", padx=12, pady=10)

        # Editor de texto
        editor_frame = ctk.CTkFrame(view, fg_color=COLOR_CARD, corner_radius=10)
        editor_frame.pack(fill="both", expand=True, pady=(0, 12))
        ctk.CTkLabel(
            editor_frame, text="Script do podcast",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 4))
        self.pod_textbox = ctk.CTkTextbox(
            editor_frame, font=("Consolas", 12),
            fg_color="#0f0d0a", text_color=COLOR_TEXT,
            border_width=1, border_color=COLOR_BORDER,
            wrap="word",
        )
        self.pod_textbox.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        # Placeholder de exemplo
        self.pod_textbox.insert("1.0", (
            "T> Engenharia de Software — Episódio 1\n"
            "TEMA> Fundamentos e camadas\n\n"
            "E> Bom dia! Hoje vamos revisar fundamentos de Engenharia de Software.\n"
            "C> Tema clássico, vamos lá.\n"
            "E> Primeira pergunta: quais são as quatro camadas da Engenharia de Software?\n"
            "C> Qualidade, processo, métodos e ferramentas.\n"
            "E> E qual é a camada base que sustenta tudo?\n"
            "C> A camada de processo.\n"
        ))

        # Linha de controles: vozes
        linha_voz = ctk.CTkFrame(view, fg_color="transparent")
        linha_voz.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            linha_voz, text="Voz Entrevistador (E):",
            font=FONT_LABEL, text_color=COLOR_TEXT,
        ).pack(side="left", padx=(0, 6))
        self.pod_voz_e = ctk.CTkOptionMenu(
            linha_voz, values=VOICES_PT,
            font=FONT_INPUT, width=240,
            fg_color=COLOR_CARD, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
        )
        self.pod_voz_e.set(self.config_data.get(
            "voice_pergunta", "pt-BR-FranciscaNeural"
        ))
        self.pod_voz_e.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            linha_voz, text="Voz Convidado (C):",
            font=FONT_LABEL, text_color=COLOR_TEXT,
        ).pack(side="left", padx=(0, 6))
        self.pod_voz_c = ctk.CTkOptionMenu(
            linha_voz, values=VOICES_PT,
            font=FONT_INPUT, width=240,
            fg_color=COLOR_CARD, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
        )
        self.pod_voz_c.set(self.config_data.get(
            "voice_resposta", "pt-BR-AntonioNeural"
        ))
        self.pod_voz_c.pack(side="left")

        # Linha de botões
        linha_btn = ctk.CTkFrame(view, fg_color="transparent")
        linha_btn.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            linha_btn, text="📂 Importar TXT", font=FONT_BTN, width=140,
            fg_color=COLOR_CARD, hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT, command=self._pod_importar_txt,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            linha_btn, text="💾 Salvar TXT", font=FONT_BTN, width=140,
            fg_color=COLOR_CARD, hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT, command=self._pod_salvar_txt,
        ).pack(side="left", padx=(0, 8))

        self.pod_btn_gerar = ctk.CTkButton(
            linha_btn, text="🎙 Gerar Áudio Único", font=FONT_BTN, width=200,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color=COLOR_BG, command=self._pod_gerar_clicado,
        )
        self.pod_btn_gerar.pack(side="left", padx=(0, 8))

        self.pod_btn_play = ctk.CTkButton(
            linha_btn, text="▶ Reproduzir", font=FONT_BTN, width=130,
            fg_color=COLOR_SUCCESS, hover_color="#16a34a",
            text_color=COLOR_BG, command=self._pod_reproduzir,
            state="disabled",
        )
        self.pod_btn_play.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            linha_btn, text="⏹ Parar", font=FONT_BTN, width=100,
            fg_color=COLOR_DANGER, hover_color="#c2392f",
            text_color=COLOR_BG, command=self._pod_parar,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            linha_btn, text="📁 Abrir Pasta", font=FONT_BTN, width=130,
            fg_color=COLOR_CARD, hover_color=COLOR_CARD_HOVER,
            text_color=COLOR_TEXT, command=self._pod_abrir_pasta,
        ).pack(side="left")

        # Status + progresso
        self.pod_status = ctk.CTkLabel(
            view, text="Pronto. Edite o script e clique em Gerar Áudio Único.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM, anchor="w",
        )
        self.pod_status.pack(fill="x", pady=(0, 4))
        self.pod_progress = ctk.CTkProgressBar(
            view, fg_color=COLOR_CARD, progress_color=COLOR_ACCENT, height=8,
        )
        self.pod_progress.set(0)
        self.pod_progress.pack(fill="x")

        # Estado do podcast
        self.pod_arquivo_gerado: str | None = None
        self.pod_cancel = threading.Event()

        return view

    # -------- Handlers PODCAST --------
    def _pod_importar_txt(self):
        path = filedialog.askopenfilename(
            title="Importar script de podcast",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                conteudo = f.read()
            self.pod_textbox.delete("1.0", "end")
            self.pod_textbox.insert("1.0", conteudo)
            self.pod_status.configure(
                text=f"📂 Importado: {os.path.basename(path)}"
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao importar: {e}")

    def _pod_salvar_txt(self):
        conteudo = self.pod_textbox.get("1.0", "end").strip()
        if not conteudo:
            messagebox.showwarning("Vazio", "Editor está vazio.")
            return
        path = filedialog.asksaveasfilename(
            title="Salvar script de podcast",
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(conteudo)
            self.pod_status.configure(
                text=f"💾 Salvo: {os.path.basename(path)}"
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar: {e}")

    def _pod_gerar_clicado(self):
        conteudo = self.pod_textbox.get("1.0", "end").strip()
        if not conteudo:
            messagebox.showwarning("Vazio", "Cole ou edite um script primeiro.")
            return
        try:
            pc = podcast_mod.parse_podcast(conteudo)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao parsear script: {e}")
            return
        if not pc.falas:
            messagebox.showwarning(
                "Sem falas",
                "Nenhuma fala encontrada. Use E> e C> nas linhas.",
            )
            return

        # Nome do arquivo: do título do podcast ou timestamp
        nome = safe_name(pc.titulo) if pc.titulo else f"podcast_{int(time.time())}"
        pasta = os.path.join(OUTPUT_DIR, nome)
        os.makedirs(pasta, exist_ok=True)
        saida = os.path.join(pasta, f"{nome}.mp3")

        self.pod_btn_gerar.configure(state="disabled", text="🎙 Gerando...")
        self.pod_btn_play.configure(state="disabled")
        self.pod_progress.set(0)
        self.pod_cancel.clear()

        threading.Thread(
            target=self._pod_gerar_thread,
            args=(pc, saida),
            daemon=True,
        ).start()

    def _pod_gerar_thread(self, pc, saida: str):
        def progresso(atual, total, msg):
            frac = atual / total if total else 0
            self.after(0, lambda: self.pod_progress.set(frac))
            self.after(0, lambda m=msg: self.pod_status.configure(text=m))

        try:
            rate = format_rate(self.config_data.get("rate", -10))
            voz_e = self.pod_voz_e.get()
            voz_c = self.pod_voz_c.get()
            podcast_mod.gerar_podcast_sync(
                pc, voz_e, voz_c, rate, saida,
                self.pod_cancel, progresso,
            )
            self.pod_arquivo_gerado = saida
            duracao = podcast_mod.estimar_duracao_segundos(pc)
            mins = int(duracao // 60)
            secs = int(duracao % 60)
            self.after(0, lambda: self.pod_status.configure(
                text=(
                    f"✓ Pronto! {len(pc.falas)} falas, ~{mins}:{secs:02d} min. "
                    f"Salvo em: {saida}"
                )
            ))
            self.after(0, lambda: self.pod_btn_play.configure(state="normal"))
        except Exception as e:
            log.exception("Falha ao gerar podcast")
            self.after(0, lambda err=str(e): messagebox.showerror(
                "Erro", f"Falha ao gerar: {err}"
            ))
            self.after(0, lambda: self.pod_status.configure(
                text="❌ Falha ao gerar áudio."
            ))
        finally:
            self.after(0, lambda: self.pod_btn_gerar.configure(
                state="normal", text="🎙 Gerar Áudio Único"
            ))

    def _pod_reproduzir(self):
        if not self.pod_arquivo_gerado or not os.path.exists(
            self.pod_arquivo_gerado
        ):
            messagebox.showwarning("Sem áudio", "Gere o áudio antes.")
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            pygame.mixer.music.load(self.pod_arquivo_gerado)
            pygame.mixer.music.play()
            self.pod_status.configure(text="▶ Reproduzindo...")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao reproduzir: {e}")

    def _pod_parar(self):
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.pod_cancel.set()
        self.pod_status.configure(text="⏹ Parado.")

    def _pod_abrir_pasta(self):
        path = (
            os.path.dirname(self.pod_arquivo_gerado)
            if self.pod_arquivo_gerado
            else OUTPUT_DIR
        )
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        try:
            os.startfile(path)  # Windows
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao abrir pasta: {e}")

    # -------- View: CONFIG --------
    def _build_view_config(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main, fg_color="transparent")
        ctk.CTkLabel(
            view, text="Configurações", font=FONT_TITLE, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            view, text="Voz, velocidade e modo de feedback.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, 14))

        card = self._card(view)
        card.pack(fill="x", pady=8)

        ctk.CTkLabel(
            card, text="🎤  Voz da PERGUNTA",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            card,
            text="Voz que vai ler cada pergunta (frente do card Anki).",
            font=("Segoe UI", 11), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=18, pady=(0, 6))
        self.combo_voz_pergunta = ctk.CTkOptionMenu(
            card, values=VOICES_PT, font=FONT_INPUT, height=36,
            fg_color=COLOR_BG, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, dropdown_fg_color=COLOR_CARD,
            command=lambda v: self._on_voz_selecionada("pergunta", v),
        )
        self.combo_voz_pergunta.set(self.config_data["voice_pergunta"])
        self.combo_voz_pergunta.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            card, text="🔊  Voz da RESPOSTA",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(6, 4))
        ctk.CTkLabel(
            card,
            text="Voz que vai ler cada resposta (verso do card Anki). "
                 "Use uma voz diferente da pergunta pra dar contraste.",
            font=("Segoe UI", 11), text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 6))
        self.combo_voz_resposta = ctk.CTkOptionMenu(
            card, values=VOICES_PT, font=FONT_INPUT, height=36,
            fg_color=COLOR_BG, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, dropdown_fg_color=COLOR_CARD,
            command=lambda v: self._on_voz_selecionada("resposta", v),
        )
        self.combo_voz_resposta.set(self.config_data["voice_resposta"])
        self.combo_voz_resposta.pack(fill="x", padx=18, pady=(0, 14))

        velo_row = ctk.CTkFrame(card, fg_color="transparent")
        velo_row.pack(fill="x", padx=18, pady=(6, 18))
        ctk.CTkLabel(
            velo_row, text="Velocidade", font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(side="left")
        self.lbl_velo = ctk.CTkLabel(
            velo_row, text=format_rate(self.config_data["rate"]),
            font=FONT_H2, text_color=COLOR_ACCENT,
        )
        self.lbl_velo.pack(side="right")
        self.slider_velo = ctk.CTkSlider(
            card, from_=-50, to=50, number_of_steps=20,
            progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER,
            command=self._on_velo_change,
        )
        self.slider_velo.set(self.config_data["rate"])
        self.slider_velo.pack(fill="x", padx=18, pady=(0, 18))

        # Modo de feedback
        card_modo = self._card(view)
        card_modo.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card_modo, text="Modo de feedback (perguntas abertas)",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            card_modo,
            text="Como o app julga a resposta digitada nas questões "
                 "abertas.",
            font=("Segoe UI", 11), text_color=COLOR_TEXT_DIM,
            wraplength=720, justify="left",
        ).pack(anchor="w", padx=18, pady=(0, 10))
        self.combo_modo = ctk.CTkOptionMenu(
            card_modo,
            values=["relaxado (similaridade %) ",
                    "manual (só mostra gabarito)"],
            font=FONT_INPUT, height=36,
            fg_color=COLOR_BG, button_color=COLOR_ACCENT,
            button_hover_color=COLOR_ACCENT_HOVER, dropdown_fg_color=COLOR_CARD,
            command=lambda v: self._salvar_config(),
        )
        modo_atual = self.config_data.get("modo_feedback", "relaxado")
        if modo_atual == "manual":
            self.combo_modo.set("manual (só mostra gabarito)")
        else:
            self.combo_modo.set("relaxado (similaridade %) ")
        self.combo_modo.pack(fill="x", padx=18, pady=(0, 18))

        return view

    def _on_velo_change(self, val):
        self.lbl_velo.configure(text=format_rate(int(val)))
        self._salvar_config()

    def _salvar_config(self):
        self.config_data["voice_pergunta"] = self.combo_voz_pergunta.get()
        self.config_data["voice_resposta"] = self.combo_voz_resposta.get()
        self.config_data["rate"] = int(self.slider_velo.get())
        self.config_data["modo_feedback"] = (
            "manual" if "manual" in self.combo_modo.get() else "relaxado"
        )
        save_config(self.config_data)

    def _on_voz_selecionada(self, tipo: str, voz: str):
        """tipo = 'pergunta' ou 'resposta' — toca prévia adequada."""
        self._salvar_config()
        self._preview_voz_selecionada(tipo, voz)

    def _preview_voz_selecionada(self, tipo: str, voz: str):
        if tipo == "pergunta":
            texto = ("Olá, eu serei a voz das perguntas. "
                     "Vamos começar quando você estiver pronto.")
        else:
            texto = ("Olá, eu serei a voz das respostas. "
                     "A resposta é essa que acabou de ouvir.")
        rate = format_rate(self.config_data["rate"])
        os.makedirs(LOGS_DIR, exist_ok=True)
        ts = int(datetime.now().timestamp() * 1000)
        out = os.path.join(LOGS_DIR, f"_preview_voz_{ts}.mp3")

        def worker():
            try:
                try:
                    if pygame.mixer.get_init() is not None:
                        pygame.mixer.music.stop()
                        try:
                            pygame.mixer.music.unload()
                        except Exception:
                            pass
                except Exception:
                    pass
                ev = threading.Event()
                asyncio.run(gerar_audio_async(
                    texto, voz, out, rate, ev, max_retries=2,
                ))
                self._tocar(out)
                self._limpar_previews_antigos(out)
            except Exception as e:
                log.warning(f"Falha na prévia: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _limpar_previews_antigos(self, manter: str):
        try:
            for nome in os.listdir(LOGS_DIR):
                if not nome.startswith("_preview_") or not nome.endswith(".mp3"):
                    continue
                caminho = os.path.join(LOGS_DIR, nome)
                if os.path.abspath(caminho) == os.path.abspath(manter):
                    continue
                try:
                    os.remove(caminho)
                except OSError:
                    pass
        except Exception:
            pass

    # -------- View: SOBRE --------
    def _build_view_sobre(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main, fg_color="transparent")
        ctk.CTkLabel(
            view, text="Sobre", font=FONT_TITLE, text_color=COLOR_TEXT,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            view, text="Informações do aplicativo e do canal.",
            font=FONT_LABEL, text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", pady=(0, 14))

        card = self._card(view)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            card, text=f"{APP_NOME} — Provas & Concursos",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            card,
            text="• Quiz interativo de Perguntas e Respostas (abertas e "
                 "múltipla escolha)\n"
                 "• Áudio das perguntas com Edge TTS em português\n"
                 "• Comparação relaxada de resposta + gabarito visível\n"
                 "• Não requer IA dentro do app (ela só gera o arquivo "
                 ".txt do quiz)\n\n"
                 f"Logs:  {os.path.abspath(os.path.join(LOGS_DIR, 'quiz.log'))}\n"
                 f"Saída: {os.path.abspath(OUTPUT_DIR)}",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            justify="left", anchor="w",
        ).pack(anchor="w", padx=18, pady=(0, 16))

        # Card: Manual do usuário
        manual_card = self._card(view)
        manual_card.pack(fill="x", pady=8)
        topo_manual = ctk.CTkFrame(manual_card, fg_color="transparent")
        topo_manual.pack(fill="x", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            topo_manual, text="📖", font=("Segoe UI", 26),
            text_color=COLOR_ACCENT,
        ).pack(side="left", padx=(0, 12))
        info_manual = ctk.CTkFrame(topo_manual, fg_color="transparent")
        info_manual.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            info_manual, text="Manual do Usuário",
            font=("Segoe UI Semibold", 17), text_color=COLOR_TEXT, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            info_manual, text="Guia completo em PDF — 11 seções + FAQ",
            font=("Segoe UI", 11), text_color=COLOR_ACCENT, anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            manual_card,
            text="Como gerar perguntas com IA, formato do arquivo, "
                 "como estudar, exportação para Anki, PDF de estudo, "
                 "configurações e perguntas frequentes.",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            justify="left", wraplength=760, anchor="w",
        ).pack(anchor="w", padx=18, pady=(8, 12))
        botoes_manual = ctk.CTkFrame(manual_card, fg_color="transparent")
        botoes_manual.pack(fill="x", padx=14, pady=(0, 16))
        ctk.CTkButton(
            botoes_manual, text="📖  Abrir Manual (PDF)",
            font=FONT_BTN, height=42, width=200,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=10,
            command=self._abrir_manual,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            botoes_manual, text="💾  Salvar Manual como…",
            font=FONT_BTN, height=42, width=200,
            fg_color="transparent", border_width=1,
            border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            corner_radius=10,
            command=self._salvar_manual,
        ).pack(side="left", padx=4)

        canal = self._card(view)
        canal.pack(fill="x", pady=8)
        ctk.CTkLabel(
            canal, text="Canal do desenvolvedor",
            font=FONT_H2, text_color=COLOR_TEXT,
        ).pack(anchor="w", padx=18, pady=(18, 6))
        ctk.CTkLabel(
            canal, text=AUTOR,
            font=("Segoe UI Semibold", 20), text_color=COLOR_ACCENT,
        ).pack(anchor="w", padx=18, pady=(2, 2))
        ctk.CTkLabel(
            canal, text=CANAL_URL,
            font=("Segoe UI", 12), text_color=COLOR_TEXT_DIM,
        ).pack(anchor="w", padx=18, pady=(0, 12))
        botoes = ctk.CTkFrame(canal, fg_color="transparent")
        botoes.pack(fill="x", padx=14, pady=(0, 16))
        ctk.CTkButton(
            botoes, text="▶  Abrir canal no YouTube",
            font=FONT_BTN, height=42,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#1a1207", corner_radius=10,
            command=lambda: webbrowser.open(CANAL_URL),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            botoes, text="🔔  Inscrever-se",
            font=FONT_BTN, height=42,
            fg_color="transparent", border_width=1, border_color=COLOR_ACCENT,
            hover_color=COLOR_CARD_HOVER, text_color=COLOR_ACCENT,
            corner_radius=10,
            command=lambda: webbrowser.open(
                CANAL_URL + "?sub_confirmation=1"
            ),
        ).pack(side="left", padx=4)
        return view

    # -------- Manual --------
    def _caminho_manual(self) -> str:
        return resource_path("assets/manual/Manual_BizuDeck.pdf")

    def _abrir_manual(self):
        caminho = self._caminho_manual()
        if not os.path.isfile(caminho):
            messagebox.showerror(
                "Manual não encontrado",
                f"O arquivo do manual não foi encontrado:\n{caminho}",
            )
            return
        try:
            os.startfile(caminho)
        except Exception as e:
            log.warning(f"Falha ao abrir manual: {e}")
            messagebox.showerror("Erro", f"Não foi possível abrir:\n{e}")

    def _salvar_manual(self):
        src = self._caminho_manual()
        if not os.path.isfile(src):
            messagebox.showerror(
                "Manual não encontrado",
                f"O arquivo do manual não foi encontrado:\n{src}",
            )
            return
        dest = filedialog.asksaveasfilename(
            title="Salvar Manual como…",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="Manual_BizuDeck.pdf",
        )
        if not dest:
            return
        try:
            import shutil
            shutil.copy2(src, dest)
            if messagebox.askyesno(
                "Salvo",
                f"Manual salvo em:\n{dest}\n\nAbrir agora?",
            ):
                try:
                    os.startfile(dest)
                except Exception:
                    pass
        except Exception as e:
            log.exception("Erro ao salvar manual")
            messagebox.showerror("Erro", f"Não foi possível salvar:\n{e}")

    # -------- UI thread-safe helpers --------
    def _set_progress(self, done: int, total: int, texto: str):
        pct = done / total if total else 0
        self.after(0, lambda: self.progress.set(pct))
        self.after(0, lambda: self.lbl_status.configure(
            text=f"{texto}  ({int(pct * 100)}%)", text_color=COLOR_TEXT,
        ))

    def _status(self, texto: str):
        self.after(0, lambda: self.lbl_status.configure(
            text=texto, text_color=COLOR_TEXT_DIM,
        ))


# =========================
# PROMPT IA (texto completo do PROMPT_IA.md)
# =========================
PROMPT_IA_TEXTO = """\
Gere um quiz em português brasileiro no formato abaixo, sobre o TEMA
(e CONTEÚDO opcional) que vou passar.

FORMATO — cada questão é um bloco separado por linha em branco:

  P> Pergunta?
  R> Resposta esperada.

  P> Pergunta?
  A) Opção A
  B) Opção B
  C) Opção C
  D) Opção D
  *> B

REGRAS:
- 15 questões, misturando os dois tipos.
- Perguntas curtas e diretas; respostas abertas de 1-2 frases.
- Distratores plausíveis na múltipla escolha.
- Apenas os blocos no resultado. Sem Markdown, sem JSON, sem numeração, sem comentários.

TEMA: [ex: Direito Constitucional · Termodinâmica · Revolução Francesa · Verb to be · Anatomia humana]

CONTEÚDO (opcional): [cole resumo, capítulo, slides, lista de tópicos — ou deixe vazio]
"""


if __name__ == "__main__":
    try:
        app = QuizApp()
        app.mainloop()
    except Exception:
        log.exception("Erro fatal")
        raise
