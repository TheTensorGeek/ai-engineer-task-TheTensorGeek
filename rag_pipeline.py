import os, json, argparse, requests
import numpy as np, faiss
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from openai import OpenAI

# local embedder
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Groq-compatible OpenAI endpoint
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# embedding dim for all-MiniLM-L6-v2
EMB_DIM = 384

def embed_text(text: str):
    emb = embedder.encode([text])[0]
    return np.array(emb, dtype=np.float32)

def build_index(paths_txt: str, index_path='faiss_index.faiss', meta_path='kb_meta.json'):
    corpus_texts, meta = [], []
    with open(paths_txt, 'r') as f:
        for line in f:
            src = line.strip()
            if not src: continue
            if src.startswith('http'):
                txt = requests.get(src).text
            else:
                with open(src, 'r', encoding='utf-8', errors='ignore') as fh:
                    txt = fh.read()
            # split into 2k-char chunks
            chunks = [txt[i:i+2000] for i in range(0, len(txt), 2000)]
            for c in chunks:
                meta.append({'source': src})
                corpus_texts.append(c)

    embeddings = [embed_text(t) for t in tqdm(corpus_texts, desc='Embedding')]
    embeddings = np.vstack(embeddings).astype('float32')

    index = faiss.IndexFlatL2(EMB_DIM)
    index.add(embeddings)
    faiss.write_index(index, index_path)

    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'texts': corpus_texts}, f)
    print('Index built:', index_path, meta_path)

def load_index(index_path='faiss_index.faiss', meta_path='kb_meta.json'):
    return faiss.read_index(index_path), json.load(open(meta_path, 'r', encoding='utf-8'))

def retrieve(query: str, k=3, index=None, meta=None):
    qv = embed_text(query).reshape(1, -1).astype('float32')
    D, I = index.search(qv, k)
    results = []
    for idx in I[0]:
        results.append({'text': meta['texts'][idx], 'source': meta['meta'][idx]['source']})
    return results

# def analyze_with_llm(doc_text: str, retrieved: list):
#     prompt = ("You are an ADGM compliance assistant. Using the following evidence and the document, "
#               "find compliance issues (jurisdiction errors, missing clauses, missing signatory, ambiguous / non-binding language). "
#               "Return a JSON array where each entry has: section_snippet, issue, severity, suggestion.\n\n")
#     prompt += "Document:\n" + doc_text[:4000] + "\n\nEvidence:\n"
#     for r in retrieved:
#         prompt += f"Source: {r['source']}\n{r['text'][:800]}\n---\n"
#     prompt += "\nReturn only JSON array."

#     resp = client.chat.completions.create(
#         model="llama3-70b-8192",
#         messages=[{'role':'user','content':prompt}],
#         temperature=0
#     )
#     out = resp.choices[0].message.content
#     try:
#         return json.loads(out)
#     except Exception:
#         return [{'section_snippet': doc_text[:200], 'issue': out, 'severity': 'medium', 'suggestion': ''}]

def analyze_with_llm(doc_text: str, retrieved: list):
    # Build evidence section
    evidence_text = ""
    for r in retrieved:
        snippet = r.get("text", "")[:800].replace("\n", " ")
        source = r.get("source", "source")
        evidence_text += f"Source: {source}\n{snippet}\n---\n"

    prompt = f"""
You are a Legal AI Assistant specialized in ADGM corporate law. 
The user has uploaded a .docx file that may be part of the company incorporation process.

Your tasks:

1. **Identify the document type** (e.g., Articles of Association, Board Resolution, etc.).
2. **Check mandatory documents** for incorporation are present (if this doc is part of a set).
3. **Detect legal red flags** and inconsistencies (e.g., missing clauses, conflicting terms).
4. **Insert contextual comments** in the text (pretend these will be embedded as Word comments).
   Format: [COMMENT: <your comment>] inserted **right after** the flagged text.
5. **Suggest legally compliant replacement clauses** if applicable.
6. **Summarize findings** in a structured JSON with:
   {{
     "document_type": "...",
     "mandatory_docs_check": "...",
     "legal_red_flags": [
       {{
         "section": "...",
         "issue": "...",
         "suggestion": "..."
       }}
     ],
     "suggested_clauses": ["..."],
     "overall_summary": "..."
   }}
7. **Output format**:
   First, write the full reviewed document text (with [COMMENT: ...] inserted where needed).
   Then, on a new line, provide the JSON summary as valid JSON.

Evidence you may use:
{evidence_text}

Here is the document content to review:
---
{doc_text}
---
"""

    resp = client.chat.completions.create(
        model="llama3-70b-8192",  # Or "mixtral-8x7b-32768" if you prefer
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0
    )

    ai_output = resp.choices[0].message.content.strip()

    # Split reviewed text and JSON
    json_start = ai_output.find("{")
    if json_start != -1:
        reviewed_text = ai_output[:json_start].strip()
        json_str = ai_output[json_start:].strip()
        try:
            parsed_json = json.loads(json_str)
        except Exception:
            parsed_json = {"raw_output": json_str}
    else:
        reviewed_text = ai_output
        parsed_json = {"raw_output": ai_output}

    return reviewed_text, parsed_json


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build'])
    parser.add_argument('--paths', default='paths.txt')
    args = parser.parse_args()
    if args.action == 'build':
        build_index(args.paths)
