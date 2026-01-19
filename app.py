from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_file
from dotenv import load_dotenv
from pymongo import MongoClient
import os
from db import users, drugs
from auth import auth
from gemini import get_drug_info
import io
from datetime import datetime
from elevenlabs import ElevenLabs
load_dotenv()

app = Flask(__name__)   
app.secret_key = "dev-secret"

app.register_blueprint(auth)

@app.route('/')
def default():
    return redirect(url_for('welcome'))

@app.route("/perscriptions")
def perscriptions():
    if "email" not in session:
        return redirect(url_for("auth.login"))

    email = session["email"]
    user = drugs.find_one({"email": email})
    prescriptions = user["drugs"] if user else []

    return render_template("perscription.html", prescriptions=prescriptions)

@app.route('/home')
def home():
    return render_template("home.html") 

@app.route('/welcome')
def welcome():
    return render_template("welcome.html")

@app.route('/new_perscription', methods=["GET", "POST"])
def new_perscription():
    if 'email' not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = session["email"]

        drug_name = request.form.get('drug-name')
        dosage = request.form.get('dosages')
        per_day = request.form.get('per-day')

        new_drug = {
            "drug_name": drug_name,
            "dosage": dosage,
            "per_day": per_day
        }

        existing = drugs.find_one({"email": email})

        if existing:
            # Add drug to existing user's list
            drugs.update_one(
                {"email": email},
                {"$push": {"drugs": new_drug}}
            )
        else:
            # Create new document for this user
            drugs.insert_one({
                "email": email,
                "drugs": [new_drug]
            })

        return redirect(url_for("perscriptions"))

    return render_template("new_perscription.html")


@app.route("/delete_prescription/<drug_name>")
def delete_prescription(drug_name):
    if "email" not in session:
        return redirect(url_for("auth.login"))

    email = session["email"]

    # Remove the drug with the matching name from the user's array
    result = drugs.update_one(
        {"email": email},
        {"$pull": {"drugs": {"drug_name": drug_name}}}
    )

    return redirect(url_for("perscriptions"))

@app.route('/homescreen')
def homescreen():
    if "email" not in session:
        return redirect(url_for("auth.login"))

    email = session["email"]
    user = drugs.find_one({"email": email})
    prescriptions = user["drugs"] if user else []

    user2 = users.find_one({"email": email})
    first_name = user2["firstname"]

    today_str = datetime.today().strftime("%Y-%m-%d")

    # Reset taken_today if last_taken_date isn't today
    for drug in prescriptions:
        if drug.get("last_taken_date") != today_str:
            # Reset only the fields we care about — safe for other data
            drugs.update_one(
                {"email": email, "drugs.drug_name": drug["drug_name"]},
                {"$set": {"drugs.$.taken_today": 0, "drugs.$.last_taken_date": today_str}}
            )
            # Also update Python dict for rendering
            drug["taken_today"] = 0
            drug["last_taken_date"] = today_str

    # Recalculate total pills taken today after resets
    total_taken = len(prescriptions)
    return render_template(
        "homescreen.html",
        prescriptions=prescriptions,
        first_name=first_name,
        total_taken=total_taken
    )


@app.route("/drug/<drug_name>")
def drug_info(drug_name):
    if "email" not in session:
        return redirect(url_for("auth.login"))

    email = session["email"]
    user = drugs.find_one({"email": email})

    # Find the specific drug
    drug = next((d for d in user["drugs"] if d["drug_name"] == drug_name), None)
    if not drug:
        return redirect(url_for("perscriptions"))

    # Check if gemini_info exists
    if "gemini_info" not in drug or not drug["gemini_info"]:
        info = get_drug_info(drug_name)
        # Update in MongoDB
        drugs.update_one(
            {"email": email, "drugs.drug_name": drug_name},
            {"$set": {"drugs.$.gemini_info": info}}
        )
        drug["gemini_info"] = info
    else:
        info = drug["gemini_info"]

    return render_template("drug_info.html", drug=drug, info=info)

@app.route("/update_taken/<drug_name>/<action>", methods=["POST"])
def update_taken(drug_name, action):
    if "email" not in session:
        return jsonify({"error": "Not logged in"}), 403

    email = session["email"]
    user = drugs.find_one({"email": email})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Find the drug
    drug = next((d for d in user["drugs"] if d["drug_name"] == drug_name), None)
    if not drug:
        return jsonify({"error": "Drug not found"}), 404

    today_str = datetime.today().strftime("%Y-%m-%d")

    # Ensure per_day is int
    try:
        per_day = int(drug.get("per_day", 1))
    except ValueError:
        per_day = 1

    # Reset taken_today if last_taken_date is not today
    if drug.get("last_taken_date") != today_str:
        drug["taken_today"] = 0

    # Initialize taken_today if missing
    if "taken_today" not in drug:
        drug["taken_today"] = 0

    # Increment / Decrement
    if action == "increment" and drug["taken_today"] < per_day:
        drug["taken_today"] += 1
    elif action == "decrement" and drug["taken_today"] > 0:
        drug["taken_today"] -= 1

    drug["last_taken_date"] = today_str

    # Update in MongoDB
    drugs.update_one(
        {"email": email, "drugs.drug_name": drug_name},
        {"$set": {"drugs.$": drug}}
    )

    return jsonify({
        "taken_today": drug["taken_today"],
        "per_day": per_day  # <-- include this for the JS
    })

client = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY")
)

@app.route("/tts/drug/<drug_name>")
def tts_drug(drug_name):
    email = session["email"]
    user = drugs.find_one({"email": email})
    drug = next(d for d in user["drugs"] if d["drug_name"] == drug_name)

    info = drug["gemini_info"]

    script = f"""
    {drug['drug_name']}.
    Dosage: {drug['dosage']}.
    About the drug: {info['about']}.
    Possible side effects include: {", ".join(info['side_effects'])}.
    """

    audio_generator = client.text_to_speech.convert(
        text=script,
        voice_id="sB1b5zUrxQVAFl2PhZFp"
    )
    audio_bytes = b"".join(audio_generator)  # <-- consume generator into bytes

    return send_file(
        io.BytesIO(audio_bytes),
        mimetype="audio/mpeg",
        download_name=f"{drug_name}.mp3"
    )


if __name__ == '__main__':
    app.run(debug=True, port=5001)

