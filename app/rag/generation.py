from __future__ import annotations

import logging
import re
from typing import Iterable

from huggingface_hub import InferenceClient
from langchain.prompts import PromptTemplate

from app.config import settings

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = PromptTemplate.from_template(
    """
You are an academic assistant helping a university class.
Use only the provided context.
If context is insufficient, explicitly say what is missing.

Task: Write a concise, faithful summary for students in 5-8 bullet points.
Preserve key facts, definitions, and any equations.

Context:
{context}

Summary:
""".strip()
)

QA_PROMPT = PromptTemplate.from_template(
    """
You are an academic assistant helping students understand a professor's uploaded document.
Answer the question using only the provided context.
If the context does not contain the answer, say: "I cannot answer from the provided file context."

Question:
{question}

Context:
{context}

Answer:
""".strip()
)


class RagGenerator:
    """Generates summaries and answers from retrieved context chunks."""

    def __init__(self) -> None:
        self._client = None
        if settings.hf_api_token:
            self._client = InferenceClient(token=settings.hf_api_token)

    def generate_summary(self, contexts: Iterable[str]) -> tuple[str, str]:
        context_list = [chunk for chunk in contexts if chunk and chunk.strip()]
        raw_context = self._join_contexts(context_list, preserve_lines=True)
        if not raw_context:
            return "No relevant content was found to summarize.", "extractive"
        context = self._normalize_whitespace(raw_context)

        if not self._client:
            return self._extractive_summary(raw_context), "extractive"

        # Summarization task is the most stable free endpoint for this workload.
        # We defensively limit payload size to avoid HF model position-index errors.
        safe_context = self._truncate_input(context)
        try:
            output = self._generate_summary_with_retries(safe_context)
            return self._format_summary(output), "rag"
        except Exception as exc:
            logger.warning("RAG summary generation failed; falling back to extractive: %s", exc)
            return self._extractive_summary(raw_context), "extractive"

    def answer_question(self, question: str, contexts: Iterable[str]) -> tuple[str, str]:
        context = self._join_contexts(contexts, preserve_lines=False)
        if not context:
            return "I cannot answer from the provided file context.", "extractive"

        if not self._client:
            return self._fallback_answer(question, context), "extractive"

        prompt = QA_PROMPT.format(question=question, context=self._truncate_input(context))
        try:
            output = self._generate_text_with_retries(prompt=prompt, text_fallback=context)
            return self._normalize_whitespace(output), "rag"
        except Exception as exc:
            logger.warning("RAG question answering failed; falling back to extractive: %s", exc)
            return self._fallback_answer(question, context), "extractive"

    def _generate_summary_with_retries(self, context: str) -> str:
        prompt = SUMMARY_PROMPT.format(context=context)
        return self._generate_text_with_retries(prompt=prompt, text_fallback=context)

    def _generate_text_with_retries(self, prompt: str, text_fallback: str) -> str:
        prompt_candidates = [self._truncate_input(prompt)]
        if len(prompt) > 1500:
            prompt_candidates.append(prompt[:1500].rstrip())
        if len(prompt) > 1000:
            prompt_candidates.append(prompt[:1000].rstrip())

        last_exc: Exception | None = None
        for candidate in prompt_candidates:
            try:
                return self._generate_text(candidate)
            except Exception as exc:  # pragma: no cover - depends on remote HF behavior
                last_exc = exc
                continue

        logger.warning("Prompt-based generation failed; trying summarization fallback: %s", last_exc)
        return self._summarize_with_retries(self._truncate_input(text_fallback))

    def _generate_text(self, prompt: str) -> str:
        if not self._client:
            return ""
        result = self._client.text_generation(
            prompt,
            model=settings.rag_generation_model,
            max_new_tokens=settings.rag_generation_max_tokens,
            do_sample=False,
            return_full_text=False,
        )
        return str(result).strip()

    def _summarize(self, text: str) -> str:
        if not self._client:
            return ""
        result = self._client.summarization(text, model=settings.rag_generation_model)
        return result.summary_text

    def _summarize_with_retries(self, text: str) -> str:
        candidates = [text]
        if len(text) > 1200:
            candidates.append(text[:1200].rstrip())
        if len(text) > 800:
            candidates.append(text[:800].rstrip())

        last_exc: Exception | None = None
        for candidate in candidates:
            try:
                return self._summarize(candidate)
            except Exception as exc:  # pragma: no cover - depends on remote HF behavior
                last_exc = exc
                continue
        if last_exc:
            raise last_exc
        raise RuntimeError("No candidate text available for summarization")

    @staticmethod
    def _truncate_input(text: str) -> str:
        max_chars = settings.summary_max_input_chars
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip()

    @staticmethod
    def _join_contexts(contexts: Iterable[str], preserve_lines: bool = False) -> str:
        text = "\n\n".join(chunk.strip() for chunk in contexts if chunk and chunk.strip())
        return RagGenerator._normalize_whitespace(text, preserve_lines=preserve_lines)

    @staticmethod
    def _normalize_whitespace(text: str, preserve_lines: bool = False) -> str:
        cleaned = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
        if preserve_lines:
            lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.split("\n")]
            cleaned = "\n".join(line for line in lines if line)
        else:
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        cleaned = re.sub(r"([\[(])\s+", r"\1", cleaned)
        cleaned = re.sub(r"\s+([\])])", r"\1", cleaned)
        return cleaned

    @staticmethod
    def _format_summary(text: str) -> str:
        cleaned = RagGenerator._normalize_whitespace(text, preserve_lines=True)
        if not cleaned.strip():
            return "No relevant content was found to summarize."

        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if lines and all(line.startswith(("-", "*", "•")) for line in lines):
            return "\n".join(lines[:8])

        flat = RagGenerator._normalize_whitespace(cleaned)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]
        if not sentences:
            return flat
        top = sentences[:8]
        return "\n".join(f"- {sentence}" for sentence in top)

    @staticmethod
    def _extractive_summary(text: str) -> str:
        cleaned = RagGenerator._normalize_whitespace(text, preserve_lines=True)
        if not cleaned:
            return "No relevant content was found to summarize."

        lines = [line.strip(" -*•\t") for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return "No relevant content was found to summarize."

        required_items: list[str] = []
        allowed_items: list[str] = []
        blocked_items: list[str] = []
        intro_lines: list[str] = []

        section: str | None = None
        for line in lines:
            low = line.lower()

            if "not permitted" in low:
                section = "blocked"
                if not intro_lines:
                    intro_lines.append(line)
                continue
            if "permitted" in low:
                section = "allowed"
                if not intro_lines:
                    intro_lines.append(line)
                continue

            if " for " in low and len(required_items) < 8:
                required_items.append(line)
                continue

            if section == "allowed" and len(allowed_items) < 16:
                allowed_items.append(line)
                continue
            if section == "blocked" and len(blocked_items) < 16:
                blocked_items.append(line)
                continue

            if len(intro_lines) < 2 and len(line.split()) >= 6:
                intro_lines.append(line)

        bullets: list[str] = []
        if intro_lines:
            bullets.append(f"- Overview: {' '.join(intro_lines[:2])}")
        if required_items:
            bullets.append(f"- Required stack: {'; '.join(required_items[:5])}")
        if allowed_items:
            bullets.append(f"- Permitted tools include: {', '.join(allowed_items[:12])}")
        if blocked_items:
            bullets.append(f"- Not permitted: {', '.join(blocked_items[:12])}")

        if bullets:
            return "\n".join(bullets)

        flat = RagGenerator._normalize_whitespace(cleaned)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]
        if not sentences:
            words = flat.split()
            extract = " ".join(words[: settings.summary_extractive_words]).strip()
            if len(words) > settings.summary_extractive_words:
                extract += " ..."
            return f"- {extract}" if extract else "No relevant content was found to summarize."

        top = sentences[:6]
        return "\n".join(f"- {sentence}" for sentence in top)

    @staticmethod
    def _fallback_answer(question: str, context: str) -> str:
        del question
        words = context.split()
        extract = " ".join(words[: min(120, len(words))])
        return (
            "[Extractive fallback - set HF_API_TOKEN to enable remote HuggingFace generation] "
            + extract
        )
