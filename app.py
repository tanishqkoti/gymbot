from flask import Flask, request
import requests
import os
import json
import pytz
import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

IST = pytz.timezone("Asia/Kolkata")
user_sessions = {}
reminder_sent_today = {}
motivation_sent_today = {}
weekly_report_sent = {}
REMINDERS_FILE = "reminders.json"
PROGRESS_FILE = "progress.json"

WORKOUT_SCHEDULE = {
    0: "Chest and Triceps 💪",
    1: "Back and Biceps 🏋️",
    2: "Legs and Glutes 🦵",
    3: "Shoulders and Arms 🏆",
    4: "Core and Abs 🔥",
    5: "Cardio / Full Body 🏃",
    6: "Rest and Recovery 😴"
}

def load_reminders():
    try:
        if os.path.exists(REMINDERS_FILE):
            with open(REMINDERS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_reminders(reminders):
    try:
        with open(REMINDERS_FILE, "w") as f:
            json.dump(reminders, f)
    except Exception as e:
        print("Save Error:", e)

def load_progress():
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def save_progress(progress):
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f)
    except Exception as e:
        print("Progress Save Error:", e)

user_reminders = load_reminders()
user_progress = load_progress()

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
            return "AI is temporarily unavailable. Try again in a moment! 💪\n\nSend 0 for Main Menu"
    except Exception as e:
        print("AI Error: " + str(e))
        return "Sorry, I could not process that right now. Send 0 for the main menu."

def ask_ai_calories(food):
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a nutrition expert. When given food items, calculate and list the calories for each item and give a total. Format your response clearly with each food item on a new line with its calories, then a total at the end. Keep it short and precise. Use this format:\n🍽️ Calorie Count:\n• [food item] = [calories] kcal\n• [food item] = [calories] kcal\n\n🔥 Total = [total] kcal\n\n[one short fitness tip related to the food]"},
                {"role": "user", "content": f"Calculate calories for: {food}"}
            ]
        }
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=10)
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"].strip() + "\n\n_Send 18 for more calorie checks_\n_Send 0 for Main Menu_ 💪"
        else:
            return "Could not calculate calories right now. Try again! 💪\n\nSend 0 for Main Menu"
    except Exception as e:
        print("Calorie AI Error: " + str(e))
        return "Sorry, could not process that. Send 0 for the main menu."

def send_message(phone, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    requests.post(url, headers=headers, json=data)

def get_progress_message(phone, new_weight):
    now = datetime.now(IST)
    today = now.strftime("%d %b %Y")

    if phone not in user_progress:
        user_progress[phone] = []

    entries = user_progress[phone]
    entries.append({"date": today, "weight": new_weight})
    user_progress[phone] = entries
    save_progress(user_progress)

    msg = f"📊 *Progress Saved!*\n\nDate: {today}\nWeight: {new_weight} kg\n\n"

    if len(entries) == 1:
        msg += "This is your first entry! Keep logging every week to track your progress! 💪"
    else:
        msg += "*Your Journey:*\n"
        show_entries = entries[-5:]
        for entry in show_entries:
            marker = "← Today" if entry == entries[-1] else ""
            msg += f"• {entry['date']} → {entry['weight']} kg {marker}\n"

        first_weight = entries[0]["weight"]
        diff = round(new_weight - first_weight, 1)

        msg += "\n"
        if diff < 0:
            msg += f"🎉 You lost *{abs(diff)} kg* since you started! Amazing progress!"
        elif diff > 0:
            msg += f"📈 You gained *{diff} kg* since you started! Bulking up nicely!"
        else:
            msg += "⚖️ Weight maintained since start! Stay consistent!"

    msg += "\n\nSend *19* anytime to log your weight!\nSend *0* for Main Menu"
    return msg

def send_weekly_progress_report():
    now = datetime.now(IST)
    if now.weekday() != 6 or now.hour != 9:
        return

    today_str = str(now.date())
    all_users = set(list(user_reminders.keys()) + list(user_sessions.keys()) + list(user_progress.keys()))

    for phone in all_users:
        if weekly_report_sent.get(phone) == today_str:
            continue

        entries = user_progress.get(phone, [])

        if len(entries) >= 2:
            latest = entries[-1]
            previous = entries[-2]
            diff = round(latest["weight"] - previous["weight"], 1)

            if diff < 0:
                change_msg = f"🎉 You lost *{abs(diff)} kg* this week! Keep it up!"
            elif diff > 0:
                change_msg = f"📈 You gained *{diff} kg* this week! Bulking nicely!"
            else:
                change_msg = "⚖️ Weight maintained this week! Consistency is key!"

            msg = (
                f"📈 *Weekly Progress Report!*\n\n"
                f"Happy Sunday! Here's your week summary:\n\n"
                f"Last logged: {previous['date']} → {previous['weight']} kg\n"
                f"This week: {latest['date']} → {latest['weight']} kg\n\n"
                f"{change_msg}\n\n"
                f"Overall journey: *{entries[0]['weight']} kg → {latest['weight']} kg*\n\n"
                f"Send *19* to log today's weight!\n"
                f"Send *0* for Main Menu 💪"
            )
        elif len(entries) == 1:
            msg = (
                f"📈 *Weekly Progress Report!*\n\n"
                f"Happy Sunday! 🌟\n\n"
                f"You have 1 weight entry so far: *{entries[0]['weight']} kg*\n\n"
                f"Log your weight every week to track your progress!\n\n"
                f"Send *19* to log today's weight!\n"
                f"Send *0* for Main Menu 💪"
            )
        else:
            msg = (
                f"📈 *Weekly Progress Report!*\n\n"
                f"Happy Sunday! 🌟\n\n"
                f"You haven't logged your weight yet!\n\n"
                f"Start tracking today — send *19* to log your first weight entry!\n\n"
                f"Send *0* for Main Menu 💪"
            )

        send_message(phone, msg)
        weekly_report_sent[phone] = today_str

def send_daily_reminders():
    now = datetime.now(IST)
    day_of_week = now.weekday()
    today = str(now.date())
    workout = WORKOUT_SCHEDULE[day_of_week]
    for phone, reminder in list(user_reminders.items()):
        if reminder["hour"] == now.hour and now.minute < 5:
            last_sent = reminder_sent_today.get(phone)
            if last_sent == today:
                continue
            if day_of_week == 6:
                msg = "🌟 Good morning! Today is your *Rest Day* — recover and stay hydrated! 💧\n\nSend 0 for Main Menu"
            else:
                msg = (
                    f"🔔 *GymBot Reminder!*\n\n"
                    f"Good morning! Time for your workout!\n\n"
                    f"Today: *{workout}*\n\n"
                    f"Send *1* for today's workout plan!\n"
                    f"Send *0* for main menu\n\n"
                    f"Let's crush it today! 💪🔥"
                )
            send_message(phone, msg)
            reminder_sent_today[phone] = today

def send_morning_motivation():
    now = datetime.now(IST)
    today = str(now.date())
    if now.hour != 8:
        return
    quote = ask_ai("Give me one powerful unique gym and fitness motivational quote for today. Keep it under 3 lines. Do not add Send 0 for Main Menu at the end.")
    msg = f"🌅 *Good Morning!*\n\n{quote}\n\n💪 Let's crush today's workout!\nSend *0* for Main Menu"
    all_users = set(list(user_reminders.keys()) + list(user_sessions.keys()))
    for phone in all_users:
        if motivation_sent_today.get(phone) == today:
            continue
        send_message(phone, msg)
        motivation_sent_today[phone] = today

def get_main_menu():
    return (
        "Welcome to GymBot! 🏋️\n\n"
        "I am your personal AI fitness assistant.\n\n"
        "Reply with a number:\n\n"
        "1 - Workout Plans\n"
        "2 - Diet and Nutrition\n"
        "3 - BMI Calculator\n"
        "4 - Weekly Schedule\n"
        "5 - Membership Info\n"
        "6 - Exercise Tips\n"
        "7 - Supplement Guide\n"
        "8 - Motivational Quote\n"
        "9 - 30 Day Challenge\n"
        "10 - Calorie Calculator\n"
        "11 - Water Intake Calculator\n"
        "12 - Body Fat Calculator\n"
        "13 - Cardio Guide\n"
        "14 - Recovery and Sleep Tips\n"
        "15 - Ask AI (Any Fitness Question)\n"
        "16 - Set Workout Reminder 🔔\n"
        "17 - Cancel Reminder ❌\n"
        "18 - Calorie Counter 🍽️\n"
        "19 - Progress Tracker 📊\n"
        "0 - Main Menu (anytime)\n\n"
        "Or just TYPE any fitness question!"
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
    return "Supplement Guide 💊\n\nBeginner Essentials:\n- Whey Protein: 1-2 scoops post workout\n- Creatine: 5g daily (any time)\n- Multivitamin: 1 daily with food\n\nIntermediate:\n- Pre-workout: 30 min before gym\n- BCAA: During workout\n- Fish Oil: 1g daily\n\nAdvanced:\n- Casein Protein: Before bed\n- Glutamine: Post workout\n\n⚠️ Food first, supplements second!\nSend 0 for Main Menu"

def get_30_day_challenge():
    return "30 Day Fitness Challenge 🔥\n\nWeek 1 - Foundation:\n- 20 push-ups daily\n- 30 squats daily\n- 1 min plank daily\n\nWeek 2 - Build:\n- 30 push-ups daily\n- 40 squats daily\n- 2 min plank daily\n\nWeek 3 - Intensity:\n- 40 push-ups daily\n- 50 squats daily\n- 3 min plank daily\n\nWeek 4 - Beast Mode:\n- 50 push-ups daily\n- 60 squats daily\n- 4 min plank daily\n\nNo excuses — consistency is key! 💪\nSend 0 for Main Menu"

def get_cardio_guide():
    return "Cardio Guide 🏃\n\nFor Weight Loss:\n- 30-45 min moderate cardio\n- 5 days per week\n- Heart rate: 60-70% max\n\nFor Endurance:\n- Long slow runs 45-60 min\n- 3-4 days per week\n\nHIIT (Best for fat burn):\n- 20 sec sprint + 40 sec rest\n- Repeat 10-15 times\n- Only 20 mins needed!\n\nBest Cardio Options:\nRunning, Cycling, Swimming, Jump rope\n\nDo cardio AFTER weights!\nSend 0 for Main Menu"

def get_recovery_tips():
    return "Recovery and Sleep Tips 😴\n\nSleep:\n- 7-9 hours every night\n- Sleep at same time daily\n- No phone 30 min before bed\n\nRecovery:\n- Stretch 10 min after workout\n- Foam roll sore muscles\n- Ice pack for injuries\n- Active rest on off days (walk)\n\nNutrition for Recovery:\n- Eat protein within 30 min\n- Stay hydrated\n- Avoid alcohol\n\nRemember: Muscles grow during REST!\nSend 0 for Main Menu"

def handle_message(phone, message):
    msg = message.strip()
    msg_lower = msg.lower()
    session = user_sessions.get(phone, {"state": "main"})

    if msg == "0":
        user_sessions[phone] = {"state": "main"}
        send_message(phone, get_main_menu())
        return

    if "stop reminder" in msg_lower or "cancel reminder" in msg_lower or msg == "17":
        if phone in user_reminders:
            del user_reminders[phone]
            save_reminders(user_reminders)
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
            send_message(phone, ask_ai("Give me a powerful motivational quote for gym and fitness"))
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
            send_message(phone, "🍽️ *Calorie Counter*\n\nType any food or meal!\n\nExamples:\n- 2 eggs and oats\n- rice 1 cup and chicken\n- banana and peanut butter toast\n\nSend 0 to go back to Main Menu")
        elif msg == "19":
            user_sessions[phone] = {"state": "progress_weight"}
            entries = user_progress.get(phone, [])
            if entries:
                last = entries[-1]
                send_message(phone, f"📊 *Progress Tracker*\n\nLast logged: {last['date']} → {last['weight']} kg\n\nEnter your current weight in kg (e.g. 75.5):\n\nSend 0 to cancel")
            else:
                send_message(phone, "📊 *Progress Tracker*\n\nTrack your weight journey here!\n\nEnter your current weight in kg (e.g. 75.5):\n\nSend 0 to cancel")
        else:
            send_message(phone, ask_ai(msg))

    elif state == "workout":
        workout = get_workout(msg)
        if workout:
            send_message(phone, workout)
            send_message(phone, "Reply 0 for Main Menu")
        else:
            send_message(phone, get_workout_menu())

    elif state == "diet":
        diet = get_diet(msg)
        if diet:
            send_message(phone, diet)
            send_message(phone, "Reply 0 for Main Menu")
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
                user_reminders[phone] = {"hour": hour, "minute": 0}
                save_reminders(user_reminders)
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

scheduler = BackgroundScheduler(timezone=IST)
scheduler.add_job(send_daily_reminders, 'cron', minute='*')
scheduler.add_job(send_morning_motivation, 'cron', minute='*')
scheduler.add_job(send_weekly_progress_report, 'cron', minute='*')
scheduler.start()

# Keep Render alive — pings itself every 10 minutes
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
