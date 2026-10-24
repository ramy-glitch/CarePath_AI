# CarePath AI

CarePath AI is a prototype chatbot. A patient uploads a blood-test report and gets a plain-language explanation of the results.

The explanation is grounded in a local synthetic corpus written for this proof of concept. It is general information, not a diagnosis, and it is not medical advice. The patient sees the model output directly, plus the passages that supported it.

This document freezes the architecture agreed for the prototype. Clinician review and reinforcement learning are future work.

## What the prototype does

1. The patient uploads a blood-test document.
2. A teammate’s extraction step reads the document and returns anonymised JSON. Identifiers are removed. Test name, value, unit, reference range, and the high/low flag are kept. The original file is not stored.
3. The browser encrypts that JSON, and later the chat transcript, and keeps both locally.
4. Each chat turn is a new request. The server does not store the patient JSON or the chat.
5. The server retrieves relevant passages from the synthetic corpus and calls a local LLM.
6. The patient sees a short explanation and the passages that supported it. Passage URLs are placeholders for real NHS or NICE links later. The passage file is deleted after it is shown.
7. If the result is not covered, the patient sees one fixed message: contact their GP or NHS 111. The model does not choose between a GP visit and emergency care.

## Architecture

```mermaid
flowchart TB
  subgraph browserBox [Browser]
    upload[Upload document]
    files[("Encrypted lab JSON and chat")]
    key[AES-GCM key for this tab]
    ui[Chat and cited passages]
  end

  subgraph redactBox [Anonymisation - teammate]
    extract[OCR plus redaction]
  end

  subgraph serverBox [Application server - nothing patient-related is stored]
    retrieve[Hybrid retrieval]
    corpus[("Synthetic corpus")]
    llm[Ollama qwen3 1.7B]
    gate{Covered by retrieved passages?}
  end

  subgraph evalBox [Offline evaluation only]
    ragas[RAGAS]
    golden[("Golden set")]
  end

  upload --> extract
  extract -->|"anonymised JSON only"| files
  key --- files
  files -->|"fresh request each turn"| retrieve
  retrieve --> corpus
  retrieve --> llm
  llm --> gate
  gate -->|yes| ui
  gate -->|no| fixedMsg[Fixed message: GP or NHS 111]
  fixedMsg --> ui
  llm -.->|"scores the prototype, does not gate a live reply"| ragas
  golden --> ragas
```

The LLM is [Qwen3 1.7B](https://ollama.com/library/qwen3) served with the local [Ollama](https://ollama.com/) API (`qwen3:1.7b`). Thinking mode is off so the patient reply stays a short explanation. Token log probabilities are not a medical confidence score and are not used to accept or reject an answer.

## Data flow for one turn

```mermaid
sequenceDiagram
  participant Patient
  participant Browser
  participant Redaction as Anonymisation step
  participant Server
  participant Corpus as Synthetic corpus
  participant Ollama as Ollama qwen3 1.7B

  Patient->>Browser: Upload blood-test document
  Browser->>Redaction: Original document
  Redaction-->>Browser: Anonymised lab JSON
  Note over Browser: Encrypt and store. Discard the original file.

  Patient->>Browser: Ask about the result
  Browser->>Server: User prompt, anonymised lab JSON, chat so far
  Server->>Corpus: Hybrid search
  Corpus-->>Server: Relevant passages, or none
  alt Passages are strong enough
    Server->>Ollama: Prompt, lab JSON, passages, system prompt
    Ollama-->>Server: Explanation, or marked not covered
  end
  alt Covered
    Server-->>Browser: Explanation and passages
    Browser-->>Patient: Show both, then delete the passage file
  else Not covered
    Server-->>Browser: Fixed GP or NHS 111 message
    Browser-->>Patient: Show that message only
  end
  Note over Server: Request is handled in memory and discarded.
```

The chat is stored as encrypted JSON in the browser. Sending it again on the next turn is what gives the model memory. The server does not keep a session.

## When an answer is shown

RAGAS does not sit on this path. A normal chat model also does not return a calibrated confidence score for “this explanation is medically right.” A number written inside the reply is just more generated text.

The live rule has two steps:

1. **Retrieval cutoff.** Hybrid search returns a similarity score. If the best passage is below the cutoff chosen during evaluation, the model is not asked to explain. The patient gets the fixed GP or NHS 111 message.
2. **Explicit abstention.** If passages exist, the model must return a structured response: whether those passages cover this result, and the explanation. If it marks the result as not covered, the explanation is discarded and the same fixed message is shown.

```mermaid
flowchart TD
  request[Anonymised request arrives] --> search[Hybrid search]
  search --> cutoff{Best passage at or above the cutoff?}
  cutoff -->|no| fixed[Show the fixed GP or NHS 111 message]
  cutoff -->|yes| model[Call qwen3 1.7B]
  model --> covered{Model marks the result as covered?}
  covered -->|no| fixed
  covered -->|yes| show[Show the explanation and the passages]
```

The cutoff itself is tuned offline. It is not the RAGAS 0.8 figure. That 0.8 faithfulness threshold is only a target for the evaluation report.

### Offline evaluation

RAGAS runs locally on the server, against a golden set. It measures the prototype. It never accepts or rejects a live answer. Faithfulness is the metric that matters for this design: the reply should stay within the retrieved passages. Future work can add clinician validation and use that to train a reinforcement-learning update.

## Browser storage

Patient data stays in the browser. The server receives a request, uses it, and stores nothing about the patient.

| Piece | Where | What it holds |
| --- | --- | --- |
| Ciphertext and IV | IndexedDB | AES-GCM encrypted lab JSON and chat. Survives reload. |
| Key | sessionStorage | The AES-GCM key for this tab. Survives reload. Destroyed when the tab closes. |
| `lastUsed` | IndexedDB, unencrypted, beside the ciphertext | When the file was last used, so expiry can be checked after the key is gone. It does not contain the lab result. |

No password is required. A password would let the files survive closing the tab, which this design does not do. While the tab is open, script on this origin can read the key. Protection starts when the tab closes.

The interface has a per-file **Delete** button and a **Delete all** button. The notice shown to the patient:

> Files stay encrypted in your browser until you delete them, close the tab, or 24 hours pass.

```mermaid
stateDiagram-v2
  [*] --> Held: Extraction succeeds and the JSON is encrypted
  Held --> Held: Reload the same tab
  Held --> Held: Upload another file
  Held --> Deleted: Delete one file, or Delete all
  Held --> Expired: lastUsed is older than 24 hours
  Held --> Unreadable: Tab is closed and the key is destroyed
  Unreadable --> Purged: Next visit deletes the leftover ciphertext
  Expired --> Purged: Purge
  Deleted --> [*]
  Purged --> [*]
```

Other storage rules:

- Uploading a new file never deletes an older one. Only the patient deletes files, aside from the 24-hour purge and the purge after a closed tab.
- Closing the tab ends the session. The key is gone immediately, so the ciphertext cannot be read. Leftover bytes are removed the next time the site opens.
- sessionStorage is per tab and IndexedDB is shared. A second tab has no key. On load, purge only when the key is missing and no tab is still alive. A second tab must not delete files that belong to a tab that is still open. It should say that the session is open in another tab.

## Anonymisation

Redaction means removing anything that identifies the person and keeping the lab numbers.

Removed before anything is stored or sent:

- patient name, address, phone, email
- NHS number, hospital number, date of birth
- GP or clinician name
- sample barcodes that identify the person

Kept, because the explainer cannot work without them:

- test name, value, unit, reference range, and the high or low flag

The original scan or PDF is discarded after extraction. Only the anonymised JSON is encrypted.

This step is owned by a teammate (OCR, Microsoft Presidio, or another tool they choose). The constraint from this architecture:

- Anonymisation stays off this application server.
- The Ollama request receives anonymised JSON only. It never receives the original document.
- The redaction step does not log or save the file.
- If a company API is used, its terms have to be checked first, including retention, training on customer data, and logging, before a real report is sent.

The report still has to be seen by whatever performs redaction. It must not enter the model, the chat logs, or disk.

## Retrieval corpus

The corpus is a JSON file written for this prototype. It is not scraped from NHS, NICE, or any other site. Passages are simulated explanations in language a patient can understand. Each `simulatedUrl` is a placeholder on `example.nhs.uk`, not a real guideline link.

Panels in scope:

- full blood count
- U&E (kidney tests)
- liver tests
- HbA1c
- lipids
- thyroid
- iron studies

Each record is one analyte in one band. The band is decided from the reference range printed on that patient’s report, not from a range hardcoded in the corpus.

```json
{
  "id": "fbc-haemoglobin-high",
  "panel": "full_blood_count",
  "analyte": "haemoglobin",
  "aliases": ["Hb", "haemoglobin", "hemoglobin"],
  "band": "high",
  "title": "Haemoglobin above the range on your report",
  "text": "Plain-language explanation for the prototype.",
  "simulatedUrl": "https://example.nhs.uk/explain/haemoglobin"
}
```

`band` is `low`, `normal`, or `high`. Keyword search uses `aliases`. Embeddings use `title` and `text`. The current retriever is a hybrid of both. Real guideline templates and preprocessing are future work.

The patient can see the passages that were used. They are returned as a separate JSON file and deleted afterwards, so the reply stays interpretable without leaving that file behind.

## What is stored where

```mermaid
flowchart LR
  subgraph kept [Stays in the browser]
    lab[Anonymised lab JSON]
    chat[Chat JSON]
  end

  subgraph transient [Sent, used, not stored]
    request[One request in memory]
    answer[Explanation]
  end

  subgraph neverStore [Not kept]
    original[Original PDF or photo]
    passages[Retrieved passages file]
    serverCopy[Server copy of the patient]
  end

  lab --> request
  chat --> request
  request --> answer
  answer --> chat
  original -.->|"discarded after anonymisation"| neverStore
  passages -.->|"shown, then deleted"| neverStore
```

## Folder structure

The repository is split along the same boundaries as the architecture. The browser, the application server, anonymisation, the corpus, and offline evaluation do not share code. JSON shapes that cross those boundaries live in `shared/contracts/`. Files are empty placeholders.

```
client/                  browser only
  index.html
  src/main.js
  src/styles/app.css
  src/upload/            choose the document, then drop the original
  src/redaction-client/  send it for anonymisation, accept lab JSON back
  src/storage/           AES-GCM, IndexedDB, session key, lastUsed, purge, tab lock, delete
  src/chat/              encrypted transcript and sending a turn
  src/passages/          show cited passages, then delete that file
  src/api/               one fresh request per turn
  src/notice/            the storage notice
  src/refusal/           fixed GP or NHS 111 message

server/                  stateless application server
  app.py
  api/                   HTTP entry only
  retrieval/             corpus load, keyword, embedding, hybrid, cutoff
  llm/                   prompt assembly and Ollama
  gate/                  covered or not, and the fixed message
  passages/              citation JSON returned to the browser
  privacy/               request handled in memory, then discarded
  config/

anonymisation/           teammate’s step, outside the app server
  ocr.py
  redact_text.py
  redact_image.py
  to_lab_json.py
  discard_original.py

corpus/passages.json     synthetic retrieval corpus

evaluation/              offline RAGAS only
  run_ragas.py
  faithfulness.py
  tune_cutoff.py
  golden/golden_set.json

shared/contracts/        JSON shapes shared by browser, server, and anonymisation
  lab_result.schema.json
  passage.schema.json
  chat_turn_request.schema.json
  chat_turn_response.schema.json
  coverage.schema.json
```

`client/` is plain browser JavaScript. It owns upload, encryption, the chat transcript, and the notice. It never keeps the original document or the passage file.

`server/` is Python. `api/` receives a turn and does nothing else. `retrieval/` searches the corpus. `llm/` builds the prompt and calls Ollama with thinking mode off. `gate/` applies the retrieval cutoff and the coverage check. `passages/` builds the citation JSON the browser shows and then deletes. `privacy/` is the boundary that discards the request after the response is sent. There is no database package.

`anonymisation/` is a separate Python package for the teammate. OCR, text redaction, and image redaction stay here so the original report never enters `server/`.

`corpus/` holds the handmade passage file the retriever reads.

`evaluation/` runs RAGAS against the golden set and is where the retrieval cutoff is tuned. The live server does not import it.

`shared/contracts/` is the only place the lab result, a corpus passage, a chat request, a chat response, and the coverage flag are defined. The other packages follow those shapes.

## Out of scope for now

- Clinician validation of answers.
- Reinforcement learning from that validation.
- Live RAGAS, or any other online confidence score, as the accept or refuse switch.
- Real NHS or NICE pages, scraped text, or live links.
- Choosing between “see your GP” and “go to emergency.” The prototype uses one fixed, non-diagnostic message.
- A user password for encryption.

## Prototype status

The folders and files in [Folder structure](#folder-structure) exist and are empty. The behaviour in this document is not implemented yet. Anonymisation remains a teammate’s workstream under the constraint above.
