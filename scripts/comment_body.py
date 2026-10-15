"""Build bounded public comments; execution logs are explicitly opt-in."""

from __future__ import annotations

from html import escape

# Leave room for the trailing newline written by finalize.py.
MAX_COMMENT_LENGTH = 60000
TRUNCATION_NOTICE = "[Earlier execution log truncated; see the artifact for the full log.]\n"
OVERSIZE_NOTICE = (
    "Content is too long to publish here. See the uploaded artifacts "
    "in the linked Actions run for the complete content."
)


def build_comment(
    body: str,
    action_link: str,
    extra: str = "",
    *,
    execution_log: str | None = None,
    details_begin: str = "",
    details_end: str = "",
) -> str:
    footer = action_link + (f"\n\n{extra}" if extra else "")
    separator = "\n\n---\n\n"
    limit = MAX_COMMENT_LENGTH - 1
    if len(body + separator + footer) > limit:
        # Do not cut arbitrary answer Markdown inside a code fence or HTML tag.
        body = OVERSIZE_NOTICE
    if len(body + separator + footer) > limit:
        raise ValueError("Action link and extra-comment-content exceed the comment size budget.")

    log_block = ""
    if execution_log is not None:
        prefix = f"{details_begin}\n\n<pre><code>"
        suffix = f"</code></pre>\n\n{details_end}\n\n"
        budget = limit - len(body + separator + footer + prefix + suffix)
        if budget > len(TRUNCATION_NOTICE):
            escaped_log = escape(execution_log)
            if len(escaped_log) > budget:
                # Keep recent progress, without splitting escaped HTML entities.
                remaining = budget - len(TRUNCATION_NOTICE)
                tail = []
                for char in reversed(execution_log):
                    escaped_char = escape(char)
                    if len(escaped_char) > remaining:
                        break
                    tail.append(escaped_char)
                    remaining -= len(escaped_char)
                escaped_log = TRUNCATION_NOTICE + "".join(reversed(tail))
            log_block = prefix + escaped_log + suffix

    return body + separator + log_block + footer
