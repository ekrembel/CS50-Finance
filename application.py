import os
import requests
from datetime import datetime, date
import json
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    i = 1
    total_spent = 0
    rows = []

    # Query database for the data of the stock shares and total fund user currently owns
    user_data = db.execute("SELECT * FROM users WHERE person_id= :person_id;", person_id=session["username"])
    cash = user_data[0]["cash"]

    # Loop through the array of user data
    while i < len(user_data):

        # Check if user still owns the share
        if user_data[i]["status"] == "Yours":

            # Store data of current stock shares in variables
            symbol = user_data[i]["symbol"]
            name = user_data[i]["company"]
            shares = user_data[i]["shares"]
            price = user_data[i]["price"]
            total = user_data[i]["total"] 

            # Store variables in a list         
            row = {
                "symbol": symbol,
                "name": name,
                "shares": shares,
                "price": usd(price),
                "total": usd(total)           
            }

            # Calculate total value of currently owned shares
            total_spent += total 
            
            # Store lists in array
            rows.append(row)

        i = i + 1

    # Calculate cash amount user currently has    
    cashRemain = usd(cash - total_spent)

    # Convert the amount to USD format
    value = usd(cash)

    # Redirect user to my shares page  
    return render_template("portfolio.html", rows=rows, cashRemain=cashRemain, value=value)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via GET by clicking a lick
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST buy submitting a form    
    else:
        status = "Yours"
        transaction_type = "Bought"
        username = session["username"]
        user_hash = "---"

        # Query database for data of user
        user_data = db.execute("SELECT * FROM users WHERE person_id= :person_id;", person_id=session["username"])
        
        # Store cash user owns in variable
        cash = user_data[0]["cash"]
        
        # Create unique additional usernames for the user for each transaction
        num = len(user_data)
        temp_username = f"{username}{num}" 

        # Store details of the share user wants to buy
        company = request.form.get("buy")
        shares = request.form.get("shares")

        # Fetch current price of the share
        data = lookup(company)
        name = data["name"]
        symbol = data["symbol"]
        price = data["price"]

        # Calculate total price based on the number of shares user wants to buy
        total = price * float(shares)

        # Get and store current date and time in the desired format
        today = date.today()
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")

        # Add details of shares user bought to database
        db.execute("INSERT INTO users (username, hash, cash, symbol, company, shares, price, total, date, time, person_id, status, boughtorsold) VALUES (:username, :hash, :cash, :symbol, :company, :shares, :price, :total, :date, :time, :person_id, :status, :transaction_type);", username=temp_username, hash=user_hash, cash=cash, symbol=symbol, company=name, shares=shares, price=price, total=total, date=today, time=current_time, person_id=session["username"], status=status, transaction_type=transaction_type)
        
        # Inform user that transaction is completed
        flash("Bought!")

        # Redirect user to home page
        return redirect("/")   


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # To skip first element in array of user data
    i = 1
    rows = []

    # Query database for some data of user
    user_data = db.execute("SELECT * FROM users WHERE person_id = :person_id;", person_id=session["username"])
    
    # Loop through array of data
    while i < len(user_data):

        # Get some data and store them in variables
        symbol = user_data[i]["symbol"]
        shares = user_data[i]["shares"]
        price = user_data[i]["price"]
        date = user_data[i]["date"]
        time = user_data[i]["time"]
        transaction_type = user_data[i]["boughtorsold"]
        transacted = str(date) + " " + str(time)

        # Store variables in a list
        row = {
            "symbol": symbol,
            "shares": shares,
            "price": price,
            "transacted": transacted,
            "transaction": transaction_type
        }

        # Store list in an array
        rows.append(row)
        i = i + 1 
       
    return render_template("history.html", rows=rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        session["username"] = request.form.get("username")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username;", username=session["username"])

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            loginFailed = "Username or password is incorrect!"
            return render_template("login.html", loginFailed=loginFailed)
            # return apology("invalid username and/or password", 403)


        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    flash("Logged out!")
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via GET by clicking a link
    if request.method == "GET":
        return render_template("quote.html")
    
    # User reached route via POST by submiting a form
    else:

        # Get and store user input in a variable
        userInquiry = request.form.get("quote")

        # Fetch details of company and stock share
        data = lookup(userInquiry)

        # Return an error message if user input does not match with any company symbol
        if not data:
            error_message = "Symbol cannot be found!"
            return render_template("quote.html", notFound=error_message)
        
        # Otherwise return the details of the company and its stock share
        name = data["name"]
        symbol = data["symbol"]
        price = usd(data["price"])
        return render_template("quoted.html", name=name, price=price, symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via GET by clicking a link
    if request.method == "GET":
        return render_template("register.html")
    
    # User reached route via POST by submitting a form
    else:
        # Get and store user input  
        username = request.form.get("email")
        password = request.form.get("password") 

        # Generate a hash for the password
        hash = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8) 

        # Add user name and hash to database   
        db.execute("INSERT INTO users (username, hash, person_id) VALUES (:username, :hash, :person_id);", username=username, hash=hash, person_id=username)
        
        # Inform user that user is registered
        flash("Registered!")
        return render_template("login.html")
        



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    symbol_list = ["Select"]
    i = 0
    j = 0

    # Query database for some data of user
    user_data = db.execute("SELECT * FROM users WHERE person_id= :person_id;", person_id=session["username"])
    
    # Loop through array of user data
    while i < len(user_data):

        # Check if user still owns the share
        if user_data[i]["status"] == "Yours":
            company_symbol = user_data[i]["symbol"]

            # Add symbol in the list if symbol is not already in the symbol list
            if company_symbol not in symbol_list:
                symbol_list.append(company_symbol)
        i = i + 1 

    # User reached route via GET by clicking a link       
    if request.method == "GET":
        return render_template("sell.html", symbol_list=symbol_list)
    
    # User reached route by submitting the form 
    else:
        status = "Gone"
        transaction_type = "Sold"
        username = session["username"]

        # Create unique additional usernames for the user for each transaction
        num = len(user_data)
        temp_username = f"{username}{num}" 

        user_hash = "---"

        # Store total fund user currently owns in a variable
        cash = user_data[0]["cash"]

        # Get and store user input in variables
        company_to_sell = request.form.get("select")
        shares = int(request.form.get("shares"))

        # Fetch data of company and its stock share details
        data = lookup(company_to_sell)
        price = data["price"]

        # Convert number of shares sold to string that shows a negative number
        shares_sold = f"-{shares}"

        # Get and store current date and time in variables in desired format
        today = date.today()
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")

        # Store error message in a variable
        not_matched = "Failed: Please double check the number of shares and the symbol of the company."
        
        # Loop through array of user data
        while j < len(user_data):

            # Check if user owns the share they try to sell
            if user_data[j]["symbol"] == company_to_sell and user_data[j]["shares"] == shares and user_data[j]["status"] == "Yours":
                username = user_data[j]["username"]
                
                # Calculate revenue or loss from this sale
                cost = user_data[j]["total"]
                difference = cost - (price * float(shares))

                # Update total fund of user based on the revenue or loss
                cash_final = cash + difference

                # Update status of share on database as sold
                db.execute("UPDATE users SET status = :status WHERE username = :username;", status=status, username=username)
                
                # Add details of transaction to database
                db.execute("INSERT INTO users (username, hash, cash, symbol, shares, price, date, time, person_id, status, boughtorsold) VALUES (:username, :hash, :cash, :symbol, :shares, :price, :date, :time, :person_id, :status, :transaction_type);", username=temp_username, hash=user_hash, cash=cash, symbol=company_to_sell, shares=shares_sold, price=price, date=today, time=current_time, person_id=session["username"], status=status, transaction_type=transaction_type)
                
                # Update total fund of user on database
                db.execute("UPDATE users SET cash = :cash WHERE person_id= :person_id", cash=cash_final, person_id=session["username"])
                
                # Inform user that transaction is completed
                flash("Sold!")
                return render_template("sell.html")
            j = j + 1

        # Return an error message if user is trying to sell a share they do not own    
        return render_template("sell.html", notMatched=not_matched)    


@app.route("/myAccount", methods=["GET", "POST"])
@login_required
def myAccount():

    # User reached route via GET by clicking a link
    if request.method == "GET":
        return render_template("myAccount.html")


@app.route("/addFund", methods=["GET", "POST"])
@login_required
def addFund():

    # Query database for total fund user has
    cash = db.execute("SELECT cash FROM users WHERE username = :username;", username=session["username"])
    
    # User reached route via GET by clicking a link
    if request.method == "GET":

        # Return total fund that user has
        balance = usd(cash[0]["cash"])
        return render_template("addFund.html", balance=balance)
    
    # User reached via POST by submitting a form
    else:

        # Get and store amount user wants to add to their fund
        amount = request.form.get("fund")

        # Calculate user fund after transaction 
        cash_updated = float(amount) + cash[0]["cash"]

        # Update total fund of user on database
        db.execute("UPDATE users SET cash = :cash_updated WHERE username = :username;", cash_updated=cash_updated, username=session["username"])
        
        # Inform user that transaction is completed
        flash("Fund has been added to your account!")
        return render_template("addFund.html", balance=cash_updated)



@app.route("/changePassword", methods=["GET", "POST"])
@login_required
def changePassword():

    # User reached route via GET by clicking a link
    if request.method == "GET":
        return render_template("changePassword.html")
    
    # User reached route via POST by submitting a password change request form
    else:

        # Get and store user input
        password = request.form.get("currentPassword")
        new_password = request.form.get("newPassword")

        # Query database for hash of user password
        user_hash = db.execute("SELECT hash FROM users WHERE username = :username;", username=session["username"])
        
        # Check if user provided correct password
        if check_password_hash(user_hash[0]["hash"], password):

            # Generate new hash for the new password
            hash = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=8)

            # Update hash on database
            db.execute("UPDATE users SET hash = :hash WHERE username = :username;", hash=hash, username=session["username"])
            
            # Inform user that password is changed
            flash("Your password has been updated.")
            return render_template("changePassword.html") 



@app.route("/deleteAccount", methods=["GET", "POST"])
@login_required
def deleteAccount():

    # User reached via GET by clicking a link
    if request.method == "GET":
        return render_template("deleteAccount.html")
    
    # User reached route by submitting a form
    else:

        # Get and store user input
        password = request.form.get("password")

        # Query database for hash of user password
        user_hash = db.execute("SELECT hash FROM users WHERE username = :username;", username=session["username"])
        
        # Check if user provided the right password
        if check_password_hash(user_hash[0]["hash"], password):

            # Delete user data from database
            db.execute("DELETE FROM users WHERE person_id = :person_id;", person_id=session["username"])
            
            # Clear session
            session.clear()

            # Inform user that their account is deleted
            flash("Your account has been deleted. We'll miss you!")
            return  render_template("login.html")
        
        # Return an error message if user provides wrong password
        else:
            error_message = "Password is incorrect!"  
            return render_template("deleteAccount.html", errorMessage=error_message)  
          


@app.route("/forgotPassword", methods=["GET", "POST"])
def forgotPassword():

    # User reached route via GET by clicking a link
    if request.method == "GET":
        return render_template("forgotPassword.html")
    
    # User reached route via POST by submitting a form
    else:

        # Get and store user input (username)
        username = request.form.get("username")

        # Query database for username
        user_name = db.execute("SELECT username FROM users WHERE username = :username;", username=username)
        
        # Return an error message if user name does not exist on the database
        if len(user_name) == 0:
            not_found = "Username does not exist"
            return render_template("forgotPassword.html", notFound=not_found)

        # Get and store user input (new password)     
        new_password = request.form.get("newPassword")

        # Generate a new hash for the new password
        hash = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=8)

        # Update hash on database
        db.execute("UPDATE users SET hash = :hash WHERE username = :username;", hash=hash, username=username)
        
        # Inform user that password is updated
        flash("Your password has been updated.")
        return render_template("login.html") 



def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
