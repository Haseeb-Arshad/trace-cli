import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
import random

DB_PATH = Path.home() / ".tracecli" / "trace.db"

def inject_mock_data():
    conn = sqlite3.connect(str(DB_PATH))
    target_date = date.today()
    date_str = target_date.isoformat()
    
    apps = [
        ("Visual Studio Code", "💻 Development"),
        ("Google Chrome", "📚 Research"),
        ("Terminal", "💻 Development"),
        ("Slack", "💬 Communication"),
        ("Spotify", "🎵 Entertainment"),
    ]
    
    # Clear today's mock data to be safe (optional)
    # conn.execute("DELETE FROM activity_log WHERE start_time LIKE ?", (date_str + "%",))
    
    for hour in range(8, 20):  # 8 AM to 8 PM
        # Generate 2-4 activities per hour
        for _ in range(random.randint(2, 4)):
            app_name, category = random.choice(apps)
            duration = random.randint(300, 1800) # 5 to 30 mins
            
            start_time = datetime(target_date.year, target_date.month, target_date.day, hour, random.randint(0, 45))
            end_time = start_time + timedelta(seconds=duration)
            
            conn.execute(
                """
                INSERT INTO activity_log (app_name, window_title, start_time, end_time, duration_seconds, category)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (app_name, f"Working on {app_name} things", start_time.isoformat(), end_time.isoformat(), duration, category)
            )
            
    conn.commit()
    conn.close()
    print("Mock data injected for", date_str)

if __name__ == "__main__":
    inject_mock_data()
