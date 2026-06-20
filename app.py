import os
import random
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN    = os.getenv("VERIFY_TOKEN", "gymbot123")
WHATSAPP_TOKEN  = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")

def ask_ai(question):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": "Bearer " + GROQ_API_KEY,
            "Content-Type": "application/json"
        }
        body = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {
                    "role": "system",
                    "content": "You are GymBot, a friendly and knowledgeable fitness assistant for a gym in Belagavi, India. Answer fitness questions in a helpful, concise way (max 150 words). Only answer fitness, health, nutrition and exercise questions. If not fitness related, say you can only help with fitness topics. Use simple language and be encouraging."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }
        r = requests.post(url, json=body, headers=headers, timeout=10)
        data = r.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            return "AI Error: " + data["error"].get("message", "Unknown") + "\n\nSend 0 for Main Menu"
        else:
            return "Sorry, AI is not available right now. Send 0 for Main Menu."
    except Exception as e:
        return "Sorry, AI error: " + str(e)

user_sessions = {}

QUOTES = [
    "The only bad workout is the one that didn\'t happen!",
    "Push yourself because no one else is going to do it for you.",
    "Your body can stand almost anything. It\'s your mind you have to convince.",
    "Success starts with self-discipline.",
    "Don\'t stop when you\'re tired. Stop when you\'re done.",
    "Wake up. Work out. Look hot. Kick ass.",
    "The pain you feel today will be the strength you feel tomorrow.",
    "Sweat is just fat crying!",
    "Be stronger than your excuses.",
    "Results happen over time, not overnight. Work hard, stay consistent.",
    "Your only limit is you.",
    "Train insane or remain the same!",
    "No pain, no gain. Shut up and train!",
    "Believe in yourself and all that you are capable of!"
]

CHALLENGE = {
    "1":  "Day 1: 20 Push-ups + 30 Squats + 1 min Plank",
    "2":  "Day 2: 25 Push-ups + 35 Squats + 20 Crunches",
    "3":  "Day 3: REST DAY - Light walk 20 mins + Stretching",
    "4":  "Day 4: 30 Push-ups + 40 Squats + 15 Burpees",
    "5":  "Day 5: 3 x 10 Pull-ups + 3 x 15 Dips + 2 min Plank",
    "6":  "Day 6: 5km Run or 30 min Cardio",
    "7":  "Day 7: REST DAY - Full body stretch + 10 min meditation",
    "8":  "Day 8: 35 Push-ups + 45 Squats + 25 Crunches",
    "9":  "Day 9: 4 x 10 Pull-ups + 3 x 12 Pike Push-ups",
    "10": "Day 10: 40 Push-ups + 50 Squats + 20 Burpees",
    "11": "Day 11: REST DAY - Yoga or light stretching 20 mins",
    "12": "Day 12: 45 Push-ups + 50 Squats + 3 min Plank",
    "13": "Day 13: 6km Run or 40 min Cardio",
    "14": "Day 14: REST DAY - Full body stretch + Recovery",
    "15": "Day 15: 50 Push-ups + 60 Squats + 30 Crunches + 25 Burpees",
    "16": "Day 16: 4 x 12 Pull-ups + 4 x 15 Dips + 3 min Plank",
    "17": "Day 17: REST DAY - Light walk + Foam rolling",
    "18": "Day 18: 55 Push-ups + 65 Squats + 20 Burpees",
    "19": "Day 19: 7km Run or 45 min Cardio",
    "20": "Day 20: 60 Push-ups + 70 Squats + 4 min Plank",
    "21": "Day 21: REST DAY - Celebrate 3 weeks! Stretch + Rest",
    "22": "Day 22: 65 Push-ups + 75 Squats + 35 Crunches",
    "23": "Day 23: 5 x 10 Pull-ups + 4 x 15 Dips + 30 Burpees",
    "24": "Day 24: 8km Run or 50 min Cardio",
    "25": "Day 25: REST DAY - Full body stretch + Meditation",
    "26": "Day 26: 70 Push-ups + 80 Squats + 5 min Plank",
    "27": "Day 27: 5 x 12 Pull-ups + 5 x 15 Dips + 35 Burpees",
    "28": "Day 28: REST DAY - Light walk + Recovery",
    "29": "Day 29: 80 Push-ups + 90 Squats + 40 Burpees + 5 min Plank",
    "30": "Day 30: FINAL DAY! 100 Push-ups + 100 Squats + 50 Burpees + 5 min Plank\n\nCONGRATULATIONS! You completed the 30 Day Challenge! You are a CHAMPION!"
}


def get_main_menu():
    return (
        "Welcome to GymBot!\n\n"
        "I am your personal fitness assistant.\n\n"
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
        "0 - Main Menu (anytime)"
    )


def get_workout_menu():
    return (
        "Workout Plans\n\n"
        "Choose your target:\n\n"
        "1 - Chest and Triceps\n"
        "2 - Back and Biceps\n"
        "3 - Legs and Glutes\n"
        "4 - Shoulders and Arms\n"
        "5 - Core and Abs\n"
        "6 - Full Body\n"
        "0 - Back to Main Menu"
    )


def get_diet_menu():
    return (
        "Diet and Nutrition\n\n"
        "Choose a topic:\n\n"
        "1 - Weight Loss Diet\n"
        "2 - Muscle Gain Diet\n"
        "3 - Pre-Workout Meals\n"
        "4 - Post-Workout Meals\n"
        "5 - Protein Rich Foods\n"
        "6 - Hydration Tips\n"
        "0 - Back to Main Menu"
    )


def get_supplement_menu():
    return (
        "Supplement Guide\n\n"
        "Choose a supplement:\n\n"
        "1 - Whey Protein\n"
        "2 - Creatine\n"
        "3 - BCAA\n"
        "4 - Pre-Workout\n"
        "5 - Multivitamins\n"
        "6 - Fish Oil\n"
        "0 - Back to Main Menu"
    )


def get_cardio_menu():
    return (
        "Cardio Guide\n\n"
        "Choose a cardio type:\n\n"
        "1 - Running Plan\n"
        "2 - HIIT Workout\n"
        "3 - Cycling Plan\n"
        "4 - Jump Rope\n"
        "5 - Swimming Guide\n"
        "6 - Cardio for Weight Loss\n"
        "0 - Back to Main Menu"
    )


def get_recovery_menu():
    return (
        "Recovery and Sleep Tips\n\n"
        "Choose a topic:\n\n"
        "1 - Sleep Guide for Athletes\n"
        "2 - Stretching Routine\n"
        "3 - Foam Rolling Guide\n"
        "4 - Muscle Recovery Tips\n"
        "5 - Rest Day Activities\n"
        "6 - Signs of Overtraining\n"
        "0 - Back to Main Menu"
    )


CARDIO = {
    "1": "Running Plan\n\nBeginner: Run 1 min, Walk 2 min x 8 rounds\nIntermediate: Run 3 min, Walk 1 min x 6 rounds\nAdvanced: Continuous 5km run\n\nTips:\n- Warm up 5 mins before\n- Run 3-4 days per week",
    "2": "HIIT Workout\n\nDuration: 20 mins\n40 sec work, 20 sec rest\n\nRepeat 4x:\n- Jumping Jacks\n- Burpees\n- High Knees\n- Mountain Climbers\n- Jump Squats\n\nBurns 300-400 calories in 20 mins!",
    "3": "Cycling Plan\n\nBeginner: 20-30 mins easy, 3 days/week\nIntermediate: 40 mins intervals, 4 days/week\nAdvanced: 60 mins endurance, 5 days/week\n\nKeep cadence 70-90 RPM",
    "4": "Jump Rope\n\nBeginner: 30 sec jump, 30 sec rest x 10\nIntermediate: 1 min jump, 30 sec rest x 10\nAdvanced: 2 min jump, 30 sec rest x 10\n\nBurns 200-300 calories per 20 mins!",
    "5": "Swimming Guide\n\nBeginner: 4 x 25m with 30 sec rest\nIntermediate: 8 x 50m with 20 sec rest\nAdvanced: 10 x 100m with 15 sec rest\n\nBurns 400-600 calories/hour!",
    "6": "Cardio for Weight Loss\n\nBest options:\n1. HIIT - Burns most in least time\n2. Running - High calorie burn\n3. Cycling - Low impact\n4. Jump Rope - Portable\n\nCardio + Calorie deficit = Fat loss!"
}

RECOVERY = {
    "1": "Sleep Guide\n\nIdeal: 8-9 hours/night\n\nWhy it matters:\n- 80% muscle growth happens during sleep\n- Growth hormone released at night\n\nBetter sleep tips:\n- Same sleep/wake time daily\n- No screens 1 hour before bed\n- No caffeine after 3 PM",
    "2": "Post Workout Stretching\n\nHold each 30-45 seconds:\n\nUpper: Chest, Shoulder, Tricep, Neck\nLower: Quad, Hamstring, Hip flexor, Calf\nCore: Cobra, Child pose, Cat cow\n\nDo 10-15 mins after every workout!",
    "3": "Foam Rolling\n\nRoll each area 60-90 seconds:\n1. Calves 2. Hamstrings\n3. IT Band 4. Quads\n5. Glutes 6. Upper back 7. Lats\n\nReduces soreness and increases blood flow!",
    "4": "Muscle Recovery\n\nAfter workout: Protein + carbs + stretch\n24-48 hrs: Cold shower, hydrate, sleep 8+ hrs\n\nDOMS peaks at 24-48 hrs, gone in 72 hrs",
    "5": "Rest Day Activities\n\nActive recovery is better!\n- 20-30 min walk\n- Yoga or stretching\n- Foam rolling\n- Meditation 10 mins\n\nRest days are when you GROW!",
    "6": "Signs of Overtraining\n\nWatch out for:\n- Performance getting worse\n- Always tired, frequent injuries\n- No motivation, mood swings\n\nFix: 1-2 weeks rest + more sleep + more food\nPrevent: Deload every 6-8 weeks"
}

SUPPLEMENTS = {
    "1": "Whey Protein\n\nWhen: Right after workout\nDosage: 1-2 scoops/day\nBrands: MuscleBlaze, Optimum Nutrition",
    "2": "Creatine\n\nBenefits: Strength + power\nDosage: 3-5g daily\nDrink extra water (4-5L daily)",
    "3": "BCAA\n\nWhen: During workout\nDosage: 5-10g per serving\nOptional if eating enough protein",
    "4": "Pre-Workout\n\nWhen: 20-30 mins before\nWarning: Has caffeine, avoid after 5 PM\nBeginners: half dose",
    "5": "Multivitamins\n\nWhen: Morning with breakfast\nDosage: 1 tablet/day",
    "6": "Fish Oil (Omega-3)\n\nBenefits: Reduces joint pain\nDosage: 1-2 capsules/day (1000mg)"
}

WORKOUTS = {
    "1": "Chest and Triceps\n\n- Bench Press: 4x10\n- Incline DB Press: 3x12\n- Cable Fly: 3x15\n- Tricep Pushdown: 3x12\n- Overhead Ext: 3x12\n- Diamond Push-ups: 2xfailure",
    "2": "Back and Biceps\n\n- Pull-ups: 4x8\n- Bent Over Row: 4x10\n- Lat Pulldown: 3x12\n- Seated Row: 3x12\n- Barbell Curl: 3x12\n- Hammer Curls: 3x12",
    "3": "Legs and Glutes\n\n- Barbell Squat: 4x10\n- Romanian Deadlift: 4x10\n- Leg Press: 3x15\n- Walking Lunges: 3x12\n- Leg Curl: 3x12\n- Calf Raises: 4x20",
    "4": "Shoulders and Arms\n\n- Overhead Press: 4x10\n- Lateral Raises: 3x15\n- Front Raises: 3x12\n- Face Pulls: 3x15\n- Barbell Curl: 3x12\n- Skull Crushers: 3x12",
    "5": "Core and Abs\n\n- Plank: 3x60sec\n- Crunches: 3x20\n- Leg Raises: 3x15\n- Russian Twists: 3x20\n- Mountain Climbers: 3x30sec\n- Bicycle Crunches: 3x20",
    "6": "Full Body\n\n- Squats: 3x12\n- Push-ups: 3x15\n- DB Row: 3x12\n- Shoulder Press: 3x12\n- Deadlift: 3x10\n- Plank: 3x45sec"
}

DIETS = {
    "1": "Weight Loss Diet\n\nBreakfast: Oats + banana + black coffee\nLunch: Chapati + dal + salad\nSnack: Apple or nuts\nDinner: Grilled paneer/fish + salad\n\nTarget: 1500-1800 kcal/day",
    "2": "Muscle Gain Diet\n\nBreakfast: 4 eggs + oats + banana + milk\nLunch: Rice + chicken + dal + veggies\nSnack: PB sandwich + protein shake\nDinner: Paneer curry + chapati\n\nTarget: 2500-3000 kcal/day",
    "3": "Pre-Workout Meals\n\nEat 60-90 mins before:\n- Banana + peanut butter toast\n- Oats + honey + black coffee\n- Sweet potato + eggs\n- Dates + black coffee",
    "4": "Post-Workout Meals\n\nEat within 30-45 mins:\n- Whey shake + banana\n- Eggs + brown bread\n- Chicken rice bowl\n- Paneer + chapati",
    "5": "Protein Rich Foods\n\nAnimal: Eggs 6g, Chicken 31g/100g, Fish 25g/100g, Paneer 18g/100g\nPlant: Dal 9g, Chickpeas 15g, Peanuts 25g per 100g\n\nTarget: 1.6-2.2g per kg bodyweight",
    "6": "Hydration Tips\n\nDaily: 3-4L normal, 4-5L training\n\n- 500ml after waking\n- 500ml before each meal\n- 250ml every 30 min during workout\n- 500ml after workout"
}


def handle_bmi(session, text):
    step = session.get("bmi_step", 1)
    if step == 1:
        session["bmi_step"] = 2
        return "BMI Calculator\n\nEnter your weight in kg:\n(Example: 70)"
    elif step == 2:
        try:
            session["weight"] = float(text)
            session["bmi_step"] = 3
            return "Now enter your height in cm:\n(Example: 175)"
        except ValueError:
            return "Please enter a valid number."
    elif step == 3:
        try:
            h = float(text) / 100
            w = session["weight"]
            bmi = round(w / (h ** 2), 1)
            if bmi < 18.5:
                cat, adv = "Underweight", "Focus on muscle gain diet."
            elif bmi < 25:
                cat, adv = "Normal weight", "Maintain with balanced diet."
            elif bmi < 30:
                cat, adv = "Overweight", "Focus on cardio and calorie deficit."
            else:
                cat, adv = "Obese", "Consult a doctor and start with light cardio."
            session.clear()
            return f"BMI Result\n\nBMI: {bmi}\nCategory: {cat}\nAdvice: {adv}\n\nSend 0 for Main Menu"
        except (ValueError, ZeroDivisionError):
            session.clear()
            return "Invalid height. Send 0 to restart."


def handle_calorie(session, text):
    step = session.get("cal_step", 1)
    if step == 1:
        session["cal_step"] = 2
        return "Calorie Calculator\n\nStep 1 of 5\n\nEnter your weight in kg:\n(Example: 70)"
    elif step == 2:
        try:
            session["weight"] = float(text); session["cal_step"] = 3
            return "Step 2 of 5\n\nEnter your height in cm:\n(Example: 175)"
        except ValueError:
            return "Please enter a valid number."
    elif step == 3:
        try:
            session["height"] = float(text); session["cal_step"] = 4
            return "Step 3 of 5\n\nEnter your age:\n(Example: 25)"
        except ValueError:
            return "Please enter a valid number."
    elif step == 4:
        try:
            session["age"] = int(text); session["cal_step"] = 5
            return "Step 4 of 5\n\nEnter your gender:\n1 - Male\n2 - Female"
        except ValueError:
            return "Please enter a valid age."
    elif step == 5:
        if text not in ["1", "2"]:
            return "Please send 1 for Male or 2 for Female."
        session["gender"] = text; session["cal_step"] = 6
        return "Step 5 of 5\n\nWhat is your goal?\n\n1 - Lose Weight\n2 - Maintain Weight\n3 - Gain Muscle"
    elif step == 6:
        if text not in ["1", "2", "3"]:
            return "Please send 1, 2 or 3."
        w, h, a, g = session["weight"], session["height"], session["age"], session["gender"]
        bmr = (10*w + 6.25*h - 5*a + 5) if g == "1" else (10*w + 6.25*h - 5*a - 161)
        tdee = round(bmr * 1.55)
        if text == "1":
            goal, cal = "Lose Weight", tdee - 500
            advice = f"{cal} kcal/day (500 deficit = ~0.5kg/week loss)"
        elif text == "2":
            goal, cal = "Maintain Weight", tdee
            advice = f"{cal} kcal/day"
        else:
            goal, cal = "Gain Muscle", tdee + 300
            advice = f"{cal} kcal/day (300 surplus for lean gain)"
        session.clear()
        return f"Calorie Result\n\nGoal: {goal}\nDaily Target: {advice}\nProtein: {round(w*2)}g/day\n\nSend 0 for Main Menu"


def handle_water(session, text):
    step = session.get("water_step", 1)
    if step == 1:
        session["water_step"] = 2
        return "Water Intake Calculator\n\nEnter your weight in kg:\n(Example: 70)"
    elif step == 2:
        try:
            session["weight"] = float(text); session["water_step"] = 3
            return "Do you workout today?\n\n1 - Yes\n2 - No"
        except ValueError:
            return "Please enter a valid number."
    elif step == 3:
        if text not in ["1", "2"]:
            return "Please send 1 for Yes or 2 for No."
        w = session["weight"]
        base = round(w * 0.033, 1)
        total = round(base + 0.5, 1) if text == "1" else base
        glasses = round(total / 0.25)
        session.clear()
        return f"Water Result\n\nDaily Target: {total} litres\n({glasses} glasses of 250ml)\n\nSend 0 for Main Menu"


def handle_bodyfat(session, text):
    step = session.get("bf_step", 1)
    if step == 1:
        session["bf_step"] = 2
        return "Body Fat Calculator\n\nStep 1 of 4\n\nEnter your weight in kg:\n(Example: 70)"
    elif step == 2:
        try:
            session["weight"] = float(text); session["bf_step"] = 3
            return "Step 2 of 4\n\nEnter your height in cm:\n(Example: 175)"
        except ValueError:
            return "Please enter a valid number."
    elif step == 3:
        try:
            session["height"] = float(text); session["bf_step"] = 4
            return "Step 3 of 4\n\nEnter your age:\n(Example: 25)"
        except ValueError:
            return "Please enter a valid number."
    elif step == 4:
        try:
            session["age"] = int(text); session["bf_step"] = 5
            return "Step 4 of 4\n\nEnter your gender:\n1 - Male\n2 - Female"
        except ValueError:
            return "Please enter a valid age."
    elif step == 5:
        if text not in ["1", "2"]:
            return "Please send 1 for Male or 2 for Female."
        w, h, a = session["weight"], session["height"], session["age"]
        bmi = w / ((h / 100) ** 2)
        if text == "1":
            bf = round((1.20 * bmi) + (0.23 * a) - 16.2, 1)
            gender = "Male"
            if bf < 6: cat = "Essential Fat (Too low)"
            elif bf < 14: cat = "Athletic"
            elif bf < 18: cat = "Fitness"
            elif bf < 25: cat = "Average"
            else: cat = "Obese"
        else:
            bf = round((1.20 * bmi) + (0.23 * a) - 5.4, 1)
            gender = "Female"
            if bf < 14: cat = "Essential Fat (Too low)"
            elif bf < 21: cat = "Athletic"
            elif bf < 25: cat = "Fitness"
            elif bf < 32: cat = "Average"
            else: cat = "Obese"
        lean = round(w * (1 - bf / 100), 1)
        fat  = round(w * bf / 100, 1)
        session.clear()
        return (f"Body Fat Result\n\nWeight: {w}kg | Height: {h}cm\n"
                f"Age: {a} | Gender: {gender}\n\n"
                f"Body Fat: {bf}%\nCategory: {cat}\n"
                f"Lean Mass: {lean}kg\nFat Mass: {fat}kg\n\n"
                "Send 0 for Main Menu")


def process_message(sender, text):
    t = text.strip()
    session = user_sessions.get(sender, {})
    menu = session.get("menu", "main")

    # Global reset
    if t == "0":
        user_sessions[sender] = {}
        return get_main_menu()

    # --- Multi-step flows ---
    if menu == "bmi" or (t == "3" and menu == "main"):
        if t == "3":
            user_sessions[sender] = {"menu": "bmi", "bmi_step": 1}
            return handle_bmi(user_sessions[sender], t)
        resp = handle_bmi(session, t)
        user_sessions[sender] = session
        return resp

    if menu == "calorie" or (t == "10" and menu == "main"):
        if t == "10":
            user_sessions[sender] = {"menu": "calorie", "cal_step": 1}
            return handle_calorie(user_sessions[sender], t)
        resp = handle_calorie(session, t)
        user_sessions[sender] = session
        return resp

    if menu == "water" or (t == "11" and menu == "main"):
        if t == "11":
            user_sessions[sender] = {"menu": "water", "water_step": 1}
            return handle_water(user_sessions[sender], t)
        resp = handle_water(session, t)
        user_sessions[sender] = session
        return resp

    if menu == "bodyfat" or (t == "12" and menu == "main"):
        if t == "12":
            user_sessions[sender] = {"menu": "bodyfat", "bf_step": 1}
            return handle_bodyfat(user_sessions[sender], t)
        resp = handle_bodyfat(session, t)
        user_sessions[sender] = session
        return resp

    if menu == "ai":
        user_sessions[sender] = {}
        reply = ask_ai(t)
        return f"AI Answer\n\n{reply}\n\nSend 0 for Main Menu\nSend 15 to ask another question"

    # --- Simple sub-menus ---
    if menu == "cardio":
        result = CARDIO.get(t)
        if result:
            user_sessions[sender] = {}
            return result + "\n\nSend 0 for Main Menu"
        return "Please choose 1 to 6."

    if menu == "recovery":
        result = RECOVERY.get(t)
        if result:
            user_sessions[sender] = {}
            return result + "\n\nSend 0 for Main Menu"
        return "Please choose 1 to 6."

    if menu == "supplement":
        result = SUPPLEMENTS.get(t)
        if result:
            user_sessions[sender] = {}
            return result + "\n\nSend 0 for Main Menu"
        return "Please choose 1 to 6."

    if menu == "challenge":
        ch = CHALLENGE.get(t)
        if ch:
            user_sessions[sender] = {}
            return f"30 Day Challenge\n\n{ch}\n\nGreat work! \U0001f4aa\n\nSend 0 for Main Menu"
        return "Please send a number between 1 and 30."

    if menu == "workout":
        result = WORKOUTS.get(t)
        if result:
            user_sessions[sender] = {}
            return result + "\n\nRest 60-90 sec between sets\n\nSend 0 for Main Menu"
        return "Please choose 1 to 6."

    if menu == "diet":
        result = DIETS.get(t)
        if result:
            user_sessions[sender] = {}
            return result + "\n\nSend 0 for Main Menu"
        return "Please choose 1 to 6."

    # --- Main menu ---
    if menu == "main":
        if t == "1":
            user_sessions[sender] = {"menu": "workout"}
            return get_workout_menu()
        elif t == "2":
            user_sessions[sender] = {"menu": "diet"}
            return get_diet_menu()
        elif t == "4":
            return (
                "Weekly Schedule\n\n"
                "Mon - Chest and Triceps\nTue - Back and Biceps\n"
                "Wed - Legs and Glutes\nThu - Shoulders and Arms\n"
                "Fri - Core and Abs\nSat - Cardio / Full Body\n"
                "Sun - Rest and Recovery\n\nSend 0 for Main Menu"
            )
        elif t == "5":
            return (
                "Membership Plans\n\n"
                "Basic - Rs.999/month\nStandard - Rs.1499/month\n"
                "Premium - Rs.2499/month\n\n"
                "Call: +917022716035\nLocation: Shahu Nagar, Belagavi\n\n"
                "Send 0 for Main Menu"
            )
        elif t == "6":
            return (
                "Exercise Tips\n\n"
                "- Start with compound exercises\n"
                "- Focus on form not weight\n"
                "- Progressive overload is key\n"
                "- Sleep 7-8 hours minimum\n"
                "- Stretch after every workout\n"
                "- Deload every 6-8 weeks\n\n"
                "Send 0 for Main Menu"
            )
        elif t == "7":
            user_sessions[sender] = {"menu": "supplement"}
            return get_supplement_menu()
        elif t == "8":
            quote = random.choice(QUOTES)
            return f"\u201c{quote}\u201d\n\nKeep pushing! \U0001f4aa\n\nSend 0 for Main Menu"
        elif t == "9":
            user_sessions[sender] = {"menu": "challenge"}
            return "30 Day Challenge\n\nSend the day number (1-30)!\n\nSend 0 for Main Menu"
        elif t == "13":
            user_sessions[sender] = {"menu": "cardio"}
            return get_cardio_menu()
        elif t == "14":
            user_sessions[sender] = {"menu": "recovery"}
            return get_recovery_menu()
        elif t == "15":
            user_sessions[sender] = {"menu": "ai"}
            return (
                "Ask AI Anything! \U0001f916\n\n"
                "Type any fitness question:\n\n"
                "- How to lose belly fat?\n"
                "- Best exercises for beginners?\n"
                "- What to eat before gym?\n"
                "- How to build chest muscles?\n\n"
                "Type your question now!"
            )
        else:
            return "Please reply with a number from the menu.\n\nSend 0 for Main Menu"

    return get_main_menu()


def send_reply(to, message):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": "Bearer " + WHATSAPP_TOKEN,
        "Content-Type": "application/json"
    }
    body = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": message}
    }
    r = requests.post(url, json=body, headers=headers, timeout=10)
    print(f"Reply to {to}: HTTP {r.status_code}")


@app.route("/webhook", methods=["GET"])
def verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def receive():
    data = request.get_json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return "OK", 200
        msg = entry["messages"][0]
        if msg.get("type") != "text":
            return "OK", 200
        sender = msg["from"]
        text   = msg["text"]["body"]
        print(f"From {sender}: {text}")
        reply = process_message(sender, text)
        send_reply(sender, reply)
    except Exception as e:
        print(f"Error: {e}")
    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
