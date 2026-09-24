# Voice AI Agent - Patient Registration System

## Technical Assessment Brief

**Role:** Voice AI / Conversational AI Engineer

**Time limit:** 3 hours maximum
**Difficulty:** Intermediate - Advanced

> This document is a structured Markdown version of the supplied coding challenge. It retains the stated requirements and separates required scope from optional bonuses and suggestions.

---

## 1. Goal

Build a voice-based AI agent that is reachable through a real, dialable U.S. phone number. A caller must be able to register as a patient through natural conversation. The system must:

1. Collect standard U.S. patient demographic information.
2. Validate the information during the conversation.
3. Confirm all collected information with the caller before saving it.
4. Persist the patient record in a database that survives server restarts.
5. Expose the patient data through a lightweight REST API.

During review, the reviewer will call the supplied phone number. If they call again later, the record from the previous call must still be available through the API.

The challenge evaluates integration of telephony, an LLM, a database, and an API into one cohesive, production-oriented system.

---

## 2. Required System Flow

```text
Caller dials U.S. phone number
        -> Voice AI agent (telephony + LLM) answers
        -> Agent collects and validates demographics conversationally
        -> Agent reads all collected details back to the caller
        -> Caller confirms or corrects details
        -> Agent saves the record through the REST API or shared service layer
        -> Persistent database stores the record
        -> Agent confirms success and ends the call gracefully

REST API <-> Persistent database
```

The voice agent, data layer, and REST API should have clear separation of concerns.

---

## 3. Functional Requirements

### 3.1 Telephony and Voice Agent

| Requirement | Details |
| --- | --- |
| Real phone number | Provision a real, dialable U.S. phone number through a telephony provider, such as Twilio, Vonage, Vapi, Retell, or Bland.ai. |
| Natural voice interaction | Use a natural conversation, not a rigid IVR/menu flow. It should feel like speaking with a human intake coordinator. |
| LLM-powered conversation | Any LLM is allowed (OpenAI, Anthropic, Google, or open-source). It must understand varied phrasing, ask clarifying questions, and handle caller corrections. |
| Confirmation before saving | Read back **all collected information** and ask the caller to confirm it or correct any field before saving. |
| Invalid-data handling | If the caller gives invalid information, re-prompt specifically for that field. Examples: a three-digit phone number or a future date of birth. |
| Graceful completion | After a successful registration, give a short confirmation such as: “You're all set, [First Name].” Then end the call gracefully. |

### 3.2 Patient Demographic Data Model

Collect and store the following standard minimum demographic dataset.

| Field | Type | Required | Validation / behaviour |
| --- | --- | :---: | --- |
| `first_name` | String | Yes | 1-50 characters; alphabetic characters, hyphens, and apostrophes allowed. |
| `last_name` | String | Yes | 1-50 characters; alphabetic characters, hyphens, and apostrophes allowed. |
| `date_of_birth` | Date | Yes | Valid date; must not be in the future; use `MM/DD/YYYY`. |
| `sex` | Enum | Yes | One of: `Male`, `Female`, `Other`, `Decline to Answer`. |
| `phone_number` | String | Yes | Valid U.S. 10-digit phone number. |
| `email` | String | No | Valid email format. |
| `address_line_1` | String | Yes | Street address. |
| `address_line_2` | String | No | Apartment, suite, or unit, if applicable. |
| `city` | String | Yes | 1-100 characters. |
| `state` | String | Yes | Valid two-letter U.S. state abbreviation. |
| `zip_code` | String | Yes | Five-digit U.S. ZIP code or ZIP+4 format. |
| `insurance_provider` | String | No | Name of insurance company. |
| `insurance_member_id` | String | No | Alphanumeric member/subscriber ID. |
| `preferred_language` | String | No | Default: `English`. |
| `emergency_contact_name` | String | No | Full name. |
| `emergency_contact_phone` | String | No | Valid U.S. 10-digit phone number. |
| `created_at` | Timestamp | Auto | Generated when the record is created, in UTC. |
| `updated_at` | Timestamp | Auto | Generated when the record is modified, in UTC. |
| `patient_id` | UUID | Auto | Generated unique identifier. |

#### Conversation rule for optional fields

The agent does **not** need to ask for every optional field on every call. It must collect all required fields, then offer optional information, for example:

> “I can also collect your insurance information, emergency contact, and preferred language. Would you like to provide any of those?”

The caller should be able to opt in or decline.

### 3.3 Persistent Database

| Requirement | Details |
| --- | --- |
| Database engine | Use any relational or document database, for example PostgreSQL, SQLite, MySQL, or MongoDB. |
| Persistence | Data must survive server restarts. A patient registered in one call must still exist for a later query or call. |
| Schema | Enforce the above data model with appropriate column types and constraints. |
| Seed data | Optional: include one or two seed patient records for demonstration. |

### 3.4 REST API

Expose these endpoints:

| Method | Endpoint | Required behaviour |
| --- | --- | --- |
| `GET` | `/patients` | List all patients. Support optional filters: `last_name`, `date_of_birth`, and `phone_number`. |
| `GET` | `/patients/:id` | Retrieve one patient by `patient_id` (UUID). |
| `POST` | `/patients` | Create a patient and return the created record, including `patient_id`. |
| `PUT` | `/patients/:id` | Update an existing patient. Partial updates are allowed. |
| `DELETE` | `/patients/:id` | Soft-delete a patient by setting a `deleted_at` timestamp. Do **not** hard-delete the record. |

#### API standards

- Use suitable HTTP status codes, including `200`, `201`, `400`, `404`, `422`, and `500`.
- Validate all inputs on the server. Do not rely only on validation by the voice agent.
- Return JSON in a consistent envelope:

```json
{
  "data": {},
  "error": null
}
```

### 3.5 Voice-Agent-to-Database Integration

- Once the caller confirms their information, the agent must create the record by calling `POST /patients` or by using an equivalent shared service-layer write.
- The agent must tell the caller whether saving succeeded. If saving fails, it must give a graceful error message rather than silence.
- **Bonus:** If a phone number matches an existing patient, the agent recognizes this and asks whether the caller wants to update that existing record instead.

---

## 4. Non-Functional Requirements

| Area | Expectation |
| --- | --- |
| Deployment | The system must be running and callable during review. Any hosting is allowed, for example Railway, Render, Fly.io, Replit, ngrok, AWS, or GCP. |
| Code quality | Code should be clean, readable, well-organized, and intentionally structured. |
| README | Include setup instructions, an architecture description, tech-stack justification, required environment variables, and known limitations or trade-offs. |
| Security | Do not hardcode API keys. Use environment variables and perform basic API input sanitization. |
| Observability | Log agent conversations at minimum as the final collected data payload, to stdout or a log file. |

---

## 5. Evaluation Criteria

Each category is weighted equally at **20%**.

### 5.1 Working System (20%)

- A reviewer can call the number and complete a patient registration.
- Patient data is persisted and can be retrieved through the API.
- A second call does not lose previously stored data.

### 5.2 Conversational Quality (20%)

- The agent sounds natural rather than robotic or rigidly scripted.
- It handles corrections gracefully, for example correcting the spelling of a last name.
- It confirms information before saving it.
- It handles interruptions and out-of-order responses.

### 5.3 Technical Architecture (20%)

- Separation between telephony, LLM logic, data layer, and API is clear.
- The database schema has appropriate types and constraints.
- API endpoints are RESTful and correctly validated.
- Voice-agent prompt engineering is thoughtful and documented.

### 5.4 Code Quality and Documentation (20%)

- Code is organized, readable, and consistent.
- The README is complete and accurate.
- Trade-offs and known limitations are documented.
- The LLM prompt/system message is included and commented.

### 5.5 Edge Cases and Resilience (20%)

The implementation should handle or document how it handles:

- An invalid date of birth.
- A dropped telephony connection during registration.
- A failed database write, with an explicit response to the caller.
- A caller who wants to start over during a conversation.

---

## 6. Bonus Challenges (Optional)

These do not affect the core score, but demonstrate additional depth.

- **Duplicate detection:** Identify a returning caller by phone number and offer an update instead of creating a new record.
- **Appointment scheduling:** After registration, offer to schedule a first appointment. Mock data is acceptable.
- **Multi-language support:** Switch to Spanish if the caller says, “Hablo español.”
- **Call recording/transcript:** Store a transcript or summary of each call, linked to the patient record.
- **Dashboard:** Create a simple web interface that displays registered patients.
- **Automated tests:** Add unit or integration tests for the API layer.

---

## 7. Technology Choices (Suggestions Only)

Any suitable technologies may be used. Suggested combinations:

| Layer | Possible options |
| --- | --- |
| Telephony and voice AI | Vapi, Retell AI, Bland.ai, Twilio + Deepgram/ElevenLabs, Vonage |
| LLM | OpenAI GPT-4o / GPT-4o mini, Anthropic Claude, Google Gemini, Groq + Llama |
| Backend | Node.js (Express/Fastify), Python (FastAPI/Flask), Go, Ruby on Rails |
| Database | PostgreSQL, SQLite for simplicity, MongoDB, Supabase |
| Hosting | Railway, Render, Fly.io, Replit, Vercel + serverless DB, ngrok for local development |

> Tip from the challenge: Vapi and Retell can abstract much of the telephony, speech-to-text, and text-to-speech work, which leaves more time for the LLM prompt, tool definitions, and backend integration.

---

## 8. Submission Requirements

Submit within **3 hours** of receiving the challenge.

1. **Repository**
   - Push code to a public or private GitHub/GitLab repository.
   - If the repository is private, grant access to the reviewer emails supplied separately.

2. **Live demo**
   - Keep the phone number and API endpoint live and accessible during review.
   - Include both the phone number and the API base URL in `README.md`.

3. **Submission details**
   - Repository URL
   - Phone number to call
   - API base URL, such as `https://your-app.railway.app`
   - Any credentials or notes needed for testing

4. **If time runs out**
   - Submit the working portion of the system.
   - Document planned follow-up work in a `Next Steps` section of the README.
   - A working but incomplete submission is valued more highly than an ambitious, non-functional one.

---

## 9. Explicit Scope Boundaries

- This is **not** a request for a production healthcare platform with HIPAA compliance and 99.99% uptime.
- Do **not** store real patient data.
- A voice-AI platform is allowed and encouraged; you do not need to build speech-to-text or text-to-speech from scratch.
- AI coding assistants are allowed. The reviewer cares about the output, your understanding, and your ability to explain your decisions.
- If a phone number cannot be provisioned because of a vendor issue, document what was tried and why it failed, and provide a working local setup with clear test instructions. This will not be penalized as a vendor issue, but the handling of the blocker will be evaluated.

---

## 10. Implementation Acceptance Checklist

Use this checklist before submitting.

### Core end-to-end path

- [ ] A real, callable U.S. phone number reaches the voice agent.
- [ ] The agent collects all required patient fields conversationally.
- [ ] The agent validates invalid inputs and re-prompts for the specific field.
- [ ] The caller can correct information.
- [ ] The agent reads back all collected information and receives confirmation before saving.
- [ ] The record is persisted successfully.
- [ ] The agent reports success or a graceful failure to the caller and ends the call.

### Data and API

- [ ] The database persists records through a server restart.
- [ ] The model has a UUID patient ID, UTC creation/modification timestamps, and appropriate validation/constraints.
- [ ] `GET /patients` lists records and supports the three required filters.
- [ ] `GET /patients/:id` retrieves a single record.
- [ ] `POST /patients` creates a record and returns its ID.
- [ ] `PUT /patients/:id` supports partial updates.
- [ ] `DELETE /patients/:id` performs a soft delete with `deleted_at`.
- [ ] Server-side validation and consistent JSON envelopes are implemented.

### Delivery and documentation

- [ ] API keys are stored in environment variables, not source code.
- [ ] The final collected payload (at minimum) is logged.
- [ ] The README explains setup, architecture, stack choices, environment variables, trade-offs, and limitations.
- [ ] The README contains the live phone number and API base URL.
- [ ] The LLM prompt/system message is included, commented, and documented.

---

## 11. What the Reviewer Values Most

Prioritize a simple, reliable end-to-end experience over over-engineering. The challenge is specifically looking for an engineer who can:

- Integrate multiple systems under time pressure.
- Make sensible trade-offs, such as using SQLite instead of PostgreSQL when it improves delivery speed, while still investing in clean prompt engineering and error handling.
- Deliver an end-to-end working system rather than isolated components.
- Create a good caller experience.
- Communicate architectural choices clearly through code and documentation.

> A simple system that works flawlessly is preferred over an over-engineered system that fails on the first call.
