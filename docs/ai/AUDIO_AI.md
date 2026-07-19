# Audio and AI Concept

EventMonitorAI combines pretrained audio classification with project-specific supervised learning.

## Learning loop

1. Import or receive audio and sound-level data.
2. Detect candidate segments using level changes and acoustic features.
3. Let a model propose one or more labels.
4. A reviewer confirms, corrects or rejects the proposal.
5. Only confirmed labels enter the training set.
6. Train and evaluate a new model version against a separate validation set.

## Quality principles

- Keep uncertain and ambiguous samples explicitly marked.
- Include negative examples such as vehicles, wind, music and normal speech.
- Split training and validation data by recording session, not random snippets from the same recording.
- Store model version, confidence and feature configuration with every prediction.
