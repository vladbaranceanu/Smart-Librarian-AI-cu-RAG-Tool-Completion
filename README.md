# 📚 AI Book Recommender (GPT + RAG + Detailed Summary + TTS)

An AI chatbot that:
1) recommends books using **GPT + RAG (ChromaDB)** based on the user’s interests,  
2) then appends a **detailed summary** pulled from a local Markdown file via a separate tool,  
3) optionally **speaks** the recommendation + summary (CLI: press `p`; Streamlit: click **Play audio**).

## ✨ Features
- **RAG** with ChromaDB over your local `.md` documents
- **Exact-title summary tool** from `book_summaries.md`
- **Inappropriate-language filter** (blocks and replies politely without hitting the LLM)
- **CLI**  (with audio playback via OpenAI TTS)

---

## 🧱 Requirements

- **Python** 3.10 or 3.11 (recommended)
- An OpenAI API key with access to:
  - a chat model (e.g., `gpt-4o-mini`)
  - a TTS model (e.g., `gpt-4o-mini-tts` or `tts-1`)
- OS: Windows/macOS/Linux

### Python packages

```bash
pip install -U   langchain-community langchain-openai openai chromadb   unstructured python-dotenv streamlit
# optional for CLI audio playback:
pip install playsound==1.2.2
```

> If you use PDFs later, also install: `pypdf`  
> If `unstructured` complains about extra dependencies, install what it suggests for your OS.

---

## 📁 Project Structure

```
your-project/
├─ main.py                       # your CLI script (GPT+RAG + summary + TTS)
├─ .env                          # holds OPENAI_API_KEY
├─ book_summaries.md          # detailed summaries file
└─ README.md
```

> Adjust paths in code if your data lives elsewhere.  
> In code, `markdown_path` points to `C:/Users/vbaranceanu/PycharmProjects/RagProject`.

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```ini
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> Alternatively, export in your shell:
> - macOS/Linux: `export OPENAI_API_KEY=...`
> - Windows (PowerShell): `$env:OPENAI_API_KEY="..."`

---

## 📝 Preparing `book_summaries.md`

This file powers the **detailed summary tool**. Use exact titles and this format:

```md
## Title: 1984
A dystopian novel set in Airstrip One, exploring surveillance, control, and the fragility of truth. (Your full detailed summary here.)

## Title: The Hobbit
A classic adventure following Bilbo Baggins as he leaves the Shire and discovers courage, friendship, and dragons. (Full detailed summary here.)
```

- The code expects `## Title: <Exact Book Title>` headers.
- The text under each header (until the next `## Title:`) becomes the full summary.
- Titles must match **exactly** for lookups.

---


## ▶️ Running (CLI)

1) Make sure dependencies and `.env` are set.  
2) Run:

```bash
python main.py
```

3) Interact:
- Example prompts:
  - `I love epic fantasy with found-family vibes.`
  - `Give me the summary for 1984`
- After a response, you’ll be offered audio options:
  - Press **`p`** → save MP3 and play it (needs `playsound`)
  - Press **`s`** → just save MP3
  - Press **Enter** → skip audio

> The MP3 is saved (default `recommendation_summary.mp3`) in the project folder.


## 🛡️ Inappropriate Language Filter

- The input is normalized (diacritics removed; symbols stripped) and checked against a regex list.
- If detected, the app responds politely and **does not** send content to the LLM.
- Extend or tune the `INAPPROPRIATE_TERMS` list in code as needed.

---

## ⚙️ Configuration Highlights (in code)

- **RAG vector store**: `Chroma("langchain_store", OpenAIEmbeddings(...))`
- **Retriever Top-K**: `k=4` (tweak via `retriever = vectorstore.as_retriever(search_kwargs={"k": 4})`)
- **Models**:
  - Chat: `gpt-4o-mini`
  - TTS: `gpt-4o-mini-tts` (or `tts-1`)
- **Paths**:
  - `markdown_path` → folder with knowledge `.md` docs
  - `SUMMARIES_MD_PATH` → path to `book_summaries.md`

---

## 🧪 Quick Test Scenarios

- **Recommendation + summary**:
  - Prompt: `I'm into dark political sci-fi with surveillance themes.`
- **Direct summary**:
  - Prompt: `Give me the summary for 1984`
- **Audio**:
  - After a result in CLI, press `p` to generate and play audio.

---

## 🔒 Notes on Safety & Privacy

- Prompts are blocked locally if they contain offensive language.
- Your documents are embedded locally into ChromaDB; model calls go to OpenAI APIs.
- Do not commit your `.env` to version control.

---


Happy reading! 📖✨
