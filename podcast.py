"""
Módulo Podcast do BizuDeck.

Formato do .txt:
    T> Título do episódio (opcional, fica no metadado e abertura)
    TEMA> Tema (opcional, lido na abertura)

    E> Fala do Entrevistador
    C> Fala do Convidado
    E> Próxima fala do entrevistador
    C> Resposta do convidado
    ...

Regras:
- Linhas em branco são ignoradas (servem só para legibilidade).
- Cada linha começando com E>, C>, T>, TEMA> é uma fala/metadado.
- T> e TEMA> só são considerados na primeira ocorrência.
- Se a primeira linha falada não for E>, o gerador injeta uma abertura
  automática "Olá, bem-vindos a mais um episódio..." se houver T>/TEMA>.

Saída: 1 arquivo MP3 único, concatenando as falas via Edge-TTS.
Duas vozes (Entrevistador e Convidado) tornam a escuta dinâmica.

Sem dependências extras — concatenação binária de MP3 funciona porque
Edge-TTS emite MP3 CBR com frames padronizados.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Callable

import edge_tts

log = logging.getLogger("bizudeck.podcast")


# =========================
# PARSER
# =========================
@dataclass
class Fala:
    """Uma fala do podcast."""
    locutor: str  # "E" (entrevistador) ou "C" (convidado)
    texto: str


@dataclass
class Podcast:
    titulo: str = ""
    tema: str = ""
    falas: list[Fala] = field(default_factory=list)

    def total_falas(self) -> int:
        return len(self.falas)


# Regex de prefixos. Aceita maiúsculas, minúsculas, com ou sem espaço após >,
# e leading whitespace (pra colagem de texto formatado).
_RE_PREFIX = re.compile(r"^\s*(T|TEMA|E|C)\s*>\s*(.*)$", re.IGNORECASE)


def parse_podcast(texto: str) -> Podcast:
    """Parseia o texto bruto do podcast e retorna o objeto Podcast.

    Aceita E>/C>/T>/TEMA> case-insensitive. Linhas em branco viram separador
    natural; linhas sem prefixo são anexadas à fala anterior (continuação).
    """
    pc = Podcast()
    fala_atual: Fala | None = None

    def commit():
        nonlocal fala_atual
        if fala_atual and fala_atual.texto.strip():
            pc.falas.append(fala_atual)
        fala_atual = None

    for raw in texto.splitlines():
        line = raw.rstrip()
        if not line.strip():
            commit()
            continue

        m = _RE_PREFIX.match(line)
        if m:
            commit()
            tag = m.group(1).upper()
            content = m.group(2).strip()
            if tag == "T" and not pc.titulo:
                pc.titulo = content
            elif tag == "TEMA" and not pc.tema:
                pc.tema = content
            elif tag in ("E", "C"):
                fala_atual = Fala(locutor=tag, texto=content)
            else:
                # T> e TEMA> repetidos viram fala de entrevistador,
                # pra não perder conteúdo.
                fala_atual = Fala(locutor="E", texto=content)
        else:
            # Continuação da fala anterior (mantém parágrafo).
            if fala_atual is not None:
                fala_atual.texto += " " + line.strip()
            # Senão, ignora linha solta sem prefixo.

    commit()

    # Abertura automática se houver título/tema mas nenhuma fala E começar.
    if (pc.titulo or pc.tema) and pc.falas and pc.falas[0].locutor != "E":
        abertura_partes = ["Olá, bem-vindos a mais um episódio."]
        if pc.titulo:
            abertura_partes.append(f"Hoje no programa: {pc.titulo}.")
        if pc.tema:
            abertura_partes.append(f"O tema é {pc.tema}.")
        abertura = " ".join(abertura_partes)
        pc.falas.insert(0, Fala(locutor="E", texto=abertura))

    return pc


# =========================
# GERAÇÃO DE ÁUDIO
# =========================
async def _gerar_segmento(
    texto: str,
    voz: str,
    rate: str,
    caminho_saida: str,
    cancel: threading.Event,
    max_retries: int = 3,
) -> None:
    """Gera 1 segmento MP3 via Edge-TTS, com retry."""
    for tentativa in range(1, max_retries + 1):
        if cancel.is_set():
            raise asyncio.CancelledError()
        try:
            tts = edge_tts.Communicate(texto, voice=voz, rate=rate)
            await tts.save(caminho_saida)
            return
        except Exception as e:
            log.warning(f"podcast TTS tentativa {tentativa} falhou: {e}")
            if tentativa == max_retries:
                raise
            await asyncio.sleep(1.5 * tentativa)


def _concat_mp3(segmentos: list[str], saida: str) -> None:
    """Concatena MP3s binariamente. Edge-TTS produz MP3 CBR consistente,
    então frame-stream funciona sem ffmpeg.
    """
    with open(saida, "wb") as out:
        for seg in segmentos:
            with open(seg, "rb") as f:
                # Pula ID3v2 header se houver (3 bytes 'ID3' + 3 + 4 size).
                head = f.read(10)
                if head[:3] == b"ID3":
                    # Tamanho ID3v2 = bytes 6-9 sincsafe
                    size = (
                        (head[6] & 0x7F) << 21
                        | (head[7] & 0x7F) << 14
                        | (head[8] & 0x7F) << 7
                        | (head[9] & 0x7F)
                    )
                    f.seek(10 + size)
                else:
                    f.seek(0)
                out.write(f.read())


def estimar_duracao_segundos(podcast: Podcast, palavras_por_min: int = 165) -> float:
    """Estimativa rude da duração (180-200 wpm é padrão narrativo)."""
    total_palavras = sum(len(f.texto.split()) for f in podcast.falas)
    return total_palavras / palavras_por_min * 60


async def gerar_podcast_async(
    podcast: Podcast,
    voz_entrevistador: str,
    voz_convidado: str,
    rate: str,
    caminho_saida: str,
    cancel: threading.Event,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> None:
    """Gera o MP3 único do podcast.

    progress_cb(atual, total, mensagem) é chamado a cada segmento gerado.
    """
    if not podcast.falas:
        raise ValueError("Podcast sem falas — verifique o script.")

    total = len(podcast.falas)
    with tempfile.TemporaryDirectory(prefix="bizudeck_pod_") as tmp:
        segmentos: list[str] = []
        for i, fala in enumerate(podcast.falas, 1):
            if cancel.is_set():
                raise asyncio.CancelledError()
            voz = voz_entrevistador if fala.locutor == "E" else voz_convidado
            seg_path = os.path.join(tmp, f"seg_{i:04d}.mp3")
            if progress_cb:
                progress_cb(i - 1, total, f"Gerando fala {i}/{total} ({fala.locutor})")
            await _gerar_segmento(fala.texto, voz, rate, seg_path, cancel)
            segmentos.append(seg_path)

        if progress_cb:
            progress_cb(total, total, "Mesclando áudio...")
        _concat_mp3(segmentos, caminho_saida)

    if progress_cb:
        progress_cb(total, total, "Pronto.")


# =========================
# HELPER: rodar em thread/UI
# =========================
def gerar_podcast_sync(
    podcast: Podcast,
    voz_entrevistador: str,
    voz_convidado: str,
    rate: str,
    caminho_saida: str,
    cancel: threading.Event,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> None:
    """Wrapper síncrono — útil pra rodar dentro de threading.Thread."""
    asyncio.run(gerar_podcast_async(
        podcast, voz_entrevistador, voz_convidado, rate,
        caminho_saida, cancel, progress_cb,
    ))


# =========================
# CONVERSOR: questões -> script de podcast
# =========================
def quizzes_to_script(
    blocos: list[dict],
    titulo: str = "",
    tema: str = "",
    intro_extra: str = "",
    fechamento: str = "",
) -> str:
    """Converte uma lista de blocos do parser do BizuDeck em um script de podcast.

    Cada bloco vira uma troca E>/C>: o entrevistador faz a pergunta, o
    convidado responde com a alternativa correta (se múltipla) ou a resposta
    aberta. Adiciona transições naturais entre questões pra não ficar robótico.
    """
    linhas = []
    if titulo:
        linhas.append(f"T> {titulo}")
    if tema:
        linhas.append(f"TEMA> {tema}")
    linhas.append("")

    saudacoes_e = [
        "Hoje vamos revisar pontos importantes desse tema.",
        "Vamos começar com a primeira questão.",
        "Bora pra próxima.",
        "Olha que interessante essa daqui.",
        "Essa próxima cai sempre em prova.",
        "Vamos seguindo com mais uma.",
        "Outra pra refletir.",
        "Mais uma pra fixar.",
    ]

    if intro_extra.strip():
        linhas.append(f"E> {intro_extra.strip()}")
        linhas.append("")

    for i, b in enumerate(blocos, 1):
        pergunta = (b.get("pergunta") or "").strip()
        if not pergunta:
            continue
        tipo = b.get("tipo", "aberta")

        # Transição pra não ficar repetitivo
        if i == 1 and not intro_extra.strip():
            transicao = "Primeira questão."
        else:
            transicao = saudacoes_e[(i - 1) % len(saudacoes_e)]

        # Pergunta do entrevistador
        if tipo == "multipla":
            opcoes = b.get("opcoes", [])
            opc_str = " ".join(f"Letra {o['letra']}: {o['texto']}." for o in opcoes)
            linhas.append(f"E> {transicao} {pergunta} As alternativas são: {opc_str}")
            letra = b.get("letra_correta", "").upper()
            texto_correta = b.get("resposta_correta", "")
            if letra and texto_correta:
                linhas.append(f"C> A resposta correta é a letra {letra}: {texto_correta}.")
            elif letra:
                linhas.append(f"C> A resposta correta é a letra {letra}.")
            else:
                linhas.append(f"C> A resposta correta é: {texto_correta}.")
        else:
            linhas.append(f"E> {transicao} {pergunta}")
            resp = b.get("resposta_correta", "").strip()
            linhas.append(f"C> {resp}")

        linhas.append("")  # separador visual

    if fechamento.strip():
        linhas.append(f"E> {fechamento.strip()}")
    else:
        linhas.append("E> E é isso por hoje, pessoal. Até o próximo episódio.")
        linhas.append("C> Valeu, até mais.")

    return "\n".join(linhas)


# =========================
# Mini-teste local
# =========================
if __name__ == "__main__":
    exemplo = """
    T> Engenharia de Software — Fundamentos
    TEMA> Crise do Software e camadas da engenharia

    E> Bom dia! Hoje vamos falar sobre os fundamentos de Engenharia de Software.
    C> Bom dia, tema clássico.
    E> Para começar, o que é a Crise do Software segundo Dijkstra?
    C> Dijkstra apontou que com o aumento exponencial do poder das máquinas,
       programar tornou-se um problema gigantesco.
    E> E quais são as quatro camadas da Engenharia de Software?
    C> Qualidade, processo, métodos e ferramentas.
    """
    pc = parse_podcast(exemplo)
    print(f"Título: {pc.titulo}")
    print(f"Tema: {pc.tema}")
    print(f"Falas: {len(pc.falas)}")
    for f in pc.falas:
        print(f"  [{f.locutor}] {f.texto[:80]}...")
    print(f"Duração estimada: {estimar_duracao_segundos(pc):.1f}s")
