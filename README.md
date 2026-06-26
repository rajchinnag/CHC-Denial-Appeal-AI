# CHC Denial Appeal AI

A standalone, fast-moving spike for one CHC Pro AI capability: take a coding-related
claim denial, de-identify the supporting medical record, research whether the denial
is actually valid against real payor policy, and generate the appeal or
reconsideration letter. Once this is solid, it gets folded into the main
CHC Pro AI pipeline as the Denial Intelligence + Appeal Generator layers.

## How it works

```
Intake form (payor, CARC/RARC, CPT/Dx/Rev/Condition/Occurrence/Value codes,
DRG, Type of Bill, visit type, specialty, taxonomy if specialty denial)
        |
        v
CARC lookup classifier  ->  coding | medical_necessity | experimental |
                             authorization | bill_type
        |
        v
Medical record upload  ->  text extraction  ->  PHI detection (regex +
                             Gemini) ->  tokenize  ->  [PATIENT_NAME_1] etc.
        |
        v
Gemini + Google Search grounding: fetch the payor's real, current policy /
LCD/NCD, determine whether the denial is valid given the codes
        |
        v
Gemini: generate appeal letter (if denial invalid) or reconsideration
letter (if denial is valid but payment can still be justified) — still
working on de-identified text
        |
        v
Re-identify: swap tokens back to real PHI in the final letter only.
The token<->PHI map lives in memory for this one request and is never
persisted, logged, or cached.
```

## IMPORTANT before using real patient data

The backend defaults to `GEMINI_MODE=api_key`, which uses a standard Google AI
Studio API key. **This mode has no HIPAA BAA.** It's meant for getting the app
running today and testing with synthetic or already-de-identified text.

Before any real PHI flows through this app:
1. Set up a GCP project and complete a Business Associate Agreement (BAA) with
   Google Cloud for Vertex AI.
2. Set `GEMINI_MODE=vertex` in `backend/.env`, fill in `GCP_PROJECT_ID` and
   `GOOGLE_APPLICATION_CREDENTIALS` (path to your service account JSON).

No code changes are needed to switch — `app/services/gemini_service.py` handles
both paths identically.

## Setup

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env: paste your Gemini API key (https://aistudio.google.com/apikey)
uvicorn app.main:app --reload --port 8000
```

### Frontend
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

## What's seeded vs. what needs expanding

- **CARC classification** (`backend/app/data/carc_codes.json`): seeded with ~30
  common codes across all five categories. X12's full CARC list is public —
  expand this table as you see real denials come through.
- **Payor policy lookup**: deliberately payor-agnostic from day one — Gemini
  searches live for whichever payor is entered, rather than relying on a
  pre-built knowledge base. No payor-specific setup needed.
- **PHI detection**: regex layer covers SSN/phone/email/date/zip patterns
  reliably. The Gemini layer covers names, MRNs, addresses, provider/facility
  names. Before this touches real records at volume, validate detection
  recall against a sample of real (but consented/test) records.

## Project structure

```
backend/
  app/
    main.py              FastAPI app + CORS
    config.py             env-driven settings (api_key vs vertex mode)
    models/schemas.py     ClaimIntake, AppealResult, etc.
    routers/claims.py     the one orchestration endpoint
    services/
      carc_classifier.py     CARC -> category lookup
      phi_deidentifier.py     detect/tokenize/reidentify PHI
      record_extractor.py     PDF/DOCX/TXT -> text
      gemini_service.py       Gemini calls (api_key + vertex modes, grounding)
    data/carc_codes.json   seed CARC lookup table
frontend/
  src/
    App.jsx
    components/IntakeForm.jsx
    components/ResultView.jsx
    styles/
```
