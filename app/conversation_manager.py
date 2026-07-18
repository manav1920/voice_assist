class ConversationManager:

    def __init__(self):

        self.history = []

    def add_user_message(self, message: str):

        self.history.append({
            "role": "user",
            "content": message
        })

    def add_assistant_message(self, message: str):

        self.history.append({
            "role": "assistant",
            "content": message
        })

    def get_history(self):

        return self.history

    def get_formatted_history(self):

        conversation = ""

        for message in self.history:

            role = message["role"].capitalize()

            conversation += f"{role}: {message['content']}\n"

        return conversation

    def clear_history(self):

        self.history.clear()