# authentication
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from db import users
auth = Blueprint('auth', __name__)

@auth.route("/sign-up", methods=["GET", "POST"])
def sign_up():
    if request.method == "POST":
        firstname = request.form.get('first_name')
        lastname = request.form.get('last_name')
        password = request.form.get('password')
        email = request.form.get('email')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash("Passwords do not match", "error")
        elif users.find_one({"email": email}): # user already exists
            flash("User already exists, please choose another", "info")
        else:
            users.insert_one({
                'email': email,
                "password" : password,
                'firstname': firstname,
                'lastname': lastname,
                })
            return redirect(url_for("auth.login"))
    return render_template("sign_up.html")
        
@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        if (users.find_one({"email" : email})):
            user = users.find_one({"email" : email})
            if user['password'] == password:
                session["email"] = email
                return redirect(url_for('homescreen'))
            
    return render_template("login.html")    
    
@auth.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))