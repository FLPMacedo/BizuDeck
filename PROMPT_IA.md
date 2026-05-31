# 🤖 Prompt para gerar quiz com IA externa

> Cole este prompt no ChatGPT, Gemini, Claude ou qualquer LLM gratuito,
> substituindo `[TEMA]` e (opcional) `[CONTEÚDO]`.
> A IA vai gerar um `.txt` no formato que o BizuDeck lê.

---

## 📋 Prompt pronto (cole exatamente isso)

```
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
```

---

## ✨ Dicas de uso

- **Mais perguntas?** Troque `15 questões` pelo número que quiser (até ~30 funciona bem em LLM gratuito).
- **Só abertas?** Adicione: *"Use apenas o tipo P>/R>."*
- **Só múltipla escolha?** Adicione: *"Use apenas o tipo com A) B) C) D) *>."*
- **Sem CONTEÚDO?** Deixe vazio que a IA gera com base no conhecimento dela.
- **Veio com Markdown ou numeração?** Peça: *"Sem ** ou ##. Use exatamente P>, R>, A) B) C) D) e *>."*

---

## 🧪 Exemplo de saída esperada

```
P> Qual é o princípio constitucional segundo o qual ninguém é obrigado a fazer ou deixar de fazer algo senão em virtude de lei?
R> Princípio da legalidade.

P> A Administração Pública direta e indireta deve obedecer aos princípios de:
A) Apenas legalidade e impessoalidade
B) Legalidade, impessoalidade, moralidade, publicidade e eficiência
C) Legalidade, eficiência, supremacia e indisponibilidade
D) Apenas moralidade e publicidade
*> B

P> O que é o princípio da impessoalidade?
R> A Administração deve agir sem favorecimento ou perseguição pessoal.
```

---

## 📥 Próximos passos no app

1. Salve a saída da IA em um arquivo `.txt` (ex: `quiz_constitucional.txt`)
2. Abra o BizuDeck
3. Vá em **Criar Quiz → Importar .txt**
4. Clique em **🎧 Gerar áudios das perguntas** (opcional)
5. Clique em **▶ Iniciar Estudo**

Pronto pra estudar.
