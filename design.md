# Design: Lenny Growth Assistant

## 1. Design Goals

- Make product growth knowledge easier to explore.
- Provide a focused conversational interface.
- Make long-form essay generation practical and structured.
- Allow users to revisit and manage saved work.
- Keep authentication and personal data handling straightforward.
- Communicate errors clearly instead of presenting failed requests as successful results.

## 2. Main Interface

### Conversation Sidebar

- Displays saved conversations and generated essays.
- Allows users to reopen previous work.
- Provides conversation management controls.
- Separates conversation history from saved artifacts.

### Chat Workspace

- Provides a message input and conversation area.
- Renders assistant responses using Markdown.
- Supports transcript-backed answers.
- Displays useful loading and error feedback.
- Maintains the active conversation context.

### Ship 30 Workspace

- Accepts an essay topic and writing instructions.
- Generates structured long-form content.
- Organizes the output for readability and reuse.
- Supports saving generated essays as artifacts.

### Artifact Viewer

- Displays saved essay content.
- Preserves Markdown structure.
- Supports reviewing and reusing generated work.

### Authentication

- Supports account registration and login.
- Supports Google authentication when configured.
- Associates saved conversations and artifacts with authenticated users.

## 3. Interaction Principles

- Keep the primary workspace focused on the current task.
- Make chat and essay-generation workflows easy to distinguish.
- Preserve saved work when users navigate between sections.
- Provide clear confirmation for destructive actions.
- Preserve saved essays when their originating conversation is deleted.
- Avoid showing internal implementation details in user-facing responses.
- Communicate when a request fails or relevant information is unavailable.

## 4. Visual Design

The interface uses a dark workspace with a sidebar and a main content area.

The sidebar organizes conversations and saved essays. The main workspace prioritizes chat or essay content depending on the active workflow.

Assistant responses use Markdown formatting to improve readability, particularly for structured explanations, headings, and lists.

## 5. Error and Empty States

The interface should handle:

- Missing or invalid authentication.
- Backend connectivity failures.
- Missing Groq configuration.
- Model API errors and rate limits.
- Requests that return no useful transcript context.
- Empty conversation history.
- Empty saved artifact collections.
- Failed conversation or artifact operations.

## 6. Security and Accessibility

- API keys and private credentials must remain on the backend.
- User-specific records must be protected by ownership checks.
- Retrieved transcript content must be treated as untrusted context.
- Markdown rendering must not allow unsafe HTML execution.
- Inputs and controls should have clear labels.
- Text and controls should remain readable across supported screen sizes.

## 7. Current Scope

The current application includes:

- Conversational AI.
- Transcript-based retrieval.
- Long-form essay generation.
- User authentication.
- Conversation history.
- Saved artifacts.
- Individual conversation deletion.
- User-specific data isolation.
- SQLite and PostgreSQL database support.

The design document describes the intended experience and interaction principles. Any behavior not verified through testing should be treated as requiring further validation.
