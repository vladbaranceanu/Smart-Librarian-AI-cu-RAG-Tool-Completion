from langchain_community.vectorstores import Chroma
from langchain_community.embeddings.openai import OpenAIEmbeddings
import chromadb.config
import os
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from dotenv import load_dotenv
import re
from pathlib import Path
import json
import unicodedata
from typing import List, Dict, Any
from io import BytesIO

# --- OpenAI ---
from openai import OpenAI

# Optional: local playback (you can comment these if you don't want playback)
try:
    from playsound import playsound  # simple cross-platform playback
    HAS_PLAYSOUND = True
except Exception:
    HAS_PLAYSOUND = False

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Missing OPENAI_API_KEY in .env")

# === RAG setup ===
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma("langchain_store", embeddings)

markdown_path = "C:/Users/vbaranceanu/PycharmProjects/RagProject"
markdown_loader = DirectoryLoader(markdown_path, glob='./*.md', loader_cls=UnstructuredMarkdownLoader)
markdown_docs = markdown_loader.load()

vectorstore.add_documents(markdown_docs)
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

# --- LLM (LangChain) ---
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.documents import Document

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

# === Helpers ===
def _format_docs(docs: List[Document]) -> str:
    parts = []
    for d in docs:
        txt = d.page_content.strip().replace("\n", " ")
        src = d.metadata.get("source", "unknown")
        parts.append(f"[{src}] {txt}")
    return "\n\n".join(parts)

def _unique_sources(docs: List[Document], top_n:int=3) -> str:
    uniq = []
    for d in docs:
        s = os.path.basename(d.metadata.get("source", "unknown"))
        if s and s not in uniq:
            uniq.append(s)
    return ", ".join(uniq[:top_n]) if uniq else "n/a"

# === Summaries tool (local .md) ===
def load_summaries_from_md(filepath: str) -> Dict[str, str]:
    text = Path(filepath).read_text(encoding="utf-8")
    pattern = r"## Title:\s*(.+?)\n(.*?)(?=\n## Title:|\Z)"
    matches = re.findall(pattern, text, flags=re.S)
    summaries = {}
    for title, summary in matches:
        summaries[title.strip()] = summary.strip().replace("\n", " ")
    return summaries

def get_summary_by_title(title: str, summaries: Dict[str, str]) -> str:
    return summaries.get(title, f"❌ I couldn't find any summary for the title: {title}")

client = OpenAI()

SUMMARIES_MD_PATH = "C:/Users/vbaranceanu/PycharmProjects/RagProject/book_summaries.md"
BOOK_SUMMARIES = load_summaries_from_md(SUMMARIES_MD_PATH)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_summary_by_title",
            "description": "Returns the full summary for an exact book title (from the local .md source).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Exact book title (e.g., '1984')."}
                },
                "required": ["title"]
            }
        }
    }
]

# === Inappropriate language filter ===
INAPPROPRIATE_TERMS = [
    # English
    r"fuck", r"shit", r"bitch(es)?", r"asshole(s)?", r"retard(ed)?", r"idiot(s)?",
    r"moron(s)?", r"stupid", r"slut", r"whore", r"bastard(s)?"
]
INAPPROPRIATE_REGEX = re.compile(r"(?<!\w)(" + r"|".join(INAPPROPRIATE_TERMS) + r")(?!\w)", flags=re.IGNORECASE)

import unicodedata
def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))

def is_inappropriate(text: str) -> bool:
    if not text: return False
    base = _strip_accents(text).casefold()
    base = re.sub(r"[\W_]+", " ", base)
    return INAPPROPRIATE_REGEX.search(base) is not None

POLITE_BLOCK_RESPONSE = (
    "I get that you might be upset. Please rephrase without offensive language and I’ll be happy to help. 💬"
)

# === Recommender (strict JSON) ===
RECO_SYSTEM_PROMPT = """You are a reading advisor. You receive a user request and context fragments from documents (RAG).
Your job: recommend ONE book from the context. If there's an exact tie, you may include a second candidate.

Return STRICT JSON ONLY, no prose, matching this schema:
{
  "titles": ["Primary Title", "Optional Second Title"],
  "pitch": "One-sentence recommendation for the primary title.",
  "reasons": ["Short reason 1", "Short reason 2", "Optional reason 3"],
  "needs_clarification": false,
  "clarification_question": null
}

Rules:
- Titles must be exact strings as they appear in context.
- Keep 'reasons' short (bullet-style).
- If context is insufficient, set needs_clarification=true and provide a single brief question.
- Answer in English.
"""

def recommend_with_rag(user_query: str) -> Dict[str, Any]:
    retrieved = retriever.get_relevant_documents(user_query)
    context = _format_docs(retrieved)
    messages = [
        SystemMessage(content=RECO_SYSTEM_PROMPT),
        HumanMessage(content=f"User request: {user_query}\n\nContext fragments:\n{context}")
    ]
    resp = llm.invoke(messages)
    try:
        data = json.loads(resp.content)
    except Exception:
        m = re.search(r"\*\*(.+?)\*\*", resp.content)
        title = m.group(1).strip() if m else ""
        data = {"titles": [title] if title else [], "pitch": "", "reasons": [], "needs_clarification": False, "clarification_question": None}
    return {"raw": resp.content, "data": data, "retrieved": retrieved}

def build_final_text(titles: List[str], pitch: str, reasons: List[str],
                     detailed_summary: str, sources: str) -> str:
    title_line = f"**Recommended Title:** {titles[0]}" if titles else "**Recommended Title:** (n/a)"
    bullets = "\n".join([f"• {r}" for r in reasons[:3]]) if reasons else "• —"
    alt = f"\n_Alternative:_ {titles[1]}" if len(titles) > 1 else ""
    summary_block = f"**Detailed summary**\n{detailed_summary}" if detailed_summary else "**Detailed summary**\n(n/a)"
    return f"{title_line} — {pitch}\n{bullets}{alt}\n\n{summary_block}\n\n(Sources for recommendation: {sources})"

TOOL_ROUTER_PROMPT = f"""You are a book assistant. You have access to a tool called get_summary_by_title.
Call it only if the user explicitly asks for the summary of a specific book (exact/obvious title).
Available titles: {", ".join(sorted(BOOK_SUMMARIES.keys()))}
"""

def assistant_reply_text(user_query: str) -> str:
    # 1) Safety
    if is_inappropriate(user_query):
        return POLITE_BLOCK_RESPONSE

    # 2) Direct summary route
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": TOOL_ROUTER_PROMPT},
                {"role": "user", "content": user_query}
            ],
            tools=tools,
            tool_choice="auto"
        )
        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []
    except Exception:
        tool_calls = []

    if tool_calls:
        final_messages = [
            {"role": "system", "content": TOOL_ROUTER_PROMPT},
            {"role": "user", "content": user_query},
            msg
        ]
        for call in tool_calls:
            if call.function.name == "get_summary_by_title":
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = call.function.arguments if isinstance(call.function.arguments, dict) else {}
                title = args.get("title", "")
                result = get_summary_by_title(title, BOOK_SUMMARIES)
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": "get_summary_by_title",
                    "content": result
                })
        followup = client.chat.completions.create(model="gpt-4o-mini", messages=final_messages)
        return followup.choices[0].message.content

    # 3) Recommendation + detailed summary pipeline
    reco = recommend_with_rag(user_query)
    data = reco["data"]
    retrieved_docs: List[Document] = reco["retrieved"]
    sources = _unique_sources(retrieved_docs)

    if data.get("needs_clarification"):
        q = data.get("clarification_question") or "Could you clarify your preferences (genre, period, tone)?"
        return q

    titles = data.get("titles") or []
    pitch = data.get("pitch") or ""
    reasons = data.get("reasons") or []
    if not titles:
        return "I couldn't confidently pick a title. Could you share more about genre, tone, or themes you enjoy?"

    primary_title = titles[0]
    detailed_summary = get_summary_by_title(primary_title, BOOK_SUMMARIES)
    return build_final_text(titles, pitch, reasons, detailed_summary, sources)

# ============== NEW: Text-to-Speech (TTS) ==============
# Uses an OpenAI TTS model to synthesize speech from the final text.
# Saves to MP3 and (optionally) auto-plays if playsound is available.

def synthesize_tts(text: str, out_path: str = "output_recommendation.mp3",
                   model: str = "gpt-4o-mini-tts", voice: str = "alloy") -> str:
    """
    Generate an MP3 with OpenAI TTS. Returns the path to the saved file.
    Models known to work: "gpt-4o-mini-tts" or "tts-1".
    """
    if not text or not text.strip():
        raise ValueError("Empty text for TTS.")
    # Create speech
    speech = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text
    )
    # speech is bytes-like (per new SDKs, it may be .read() or .content)
    audio_bytes = speech.read() if hasattr(speech, "read") else getattr(speech, "content", None)
    if audio_bytes is None:
        # Some SDKs return a dict with 'audio' base64. Try to handle it:
        if isinstance(speech, dict) and "audio" in speech:
            import base64
            audio_bytes = base64.b64decode(speech["audio"])
        else:
            raise RuntimeError("Unexpected TTS response format.")
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
    return out_path

def format_text_for_tts(final_text: str) -> str:
    """
    Strip markdown bullets and bold to make TTS sound nicer.
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", final_text)   # remove bold
    text = text.replace("•", "-")
    text = re.sub(r"\(Sources.*?\)$", "", text.strip(), flags=re.S)  # drop trailing sources
    return text.strip()

# === CLI ===
if __name__ == "__main__":
    print("Chat (GPT+RAG recommendation) → adds a detailed summary → optional Text-to-Speech. (Ctrl+C to exit)")
    print('Examples: "I love epic fantasy with found-family vibes." | "Give me the summary for 1984"')
    try:
        while True:
            q = input("\nYou: ").strip()
            if not q:
                continue
            if is_inappropriate(q):
                print("\nBot:", POLITE_BLOCK_RESPONSE)
                continue

            final_text = assistant_reply_text(q)
            print("\nBot:\n", final_text)

            # === NEW: press 'p' to play the audio ===
            choice = input("\nPress 'p' to play audio, 's' to save MP3 only, or Enter to skip: ").strip().lower()
            if choice in ("p", "s"):
                try:
                    tts_text = format_text_for_tts(final_text)
                    out_path = synthesize_tts(tts_text, out_path="recommendation_summary.mp3")
                    print(f"\nAudio saved to: {out_path}")
                    if choice == "p":
                        if HAS_PLAYSOUND:
                            print("Playing audio…")
                            playsound(out_path)
                        else:
                            print("Install 'playsound' to enable auto-play, or open the MP3 manually.")
                except Exception as e:
                    print(f"Text-to-Speech failed: {e}")
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
