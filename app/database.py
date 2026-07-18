from contextlib import contextmanager

from mysql.connector import Error
from mysql.connector import pooling

from app.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)


class DatabaseManager:
    """
    MySQL stores all application data.
    Supabase is used ONLY for authentication.
    """

    _pool = None

    def __init__(self):

        if DatabaseManager._pool is None:

            DatabaseManager._pool = pooling.MySQLConnectionPool(
                pool_name="manasvi_pool",
                pool_size=5,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
            )

            print("✅ Connected to MySQL")

    @contextmanager
    def get_cursor(self, dictionary=True):

        connection = DatabaseManager._pool.get_connection()

        cursor = connection.cursor(dictionary=dictionary)

        try:

            yield cursor

            connection.commit()

        except Error:

            connection.rollback()

            raise

        finally:

            cursor.close()
            connection.close()

    # =====================================================
    # USERS
    # =====================================================

    def get_user_by_id(self, user_id: int):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )

            return cursor.fetchone()

    def get_user_by_supabase_id(self, supabase_user_id: str):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE supabase_user_id = %s
                """,
                (supabase_user_id,),
            )

            return cursor.fetchone()

    def get_user_by_email(self, email: str):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM users
                WHERE email = %s
                """,
                (email,),
            )

            return cursor.fetchone()

    def update_supabase_user_id(self, user_id: int, supabase_user_id: str):
        """
        Links an existing MySQL user (originally created via a
        different login method, e.g. email/password) to a Supabase
        account - used when someone with an existing email later logs
        in via Google for the first time. Also stamps last_login,
        since this always happens as part of a successful login.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                UPDATE users
                SET
                    supabase_user_id = %s,
                    last_login = NOW()
                WHERE id = %s
                """,
                (supabase_user_id, user_id),
            )

        return self.get_user_by_id(user_id)

    def create_user(
        self,
        supabase_user_id: str,
        email: str,
        first_name: str = None,
        last_name: str = None,
        phone_number: str = None,
    ):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO users (
                    supabase_user_id,
                    first_name,
                    last_name,
                    email,
                    phone_number,
                    last_login
                )
                VALUES (
                    %(supabase_user_id)s,
                    %(first_name)s,
                    %(last_name)s,
                    %(email)s,
                    %(phone_number)s,
                    NOW()
                )
                """,
                {
                    "supabase_user_id": supabase_user_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone_number": phone_number,
                },
            )

            user_id = cursor.lastrowid

        return self.get_user_by_id(user_id)

    def update_last_login(self, user_id: int):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                UPDATE users
                SET last_login = NOW()
                WHERE id = %s
                """,
                (user_id,),
            )

    def count_users(self):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM users
                """
            )

            row = cursor.fetchone()

            return row["total"] if row else 0

    def mark_onboarding_completed(self, user_id: int):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                UPDATE users
                SET onboarding_completed = TRUE
                WHERE id = %s
                """,
                (user_id,),
            )

    # =====================================================
    # MEMORY
    # =====================================================
    # Onboarding answers (and, later, any other long-term memory)
    # live here - one row per fact, never inside `users`.

    def save_memory_bulk(self, user_id: int, entries: list[dict]):
        """
        entries: [{"category": "identity", "key_name": "preferred_name", "value": "Manav"}, ...]

        Upserts each entry - if the user already has a memory row for
        that key_name (e.g. they went Back and changed an answer, or
        autosave ran twice for the same step), it's updated in place
        rather than duplicated, relying on the UNIQUE(user_id, key_name)
        constraint already in the schema.
        """

        if not entries:
            return

        with self.get_cursor() as cursor:

            for entry in entries:

                cursor.execute(
                    """
                    INSERT INTO memory (user_id, category, key_name, value)
                    VALUES (%(user_id)s, %(category)s, %(key_name)s, %(value)s)
                    ON DUPLICATE KEY UPDATE
                        value = VALUES(value),
                        category = VALUES(category)
                    """,
                    {
                        "user_id": user_id,
                        "category": entry["category"],
                        "key_name": entry["key_name"],
                        "value": entry["value"],
                    },
                )

    def get_memory(self, user_id: int):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT category, key_name, value
                FROM memory
                WHERE user_id = %s
                """,
                (user_id,),
            )

            return cursor.fetchall()

    # =====================================================
    # CONVERSATIONS
    # =====================================================

    def create_conversation(self, user_id: int, title: str = "New Conversation"):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO conversations (user_id, title)
                VALUES (%s, %s)
                """,
                (user_id, title),
            )

            conversation_id = cursor.lastrowid

        return self.get_conversation_by_id(conversation_id, user_id)

    def get_conversation_by_id(self, conversation_id: int, user_id: int):
        """
        Always scoped to user_id so one account can never load, rename,
        or delete another account's conversation.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )

            return cursor.fetchone()

    def get_latest_conversation(self, user_id: int):
        """
        Most recently active conversation for this user, used to decide
        what should be "active" right after login. Returns None if the
        user has no conversations yet.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT *
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id,),
            )

            return cursor.fetchone()

    def list_conversations(self, user_id: int):
        """
        Newest-first. Kept as a flat list - grouping into
        Today / Yesterday / Previous 7 Days / Older is a presentation
        concern and is done by the caller (frontend), not here.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )

            return cursor.fetchall()

    def update_conversation_title(self, conversation_id: int, user_id: int, title: str):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                UPDATE conversations
                SET title = %s
                WHERE id = %s AND user_id = %s
                """,
                (title, conversation_id, user_id),
            )

            return cursor.rowcount > 0

    def touch_conversation(self, conversation_id: int, user_id: int):
        """
        Bumps updated_at. MySQL's ON UPDATE CURRENT_TIMESTAMP only
        fires on an actual UPDATE to the row, so this is called
        explicitly whenever a message is added to the conversation -
        that's what keeps "most recently active" (and therefore
        sidebar ordering) accurate.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )

    def delete_conversation(self, conversation_id: int, user_id: int):
        """
        Messages cascade-delete automatically via the FK's
        ON DELETE CASCADE. Returns True if a row was actually deleted.
        """

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                DELETE FROM conversations
                WHERE id = %s AND user_id = %s
                """,
                (conversation_id, user_id),
            )

            return cursor.rowcount > 0

    # =====================================================
    # MESSAGES
    # =====================================================

    def add_message(
        self,
        conversation_id: int,
        role: str,
        message: str,
        model: str = None,
        token_count: int = 0,
    ):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO messages (conversation_id, role, message, model, token_count)
                VALUES (%(conversation_id)s, %(role)s, %(message)s, %(model)s, %(token_count)s)
                """,
                {
                    "conversation_id": conversation_id,
                    "role": role,
                    "message": message,
                    "model": model,
                    "token_count": token_count,
                },
            )

            return cursor.lastrowid

    def get_messages(self, conversation_id: int, limit: int = None):
        """
        Ordered oldest -> newest, exactly how a chat transcript reads.
        `limit` (when given) returns only the most recent N messages,
        still in oldest -> newest order - useful later if a
        conversation grows long enough that the full transcript
        shouldn't be replayed into every prompt.
        """

        with self.get_cursor() as cursor:

            if limit:
                cursor.execute(
                    """
                    SELECT id, conversation_id, role, message, model, token_count, created_at
                    FROM messages
                    WHERE conversation_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (conversation_id, limit),
                )
                rows = cursor.fetchall()
                rows.reverse()
                return rows

            cursor.execute(
                """
                SELECT id, conversation_id, role, message, model, token_count, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (conversation_id,),
            )

            return cursor.fetchall()

    def count_messages(self, conversation_id: int):

        with self.get_cursor() as cursor:

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM messages
                WHERE conversation_id = %s
                """,
                (conversation_id,),
            )

            row = cursor.fetchone()

            return row["total"] if row else 0

    # =====================================================
    # HEALTH CHECK
    # =====================================================

    def ping(self):

        try:

            connection = DatabaseManager._pool.get_connection()

            connection.ping(reconnect=True)

            connection.close()

            return True

        except Exception:

            return False