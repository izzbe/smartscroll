"""Script rewriting prompt for Gemma 4."""

SCRIPT_PROMPT_V = 2

SCRIPT_REWRITE_SYSTEM = """You rewrite academic/technical content into TikTok-style narration scripts.

Rules:
- Hook in first 8 words ("Here's why X is wild:", "Most people get Y wrong:")
- Conversational, second-person, present tense
- No filler intros ("In this video we'll explore...")
- End on a payoff or cliffhanger, never a summary
- Plain text only, no markdown/headers/bullets
"""

SCRIPT_REWRITE_USER = """Rewrite this content as a TikTok narration:

{chunk_text}
"""
