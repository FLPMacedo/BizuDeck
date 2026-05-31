# BizuDeck

> **Bizus que você memoriza.**
> Quiz interativo com áudio para **estudo ativo**: Escola, Faculdade, Concursos Públicos.

Você cola um conteúdo no ChatGPT (ou Gemini/Claude) com o prompt pronto do app, copia a saída pra um `.txt`, importa no BizuDeck e estuda. O app **gera os áudios em português**, **roda o quiz com feedback imediato**, **exporta o baralho pro Anki** com áudio em frente e verso e **gera um PDF de estudo** offline.

Sem chave de API. Sem assinatura. A IA roda fora do app — o app só lê o resultado e te faz estudar.

---

**Canal:** [youtube.com/@UaiScript](https://www.youtube.com/@UaiScript) — ferramentas e automações de estudo

---

## Como funciona

```
1. IA externa                 2. BizuDeck                  3. Você
   ──────────────                ──────────────               ───────
   ChatGPT/Gemini/Claude    →    Lê o .txt                →   Estuda no app
   gera um .txt no               Gera áudios PT-BR            (quiz interativo)
   formato P>/R>/*>              Exporta .apkg + PDF      →   ou no Anki
                                                          →   ou no PDF
```

## Funcionalidades

- 🎓 **Quiz interativo** com perguntas abertas (digite a resposta) e múltipla escolha (clique)
- 🔊 **Áudio em PT-BR** com 3 vozes do Edge TTS (gratuito), velocidade configurável
- 🎤 **Voz da pergunta ≠ voz da resposta** — Francisca pergunta, Antonio responde (ou troque como quiser)
- ✓ **Feedback automático**: comparação relaxada (sem caixa/acento/pontuação) + gabarito sempre visível
- 📦 **Exporta para Anki (.apkg)** com áudio embutido em frente E verso
- 📄 **Exporta PDF de estudo** com gabarito e espaço pra anotações — abre automaticamente
- ✏️ **Editor inline** — edita perguntas/respostas dentro do app, sem abrir Bloco de Notas
- 📖 **Manual completo em PDF** embarcado no app
- 📁 **4 exemplos prontos**: Direito Constitucional, História, Matemática, Português

## Formato do arquivo de quiz

```
P> Qual é o princípio constitucional segundo o qual ninguém é
   obrigado a fazer ou deixar de fazer algo senão em virtude de lei?
R> Princípio da legalidade.

P> Conforme a CF/88, qual o prazo da licença-maternidade?
A) 90 dias
B) 100 dias
C) 120 dias
D) 180 dias
*> C
```

**Regras:**
- Cada questão é um bloco separado por linha em branco
- `P>` começa a pergunta
- `R>` define a resposta (aberta)
- `A) B) C) D)` listam opções (múltipla)
- `*> X` indica a letra correta

Veja [PROMPT_IA.md](PROMPT_IA.md) — prompt pronto pra colar no ChatGPT/Gemini e gerar arquivos nesse formato.

## Instalação

### Opção 1 — Executável Windows (recomendado)

Baixe `BizuDeck.exe` na aba [Releases](https://github.com/FLPMacedo/BizuDeck/releases) e dê dois cliques. Não precisa instalar Python.

> Se o Windows reclamar na primeira execução, clique em **Mais informações → Executar assim mesmo**. É falso positivo do PyInstaller — código aberto neste repositório.

### Opção 2 — Rodar do código-fonte

```bash
git clone https://github.com/FLPMacedo/BizuDeck.git
cd BizuDeck
pip install -r requirements.txt
python BizuDeck.py
```

Funciona em Python 3.10+.

### Gerar o próprio executável

```bash
pip install pyinstaller
pyinstaller BizuDeck.spec
```

Saída em `dist/BizuDeck.exe`.

## Fluxo de uso

1. **Criar Quiz** → cole o conteúdo da matéria no prompt do app
2. Salve a saída da IA em `meu_quiz.txt` e **Importe**
3. Edite o nome do baralho, adicione/remova questões no editor inline
4. **🎧 Gerar áudios** (perguntas + respostas, em vozes diferentes)
5. Escolha um destino:
   - **▶ Iniciar Estudo** — quiz interativo dentro do app
   - **📦 Exportar para Anki** — baralho `.apkg` com áudio
   - **📄 Gerar PDF de estudo** — abre automaticamente

## Estrutura

```
BizuDeck.py             app principal
BizuDeck.spec           build do PyInstaller
requirements.txt        dependências
PROMPT_IA.md            prompt pronto pra colar em ChatGPT/Gemini/Claude
gerar_manual.py         gera Manual_BizuDeck.pdf
exemplos/
  exemplo_misto.txt           Direito Constitucional (10 questões)
  exemplo_historia.txt        História do Brasil (8 questões)
  exemplo_matematica.txt      Matemática elementar (12 questões)
  exemplo_portugues.txt       Português (12 questões)
assets/
  uaiscript.ico               ícone do app
  uaiscript.png               avatar do canal
  manual/Manual_BizuDeck.pdf  manual do usuário embarcado
quizzes/                pasta com áudios + .apkg + PDF (uma pasta por quiz)
logs/bizudeck.log       logs do app
config_bizudeck.json    gerado pelo app (vozes, velocidade, modo)
```

## Por que sem IA dentro do app

- 🆓 **Zero custo** — não precisa de API key paga
- 📴 **Funciona offline** depois que o áudio é gerado
- 🎯 **Você escolhe sua IA** — ChatGPT, Gemini, Claude, qualquer uma
- 🪶 **Mais leve, mais simples de manter, mais fácil de distribuir**
- O quiz em si (rodar, comparar, dar feedback) **não precisa** de LLM

## Comparação relaxada — como funciona

Para questões abertas, a resposta digitada é normalizada antes de comparar com o gabarito:

- Tudo minúsculas
- Sem acentuação
- Sem pontuação
- Espaços normalizados

A similaridade vem do `difflib.SequenceMatcher` (stdlib do Python, zero dependências). Faixas:

- `≥ 80%` → ✓ **correto**
- `40-79%` → ◐ **parcial**
- `< 40%` → ✗ **distante**

| Resposta digitada | Gabarito | Similaridade | Status |
|---|---|---:|:---:|
| `PRINCÍPIO da Legalidade!!!` | `Princípio da legalidade.` | 100% | ✓ |
| `principio da legalidade` | `Princípio da legalidade.` | 100% | ✓ |
| `legalidade` | `Princípio da legalidade.` | 60% | ◐ |
| `não sei` | `Princípio da legalidade.` | 33% | ✗ |

## Stack

- Python 3.12
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — UI moderna
- [edge-tts](https://github.com/rany2/edge-tts) — síntese de voz da Microsoft Edge
- [genanki](https://github.com/kerrickstaley/genanki) — geração de `.apkg`
- [reportlab](https://www.reportlab.com/) — PDF de estudo + manual
- pygame.mixer — playback de áudio
- PyInstaller — empacotamento `.exe`

## Canal

Tutoriais, scripts e ferramentas para automatizar estudo, trabalho e produtividade.

[**▶ youtube.com/@UaiScript**](https://www.youtube.com/@UaiScript)

---

### Projeto relacionado

Variação de [Criar_Baralho](https://github.com/FLPMacedo/Criar_Baralho) (AnkiAudio v2) — aquele gera baralhos Anki bilíngues para estudo de inglês. Este aqui é para estudo ativo com perguntas e respostas em português.
