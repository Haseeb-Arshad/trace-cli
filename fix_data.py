from src import database as db
from datetime import date

def fix():
    print("Connecting to DB...")
    conn = db.get_connection()
    
    # 1. Update activity_log
    cursor = conn.execute(
        "UPDATE activity_log SET category = '💻 Development' WHERE app_name IN ('Antigravity.exe', 'python.exe', 'code.exe')"
    )
    print(f"Updated {cursor.rowcount} rows in activity_log.")
    
    # 2. Update app_usage_history
    cursor = conn.execute(
        "UPDATE app_usage_history SET category = '💻 Development', role = 'IDE' WHERE app_name IN ('Antigravity.exe', 'python.exe', 'code.exe')"
    )
    print(f"Updated {cursor.rowcount} rows in app_usage_history.")
    
    conn.commit()

    # 3. Refresh daily stats for today
    print("Refreshing daily stats...")
    db.upsert_daily_stats(date.today())
    print("Done!")

if __name__ == "__main__":
    fix()
