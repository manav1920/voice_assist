"""
PromptBuilder
==============
Combines everything Gemini needs into ONE finished prompt string:

    System Prompt
    Communication Style Instructions
    Relevant User Memories
    Conversation History
    Latest User Message

Nothing upstream of GeminiService.generate_reply() should ever hand
Gemini raw pieces again - this class is the single seam between
"what we know" (system prompt, communication style, memory, history)
and "what we say to the model" (one prompt string).
"""


class PromptBuilder:

    def build(
        self,
        system_prompt: str,
        user_message: str,
        history: str = "",
        memory_context: str = "",
        communication_instructions: str = "",
    ) -> str:

        sections = [system_prompt.strip()]

        if communication_instructions:
            sections.append(communication_instructions.strip())

        if memory_context:
            sections.append(
                "What you know about this user (only bring these up if "
                "they're actually relevant to the message below):\n"
                f"{memory_context}"
            )

        if history:
            sections.append(f"Conversation so far:\n{history}")

        sections.append(f"User:\n{user_message}\n\nManasvi:")

        return "\n\n".join(sections)
