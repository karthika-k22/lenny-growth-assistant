\# Design: The Lenny Growth Assistant



\## 1. Design Goals



\- Make asking questions about podcast transcripts simple.

\- Keep the chat interface readable and easy to navigate.

\- Make generated essays easy to review, copy, and reuse.

\- Provide clear access to model selection and saved work.

\- Support local inference to reduce dependence on paid cloud APIs.



\## 2. Main Interface



\### Conversation Sidebar

\- Displays recent saved conversations and generated essays.

\- Allows the user to reopen saved work.

\- Includes a control to collapse or resize the sidebar.

\- Provides a refresh action for saved history.



\### Chat Workspace

\- Provides a message input and conversation area.

\- Displays assistant responses as Markdown.

\- Shows transcript source references when available.

\- Provides a provider selector for choosing the inference option.



\### Ship 30 for 30 Workspace

\- Accepts an essay topic and intended audience.

\- Requests a structured long-form essay.

\- Organizes the result into a title, opening hook, narrative progression, and actionable takeaway.

\- Saves the generated essay as an artifact.



\### Artifact Viewer

\- Displays the generated Markdown alongside its source text.

\- Supports copying or downloading the content.

\- Allows users to review the essay without losing its structure.



\## 3. Interaction Principles



\- Keep the main writing and conversation areas visible.

\- Make provider selection explicit.

\- Preserve saved conversations so users can return to earlier discussions.

\- Show useful feedback when requests fail.

\- Avoid presenting unavailable transcript evidence as verified fact.

\- Keep the interface focused on the user's current task.



\## 4. Visual Design



The interface uses a dark, compact workspace with a sidebar and a main content area. The sidebar separates conversation history from generated essays. The primary workspace gives the chat or essay content most of the available space.



The essay view uses a side-by-side layout so the rendered Markdown and its source can be reviewed together.



\## 5. Error and Empty States



The interface should communicate when:

\- The selected model provider is unavailable.

\- A cloud API key is missing or the provider quota is exhausted.

\- Transcript retrieval returns no useful context.

\- A request times out or fails.

\- No conversations or saved artifacts exist yet.



\## 6. Security and Accessibility



\- Do not expose API keys in the frontend or source control.

\- Treat retrieved transcript content as untrusted input.

\- Sanitize and isolate generated HTML before rendering it.

\- Provide clear labels for inputs and controls.

\- Maintain readable contrast and usable controls at different screen sizes.



\## 7. Current Scope



The current implementation provides chat, model selection, transcript retrieval, essay generation, Markdown viewing, and local history persistence.



The design document describes the intended interaction and safety principles. Any behavior not verified in the running application should be treated as a requirement for further testing rather than a completed feature.



