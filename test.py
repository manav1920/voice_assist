from app.database import DatabaseManager

db = DatabaseManager()

db.connect()

connection = db.get_connection()

if connection and connection.is_connected():
    print("✅ Database Connection Successful!")
else:
    print("❌ Database Connection Failed!")

db.disconnect()