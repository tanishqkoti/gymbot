from flask import Flask, request, jsonify
import requests
import os
import pytz
import threading
import sqlite3
import random
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "gymbot123")

IST = pytz.timezone("Asia/Kolkata")
user_sessions = {}
reminder_sent_today = {}
motivation_sent_today = {}
weekly_report_sent = {}

DB_FILE = "gymbot.db"

WORKOUT_SCHEDULE = {
    0: "Chest and Triceps 💪",
    1: "Back and Biceps 🏋️",
    2: "Legs and Glutes 🦵",
    3: "Shoulders and Arms 🏆",
    4: "Core and Abs 🔥",
    5: "Cardio / Full Body 🏃",
    6: "Rest and Recovery 😴"
}

WORKOUT_IMAGES = {
    "1": "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?w=800",
    "2": "https://images.unsplash.com/photo-1603287681836-b174ce5074c2?w=800",
    "3": "https://images.unsplash.com/photo-1434682881908-b43d0467b798?w=800",
    "4": "https://images.unsplash.com/photo-1532029837206-abbe2b7620e3?w=800",
    "5": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=800",
    "6": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=800",
}

MOTIVATION_IMAGES = [
    "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800",
    "https://images.unsplash.com/photo-1574680096145-d05b474e2155?w=800",
    "https://images.unsplash.com/photo-1526506118085-60ce8714f8c5?w=800",
    "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?w=800",
    "https://images.unsplash.com/photo-1549060279-7e168fcee0c2?w=800",
]

DIET_IMAGES = {
    "1": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=800",
    "2": "https://images.unsplash.com/photo-1547496502-affa22d38842?w=800",
    "3": "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=800",
    "4": "https://images.unsplash.com/photo-1559847844-5315695dadae?w=800",
    "5": "https://images.unsplash.com/photo-1532550907401-a500c9a57435?w=800",
    "6": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=800",
}

# ─── DATABASE SETUP ───────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        first_seen TEXT,
        last_active TEXT,
        message_count INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders (
        phone TEXT PRIMARY KEY,
        hour INTEGER,
        minute INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT,
        date TEXT,
        weight REAL
    )''')
    conn.commit()
    conn.close()

def get_conn():
    return sqlite3.connect(DB_FILE)

def upsert_user(phone):
    now = datetime.now(IST).strftime("%d %b %Y %H:%M")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT phone FROM users WHERE phone=?", (phone,))
    if c.fetchone():
        c.execute("UPDATE users SET last_active=?, message_count=message_count+1 WHERE phone=?", (now, phone))
    else:
        c.execute("INSERT INTO users (phone, first_seen, last_active, message_count) VALUES (?,?,?,1)", (phone, now, now))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT phone FROM users")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_reminder(phone, hour):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO reminders (phone, hour, minute) VALUES (?,?,0)", (phone, hour))
    conn.commit()
    conn.close()

def delete_reminder(phone):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM reminders WHERE phone=?", (phone,))
    conn.commit()
    conn.close()

def get_all_reminders():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT phone, hour, minute FROM reminders")
    rows = c.fetchall()
    conn.close()
    return {r[0]: {"hour": r[1], "minute": r[2]} for r in rows}

def has_reminder(phone):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT phone FROM reminders WHERE phone=?", (phone,))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_progress_entry(phone, date, weight):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO progress (phone, date, weight) VALUES (?,?,?)", (phone, date, weight))
    conn.commit()
    conn.close()

def get_progress_entries(phone):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT date, weight FROM progress WHERE phone=? ORDER BY id ASC", (phone,))
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "weight": r[1]} for r in rows]

# ─── KEEP ALIVE ───────────────────────────────────────────────

def keep_alive():
    while True:
        try:
            url = os.getenv("RENDER_EXTERNAL_URL", "https://gymbot-2cr9.onrender.com")
            requests.get(url + "/", timeout=10)
            print("Keep alive ping sent!")
        except Exception as e:
            print("Keep alive error:", e)
        import time
        time.sleep(600)

# ─── AI FUNCTIONS ─────────────────────────────────────────────

def ask_ai(question):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are GymBot, a professional fitness coach. Only answer fitness, gym, workout, diet, nutrition, weight loss, muscle gain questions. Keep answers short and practical under 200 words. If asked something unrelated to fitness, say you only help with fitness topics. Always end with a motivational line."},
                {"role": "user", "content": question}
            ]
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=10)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip() + "\n\n_Send 0 for Main Menu_ 💪"
        else:
            return "AI is temporarily unavailable. Try again! 💪\n\nSend 0 for Main Menu"
    except Exception as e:
        print("AI Error: " + str(e))
        return "Sorry, could not process that. Send 0 for the main menu."

def ask_ai_calories(food):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a nutrition expert. When given food items, calculate and list the calories for each item and give a total. Format: 🍽️ Calorie Count:\n• item = X kcal\n🔥 Total = X kcal\n[one tip]"},
                {"role": "user", "content": f"Calculate calories for: {food}"}
            ]
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=10)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip() + "\n\n_Send 18 for more_\n_Send 0 for Main Menu_ 💪"
        else:
            return "Could not calculate calories. Try again! 💪"
    except Exception as e:
        return "Sorry, could not process that. Send 0 for the main menu."

# ─── SEND FUNCTIONS ───────────────────────────────────────────

def send_message(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=data)

def send_image(phone, image_url, caption=""):
    try:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
        data = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "image",
            "image": {"link": image_url, "caption": caption}
        }
        requests.post(url, headers=headers, json=data)
    except Exception as e:
        print("Image send error:", e)

# ─── PROGRESS MESSAGE ─────────────────────────────────────────

def get_progress_message(phone, new_weight):
    now = datetime.now(IST)
    today = now.strftime("%d %b %Y")
    save_progress_entry(phone, today, new_weight)
    entries = get_progress_entries(phone)
    msg = f"📊 *Progress Saved!*\n\nDate: {today}\nWeight: {new_weight} kg\n\n"
    if len(entries) == 1:
        msg += "This is your first entry! Keep logging every week! 💪"
    else:
        msg += "*Your Journey:*\n"
        for entry in entries[-5:]:
            marker = "← Today" if entry == entries[-1] else ""
            msg += f"• {entry['date']} → {entry['weight']} kg {marker}\n"
        diff = round(new_weight - entries[0]["weight"], 1)
        msg += "\n"
        if diff < 0:
            msg += f"🎉 You lost *{abs(diff)} kg* since you started!"
        elif diff > 0:
            msg += f"📈 You gained *{diff} kg* since you started!"
        else:
            msg += "⚖️ Weight maintained! Stay consistent!"
    msg += "\n\nSend *19* to log weight!\nSend *0* for Main Menu"
    return msg

# ─── SCHEDULED JOBS ───────────────────────────────────────────

def send_weekly_progress_report():
    now = datetime.now(IST)
    if now.weekday() != 6 or now.hour != 9:
        return
    today_str = str(now.date())
    for phone in get_all_users():
        if weekly_report_sent.get(phone) == today_str:
            continue
        entries = get_progress_entries(phone)
        if len(entries) >= 2:
            latest, previous = entries[-1], entries[-2]
            diff = round(latest["weight"] - previous["weight"], 1)
            change_msg = f"🎉 Lost *{abs(diff)} kg*!" if diff < 0 else (f"📈 Gained *{diff} kg*!" if diff > 0 else "⚖️ Maintained!")
            msg = (f"📈 *Weekly Progress Report!*\n\nHappy Sunday! 🌟\n\n"
                   f"Last: {previous['date']} → {previous['weight']} kg\n"
                   f"Now: {latest['date']} → {latest['weight']} kg\n\n{change_msg}\n\n"
                   f"Journey: *{entries[0]['weight']} kg → {latest['weight']} kg*\n\nSend *19* to log!\nSend *0* for Menu 💪")
        else:
            msg = "📈 *Weekly Report!*\n\nHappy Sunday! 🌟\n\nSend *19* to log your weight! 💪"
        send_message(phone, msg)
        weekly_report_sent[phone] = today_str

def send_daily_reminders():
    now = datetime.now(IST)
    day_of_week = now.weekday()
    today = str(now.date())
    for phone, reminder in get_all_reminders().items():
        if reminder["hour"] == now.hour and now.minute < 5:
            if reminder_sent_today.get(phone) == today:
                continue
            if day_of_week == 6:
                msg = "🌟 Rest Day today — recover and stay hydrated! 💧\n\nSend 0 for Main Menu"
                send_message(phone, msg)
            else:
                workout_name = WORKOUT_SCHEDULE[day_of_week]
                msg = (f"🔔 *GymBot Reminder!*\n\nTime for your workout!\n\n"
                       f"Today: *{workout_name}*\n\nSend *1* for workout plan!\nLet's crush it! 💪🔥")
                img_key = str(day_of_week + 1) if day_of_week < 6 else "6"
                if img_key in WORKOUT_IMAGES:
                    send_image(phone, WORKOUT_IMAGES[img_key], msg)
                else:
                    send_message(phone, msg)
            reminder_sent_today[phone] = today

def send_morning_motivation():
    now = datetime.now(IST)
    today = str(now.date())
    if now.hour != 8:
        return
    quote = ask_ai("Give me one powerful gym motivational quote. Under 3 lines. No menu text.")
    img_url = random.choice(MOTIVATION_IMAGES)
    msg = f"🌅 *Good Morning!*\n\n{quote}\n\n💪 Let's crush today!\nSend *0* for Main Menu"
    for phone in get_all_users():
        if motivation_sent_today.get(phone) == today:
            continue
        send_image(phone, img_url, msg)
        motivation_sent_today[phone] = today

# ─── BROADCAST ────────────────────────────────────────────────

@app.route('/broadcast', methods=['POST'])
def broadcast():
    password = request.form.get('key', '')
    if password != ADMIN_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 401

    message = request.form.get('message', '').strip()
    if not message:
        return jsonify({"error": "Message is empty"}), 400

    users = get_all_users()
    sent = 0
    failed = 0
    for phone in users:
        try:
            send_message(phone, message)
            sent += 1
        except:
            failed += 1

    return jsonify({"success": True, "sent": sent, "failed": failed})

# ─── ADMIN PANEL ──────────────────────────────────────────────

@app.route('/admin')
def admin_panel():
    password = request.args.get('key', '')
    if password != ADMIN_PASSWORD:
        return '''
        <html><head><title>GymBot Admin</title>
        <style>
        body{font-family:Arial,sans-serif;background:#1a1a2e;color:white;
             display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
        .box{background:#16213e;padding:40px;border-radius:12px;text-align:center}
        input{padding:12px;border-radius:8px;border:none;margin:10px 0;width:250px;font-size:16px;text-align:center}
        button{background:#0f3460;color:white;padding:12px 30px;border:none;border-radius:8px;cursor:pointer;font-size:16px;margin-top:10px}
        button:hover{background:#00d4aa}
        </style></head>
        <body><div class="box">
        <h2>🏋️ GymBot Admin</h2><p>Enter admin password</p>
        <form method="get">
        <input type="password" name="key" placeholder="Password"><br>
        <button type="submit">Login</button>
        </form></div></body></html>
        ''', 401

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM reminders")
    total_reminders = c.fetchone()[0]
    c.execute("SELECT SUM(message_count) FROM users")
    total_messages = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(DISTINCT phone) FROM progress")
    tracking_users = c.fetchone()[0]
    c.execute("SELECT phone, first_seen, last_active, message_count FROM users ORDER BY message_count DESC")
    users = c.fetchall()
    conn.close()

    all_reminders = get_all_reminders()
    users_html = ""
    for u in users:
        phone_hidden = u[0][:4] + "****" + u[0][-3:]
        has_rem = "🔔 Yes" if u[0] in all_reminders else "❌ No"
        prog = get_progress_entries(u[0])
        weight_info = f"{prog[-1]['weight']} kg" if prog else "—"
        users_html += f"""
        <tr>
            <td>{phone_hidden}</td>
            <td>{u[1]}</td>
            <td>{u[2]}</td>
            <td><b>{u[3]}</b></td>
            <td>{has_rem}</td>
            <td>{weight_info}</td>
        </tr>"""

    return f'''
    <html>
    <head>
        <title>GymBot Admin Panel</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            *{{box-sizing:border-box;margin:0;padding:0}}
            body{{font-family:Arial,sans-serif;background:#0f0f1a;color:#e0e0e0;padding:20px}}
            h1{{color:#00d4aa;margin-bottom:20px;font-size:28px}}
            h2{{color:#00d4aa;margin:30px 0 15px;font-size:20px}}
            .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:15px;margin-bottom:30px}}
            .card{{background:#1a1a2e;border-radius:12px;padding:20px;text-align:center;border:1px solid #00d4aa33}}
            .card .number{{font-size:42px;font-weight:bold;color:#00d4aa}}
            .card .label{{font-size:13px;color:#888;margin-top:5px}}
            table{{width:100%;border-collapse:collapse;background:#1a1a2e;border-radius:12px;overflow:hidden}}
            th{{background:#00d4aa22;color:#00d4aa;padding:12px 15px;text-align:left;font-size:13px}}
            td{{padding:12px 15px;border-bottom:1px solid #ffffff11;font-size:13px}}
            tr:hover td{{background:#ffffff08}}
            .refresh{{background:#00d4aa;color:#0f0f1a;padding:8px 20px;border-radius:8px;
                      text-decoration:none;font-weight:bold;display:inline-block;margin-bottom:20px;margin-right:10px}}
            .refresh:hover{{background:#00b894}}
            .broadcast-box{{background:#1a1a2e;border-radius:12px;padding:25px;margin-bottom:30px;border:1px solid #00d4aa33}}
            .broadcast-box textarea{{width:100%;background:#0f0f1a;color:#e0e0e0;border:1px solid #00d4aa44;
                                     border-radius:8px;padding:12px;font-size:14px;resize:vertical;min-height:100px;margin:10px 0}}
            .broadcast-box textarea:focus{{outline:none;border-color:#00d4aa}}
            .send-btn{{background:#00d4aa;color:#0f0f1a;padding:10px 25px;border:none;border-radius:8px;
                      cursor:pointer;font-size:15px;font-weight:bold}}
            .send-btn:hover{{background:#00b894}}
            .result{{margin-top:10px;padding:10px;border-radius:8px;font-size:14px;display:none}}
            .result.success{{background:#00d4aa22;color:#00d4aa;border:1px solid #00d4aa44}}
            .result.error{{background:#ff444422;color:#ff6666;border:1px solid #ff444444}}
            .footer{{text-align:center;color:#444;margin-top:30px;font-size:12px}}
        </style>
    </head>
    <body>
        <h1>🏋️ GymBot Admin Panel</h1>
        <a class="refresh" href="/admin?key={password}">🔄 Refresh</a>

        <div class="stats">
            <div class="card"><div class="number">{total_users}</div><div class="label">Total Users 👥</div></div>
            <div class="card"><div class="number">{total_messages}</div><div class="label">Total Messages 💬</div></div>
            <div class="card"><div class="number">{total_reminders}</div><div class="label">Active Reminders 🔔</div></div>
            <div class="card"><div class="number">{tracking_users}</div><div class="label">Tracking Weight 📊</div></div>
        </div>

        <h2>📢 Broadcast Message</h2>
        <div class="broadcast-box">
            <p style="color:#888;font-size:13px;margin-bottom:5px">Send a message to ALL {total_users} users at once</p>
            <textarea id="broadcastMsg" placeholder="Type your message here...
Example: 🎉 New feature added! Send 20 to check it out!"></textarea>
            <br>
            <button class="send-btn" onclick="sendBroadcast()">📢 Send to All Users</button>
            <div class="result" id="broadcastResult"></div>
        </div>

        <h2>👥 All Users</h2>
        <table>
            <thead><tr>
                <th>Phone</th><th>First Seen</th><th>Last Active</th>
                <th>Messages</th><th>Reminder</th><th>Last Weight</th>
            </tr></thead>
            <tbody>{users_html}</tbody>
        </table>

        <div class="footer">GymBot Admin Panel • {datetime.now(IST).strftime("%d %b %Y %H:%M")} IST</div>

        <script>
        function sendBroadcast() {{
            const msg = document.getElementById('broadcastMsg').value.trim();
            const resultDiv = document.getElementById('broadcastResult');
            if (!msg) {{
                resultDiv.className = 'result error';
                resultDiv.style.display = 'block';
                resultDiv.textContent = '❌ Please type a message first!';
                return;
            }}
            const btn = document.querySelector('.send-btn');
            btn.textContent = '⏳ Sending...';
            btn.disabled = true;
            const formData = new FormData();
            formData.append('key', '{password}');
            formData.append('message', msg);
            fetch('/broadcast', {{method: 'POST', body: formData}})
                .then(r => r.json())
                .then(data => {{
                    btn.textContent = '📢 Send to All Users';
                    btn.disabled = false;
                    if (data.success) {{
                        resultDiv.className = 'result success';
                        resultDiv.style.display = 'block';
                        resultDiv.textContent = '✅ Sent to ' + data.sent + ' users successfully!';
                        document.getElementById('broadcastMsg').value = '';
                    }} else {{
                        resultDiv.className = 'result error';
                        resultDiv.style.display = 'block';
                        resultDiv.textContent = '❌ Error: ' + (data.error || 'Something went wrong');
                    }}
                }})
                .catch(e => {{
                    btn.textContent = '📢 Send to All Users';
                    btn.disabled = false;
                    resultDiv.className = 'result error';
                    resultDiv.style.display = 'block';
                    resultDiv.textContent = '❌ Network error. Try again!';
                }});
        }}
        </script>
    </body>
    </html>
    '''

# ─── MENUS & CONTENT ──────────────────────────────────────────

def get_main_menu():
    return (
        "Welcome to GymBot! 🏋️\n\nI am your personal AI fitness assistant.\n\nReply with a number:\n\n"
        "1 - Workout Plans\n2 - Diet and Nutrition\n3 - BMI Calculator\n4 - Weekly Schedule\n"
        "5 - Membership Info\n6 - Exercise Tips\n7 - Supplement Guide\n8 - Motivational Quote\n"
        "9 - 30 Day Challenge\n10 - Calorie Calculator\n11 - Water Intake Calculator\n"
        "12 - Body Fat Calculator\n13 - Cardio Guide\n14 - Recovery and Sleep Tips\n"
        "15 - Ask AI (Any Fitness Question)\n16 - Set Workout Reminder 🔔\n"
        "17 - Cancel Reminder ❌\n18 - Calorie Counter 🍽️\n19 - Progress Tracker 📊\n"
        "0 - Main Menu (anytime)\n\nOr just TYPE any fitness question!"
    )

def get_workout_menu():
    return "Workout Plans\n\nChoose your target:\n\n1 - Chest and Triceps\n2 - Back and Biceps\n3 - Legs and Glutes\n4 - Shoulders and Arms\n5 - Core and Abs\n6 - Full Body\n0 - Back to Main Menu"

def get_diet_menu():
    return "Diet and Nutrition\n\nChoose a topic:\n\n1 - Weight Loss Diet\n2 - Muscle Gain Diet\n3 - Pre-Workout Meals\n4 - Post-Workout Meals\n5 - Protein Rich Foods\n6 - Hydration Tips\n0 - Back to Main Menu"

def get_workout(choice):
    workouts = {
        "1": "Chest and Triceps Workout\n\n- Bench Press: 4x10\n- Incline Dumbbell Press: 3x12\n- Cable Fly: 3x15\n- Tricep Pushdown: 3x12\n- Overhead Tricep Extension: 3x12\n\nDuration: 45-50 mins",
        "2": "Back and Biceps Workout\n\n- Pull-ups: 4x8\n- Bent Over Row: 4x10\n- Lat Pulldown: 3x12\n- Seated Cable Row: 3x12\n- Barbell Curl: 3x12\n- Hammer Curls: 3x12\n\nDuration: 45-50 mins",
        "3": "Legs and Glutes Workout\n\n- Barbell Squat: 4x10\n- Romanian Deadlift: 4x10\n- Leg Press: 3x15\n- Walking Lunges: 3x12\n- Leg Curl: 3x12\n- Calf Raises: 4x20\n\nDuration: 50-60 mins",
        "4": "Shoulders and Arms Workout\n\n- Overhead Press: 4x10\n- Lateral Raises: 3x15\n- Front Raises: 3x12\n- Barbell Curl: 3x12\n- Skull Crushers: 3x12\n\nDuration: 45 mins",
        "5": "Core and Abs Workout\n\n- Plank: 3x60sec\n- Crunches: 3x20\n- Leg Raises: 3x15\n- Russian Twists: 3x20\n- Mountain Climbers: 3x30sec\n\nDuration: 30 mins",
        "6": "Full Body Workout\n\n- Squats: 3x12\n- Push-ups: 3x15\n- Dumbbell Row: 3x12\n- Shoulder Press: 3x12\n- Plank: 3x45sec\n\nDuration: 45 mins"
    }
    return workouts.get(choice, None)

def get_diet(choice):
    diets = {
        "1": "Weight Loss Diet\n\nBreakfast: Oats + banana + black coffee\nLunch: 2 chapati + dal + salad\nSnack: Apple or nuts\nDinner: Grilled paneer/fish + salad\n\nTarget: 1500-1800 kcal\nDrink 3-4 litres water daily",
        "2": "Muscle Gain Diet\n\nBreakfast: 4 eggs + oats + banana + milk\nLunch: Rice + chicken + dal + veggies\nSnack: Peanut butter sandwich + shake\nDinner: Paneer curry + chapati\n\nTarget: 2500-3000 kcal\nDrink 4-5 litres water daily",
        "3": "Pre-Workout Meals\n\nEat 60-90 mins before:\n- Banana + peanut butter toast\n- Oats with honey\n- Brown rice + chicken\n- Dates + black coffee",
        "4": "Post-Workout Meals\n\nEat within 30-45 mins after:\n- Whey protein + banana\n- Eggs + brown bread\n- Chicken rice bowl\n- Paneer + chapati",
        "5": "Protein Rich Foods\n\nEggs: 6g each\nChicken breast: 31g/100g\nPaneer: 18g/100g\nDal: 9g/100g\nPeanuts: 25g/100g\n\nTarget: 1.6-2.2g per kg bodyweight",
        "6": "Hydration Tips\n\nDaily: 3-4 litres\nTraining day: 4-5 litres\n\n- 500ml after waking up\n- 250ml every 30 min during workout\n- 500ml after workout"
    }
    return diets.get(choice, None)

def get_weekly_schedule():
    return "Weekly Gym Schedule\n\nMonday - Chest and Triceps\nTuesday - Back and Biceps\nWednesday - Legs and Glutes\nThursday - Shoulders and Arms\nFriday - Core and Abs\nSaturday - Cardio / Full Body\nSunday - Rest and Recovery\n\nConsistency beats Intensity!"

def get_supplement_guide():
    return "Supplement Guide 💊\n\nBeginner:\n- Whey Protein: 1-2 scoops post workout\n- Creatine: 5g daily\n- Multivitamin: 1 daily\n\nIntermediate:\n- Pre-workout: 30 min before gym\n- BCAA: During workout\n- Fish Oil: 1g daily\n\nAdvanced:\n- Casein Protein: Before bed\n- Glutamine: Post workout\n\n⚠️ Food first, supplements second!\nSend 0 for Main Menu"

def get_30_day_challenge():
    return "30 Day Fitness Challenge 🔥\n\nWeek 1: 20 push-ups, 30 squats, 1 min plank daily\nWeek 2: 30 push-ups, 40 squats, 2 min plank daily\nWeek 3: 40 push-ups, 50 squats, 3 min plank daily\nWeek 4: 50 push-ups, 60 squats, 4 min plank daily\n\nConsistency is key! 💪\nSend 0 for Main Menu"

def get_cardio_guide():
    return "Cardio Guide 🏃\n\nWeight Loss: 30-45 min, 5 days/week, 60-70% max HR\nEndurance: 45-60 min long runs, 3-4 days/week\nHIIT: 20s sprint + 40s rest, 10-15 rounds, 20 mins\n\nBest: Running, Cycling, Swimming, Jump rope\n\nDo cardio AFTER weights!\nSend 0 for Main Menu"

def get_recovery_tips():
    return "Recovery and Sleep Tips 😴\n\nSleep: 7-9 hours, same time daily\nStretch 10 min after workout\nFoam roll sore muscles\nDrink 3-4 litres water\nEat protein within 30 min post workout\nAvoid alcohol\n\nMuscles grow during REST!\nSend 0 for Main Menu"

# ─── MESSAGE HANDLER ──────────────────────────────────────────

def handle_message(phone, message):
    upsert_user(phone)
    msg = message.strip()
    msg_lower = msg.lower()
    session = user_sessions.get(phone, {"state": "main"})

    if msg == "0":
        user_sessions[phone] = {"state": "main"}
        send_message(phone, get_main_menu())
        return

    if "stop reminder" in msg_lower or "cancel reminder" in msg_lower or msg == "17":
        if has_reminder(phone):
            delete_reminder(phone)
            if phone in reminder_sent_today:
                del reminder_sent_today[phone]
            send_message(phone, "✅ Reminder cancelled!\n\nSend 0 for Main Menu")
        else:
            send_message(phone, "You have no active reminder.\n\nSend 0 for Main Menu")
        return

    state = session.get("state", "main")

    if state == "main":
        if msg == "1":
            user_sessions[phone] = {"state": "workout"}
            send_message(phone, get_workout_menu())
        elif msg == "2":
            user_sessions[phone] = {"state": "diet"}
            send_message(phone, get_diet_menu())
        elif msg == "3":
            user_sessions[phone] = {"state": "bmi_weight"}
            send_message(phone, "BMI Calculator\n\nEnter your weight in kg (e.g. 70):")
        elif msg == "4":
            send_message(phone, get_weekly_schedule())
        elif msg == "5":
            send_message(phone, "Membership Info\n\nBasic Plan: Rs 800/month\nStandard Plan: Rs 1200/month\nPremium Plan: Rs 2000/month\n\nContact us to join!\nSend 0 for Main Menu")
        elif msg == "6":
            send_message(phone, ask_ai("Give me 5 important exercise tips for beginners"))
        elif msg == "7":
            send_message(phone, get_supplement_guide())
        elif msg == "8":
            quote = ask_ai("Give me a powerful motivational quote for gym and fitness. No menu text at end.")
            img_url = random.choice(MOTIVATION_IMAGES)
            send_image(phone, img_url, "💪 Daily Motivation!")
            send_message(phone, quote)
        elif msg == "9":
            send_message(phone, get_30_day_challenge())
        elif msg == "10":
            user_sessions[phone] = {"state": "calorie_gender"}
            send_message(phone, "Calorie Calculator\n\nEnter your gender:\n1 - Male\n2 - Female")
        elif msg == "11":
            user_sessions[phone] = {"state": "water_weight"}
            send_message(phone, "Water Intake Calculator\n\nEnter your weight in kg (e.g. 70):")
        elif msg == "12":
            user_sessions[phone] = {"state": "bodyfat_gender"}
            send_message(phone, "Body Fat Calculator\n\nEnter your gender:\n1 - Male\n2 - Female")
        elif msg == "13":
            send_message(phone, get_cardio_guide())
        elif msg == "14":
            send_message(phone, get_recovery_tips())
        elif msg == "15":
            user_sessions[phone] = {"state": "ask_ai"}
            send_message(phone, "🤖 Ask AI Mode\n\nType any fitness question!\n\nSend 0 to go back to Main Menu")
        elif msg == "16":
            user_sessions[phone] = {"state": "set_reminder"}
            send_message(phone, "🔔 Set Workout Reminder\n\nEnter hour in 24hr format (IST)\nExamples:\n- 6 = 6:00 AM\n- 7 = 7:00 AM\n- 18 = 6:00 PM")
        elif msg == "18":
            user_sessions[phone] = {"state": "calorie_counter"}
            send_message(phone, "🍽️ *Calorie Counter*\n\nType any food or meal!\n\nExamples:\n- 2 eggs and oats\n- rice 1 cup and chicken\n\nSend 0 to go back to Main Menu")
        elif msg == "19":
            user_sessions[phone] = {"state": "progress_weight"}
            entries = get_progress_entries(phone)
            if entries:
                last = entries[-1]
                send_message(phone, f"📊 *Progress Tracker*\n\nLast logged: {last['date']} → {last['weight']} kg\n\nEnter current weight in kg:\n\nSend 0 to cancel")
            else:
                send_message(phone, "📊 *Progress Tracker*\n\nTrack your weight journey here!\n\nEnter your current weight in kg:\n\nSend 0 to cancel")
        else:
            send_message(phone, ask_ai(msg))

    elif state == "workout":
        workout = get_workout(msg)
        if workout:
            if msg in WORKOUT_IMAGES:
                send_image(phone, WORKOUT_IMAGES[msg], workout)
            else:
                send_message(phone, workout)
            send_message(phone, "Reply 0 for Main Menu 💪")
        else:
            send_message(phone, get_workout_menu())

    elif state == "diet":
        diet = get_diet(msg)
        if diet:
            if msg in DIET_IMAGES:
                send_image(phone, DIET_IMAGES[msg], diet)
            else:
                send_message(phone, diet)
            send_message(phone, "Reply 0 for Main Menu 💪")
        else:
            send_message(phone, get_diet_menu())

    elif state == "bmi_weight":
        try:
            weight = float(msg)
            user_sessions[phone] = {"state": "bmi_height", "weight": weight}
            send_message(phone, "Now enter your height in cm (e.g. 175):")
        except:
            send_message(phone, "Please enter a valid weight (e.g. 70):")

    elif state == "bmi_height":
        try:
            height = float(msg) / 100
            weight = session.get("weight", 70)
            bmi = round(weight / (height ** 2), 1)
            if bmi < 18.5: category = "Underweight"
            elif bmi < 25: category = "Normal weight"
            elif bmi < 30: category = "Overweight"
            else: category = "Obese"
            user_sessions[phone] = {"state": "main"}
            send_message(phone, f"Your BMI: {bmi}\nCategory: {category}\n\nSend 0 for Main Menu")
        except:
            send_message(phone, "Please enter a valid height (e.g. 175):")

    elif state == "calorie_gender":
        if msg == "1":
            user_sessions[phone] = {"state": "calorie_weight", "gender": "male"}
            send_message(phone, "Enter your weight in kg:")
        elif msg == "2":
            user_sessions[phone] = {"state": "calorie_weight", "gender": "female"}
            send_message(phone, "Enter your weight in kg:")
        else:
            send_message(phone, "Enter 1 for Male or 2 for Female:")

    elif state == "calorie_weight":
        try:
            weight = float(msg)
            user_sessions[phone] = {**session, "state": "calorie_height", "weight": weight}
            send_message(phone, "Enter your height in cm:")
        except:
            send_message(phone, "Please enter a valid weight (e.g. 70):")

    elif state == "calorie_height":
        try:
            height = float(msg)
            user_sessions[phone] = {**session, "state": "calorie_age", "height": height}
            send_message(phone, "Enter your age:")
        except:
            send_message(phone, "Please enter a valid height (e.g. 175):")

    elif state == "calorie_age":
        try:
            age = int(msg)
            weight = session.get("weight", 70)
            height = session.get("height", 170)
            gender = session.get("gender", "male")
            if gender == "male":
                bmr = 10 * weight + 6.25 * height - 5 * age + 5
            else:
                bmr = 10 * weight + 6.25 * height - 5 * age - 161
            maintain = round(bmr * 1.55)
            lose = round(maintain - 500)
            gain = round(maintain + 500)
            user_sessions[phone] = {"state": "main"}
            send_message(phone, f"Calorie Results 🔥\n\nMaintain: {maintain} kcal/day\nLose weight: {lose} kcal/day\nGain muscle: {gain} kcal/day\n\nSend 0 for Main Menu")
        except:
            send_message(phone, "Please enter a valid age (e.g. 25):")

    elif state == "water_weight":
        try:
            weight = float(msg)
            water = round(weight * 0.033, 1)
            workout_water = round(water + 0.5, 1)
            user_sessions[phone] = {"state": "main"}
            send_message(phone, f"Water Intake 💧\n\nNormal day: {water} litres\nWorkout day: {workout_water} litres\n\nTip: Drink 500ml right after waking up!\nSend 0 for Main Menu")
        except:
            send_message(phone, "Please enter a valid weight (e.g. 70):")

    elif state == "bodyfat_gender":
        if msg == "1":
            user_sessions[phone] = {"state": "bodyfat_weight", "gender": "male"}
            send_message(phone, "Enter your weight in kg:")
        elif msg == "2":
            user_sessions[phone] = {"state": "bodyfat_weight", "gender": "female"}
            send_message(phone, "Enter your weight in kg:")
        else:
            send_message(phone, "Enter 1 for Male or 2 for Female:")

    elif state == "bodyfat_weight":
        try:
            weight = float(msg)
            user_sessions[phone] = {**session, "state": "bodyfat_height", "weight": weight}
            send_message(phone, "Enter your height in cm:")
        except:
            send_message(phone, "Please enter a valid weight (e.g. 70):")

    elif state == "bodyfat_height":
        try:
            height = float(msg)
            user_sessions[phone] = {**session, "state": "bodyfat_age", "height": height}
            send_message(phone, "Enter your age:")
        except:
            send_message(phone, "Please enter a valid height (e.g. 175):")

    elif state == "bodyfat_age":
        try:
            age = int(msg)
            weight = session.get("weight", 70)
            height = session.get("height", 170)
            gender = session.get("gender", "male")
            bmi = weight / ((height / 100) ** 2)
            if gender == "male":
                body_fat = round(1.20 * bmi + 0.23 * age - 16.2, 1)
            else:
                body_fat = round(1.20 * bmi + 0.23 * age - 5.4, 1)
            if gender == "male":
                if body_fat < 6: category = "Essential Fat"
                elif body_fat < 14: category = "Athlete"
                elif body_fat < 18: category = "Fitness"
                elif body_fat < 25: category = "Average"
                else: category = "Obese"
            else:
                if body_fat < 14: category = "Essential Fat"
                elif body_fat < 21: category = "Athlete"
                elif body_fat < 25: category = "Fitness"
                elif body_fat < 32: category = "Average"
                else: category = "Obese"
            user_sessions[phone] = {"state": "main"}
            send_message(phone, f"Body Fat Results 📊\n\nEstimated Body Fat: {body_fat}%\nCategory: {category}\n\nSend 0 for Main Menu")
        except:
            send_message(phone, "Please enter a valid age (e.g. 25):")

    elif state == "ask_ai":
        send_message(phone, ask_ai(msg))

    elif state == "calorie_counter":
        send_message(phone, ask_ai_calories(msg))

    elif state == "progress_weight":
        try:
            weight = float(msg)
            user_sessions[phone] = {"state": "main"}
            send_message(phone, get_progress_message(phone, weight))
        except:
            send_message(phone, "Please enter a valid weight (e.g. 75.5):")

    elif state == "set_reminder":
        try:
            hour = int(msg)
            if 0 <= hour <= 23:
                save_reminder(phone, hour)
                if phone in reminder_sent_today:
                    del reminder_sent_today[phone]
                user_sessions[phone] = {"state": "main"}
                period = "AM" if hour < 12 else "PM"
                display_hour = hour % 12 or 12
                send_message(phone, f"✅ Reminder set for {display_hour}:00 {period} IST daily!\n\nEvery day I'll send your workout plan! 💪\n\nTo cancel: send *stop reminder*\n\nSend 0 for Main Menu")
            else:
                send_message(phone, "Enter a valid hour (0-23):")
        except:
            send_message(phone, "Enter a number (e.g. 7 for 7 AM, 18 for 6 PM):")

# ─── FLASK ROUTES ─────────────────────────────────────────────

@app.route('/webhook', methods=['GET'])
def verify():
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if token == VERIFY_TOKEN:
        return challenge, 200
    return 'Invalid verify token', 403

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    try:
        for entry in data.get('entry', []):
            for change in entry.get('changes', []):
                messages = change.get('value', {}).get('messages', [])
                for msg in messages:
                    phone = msg['from']
                    if msg['type'] == 'text':
                        handle_message(phone, msg['text']['body'])
    except Exception as e:
        print("Error:", e)
    return 'OK', 200

@app.route('/', methods=['GET'])
def home():
    return 'GymBot is running! 💪', 200

# ─── STARTUP ──────────────────────────────────────────────────

init_db()

scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_reminders, 'cron', minute='*')
scheduler.add_job(send_morning_motivation, 'cron', minute='*')
scheduler.add_job(send_weekly_progress_report, 'cron', minute='*')
scheduler.start()

threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
