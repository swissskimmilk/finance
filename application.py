import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import sys
from datetime import datetime

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
    total = 0
    stocks = db.execute("select * from stocks where id = %s",
                        session["user_id"])
    for stock in stocks:
        info = lookup(stock['symbol'])
        stock['currentPrice'] = round(info['price'], 2)
        stock['averageCost'] = round((stock['initCost'] / stock['quantity']), 2)
        stock['initCost'] = round(stock['initCost'], 2)
        total += stock['currentPrice'] * stock['quantity']
        stock['totalValue'] = round(stock['currentPrice'] * stock['quantity'], 2)

    cash = db.execute("select cash from users where id = %s",
                        session["user_id"])

    total += cash[0]['cash']
    total = round(total, 2)
    cash[0]['cash'] = round(cash[0]['cash'], 2)
    return render_template("index.html", stocks=stocks, total=total, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        stock = request.form.get("symbol")
        quantity = request.form.get("quantity")
        info = lookup(request.form.get("symbol"))
        if info == None:
            return apology("must provide a valid symbol")
        currentCash = db.execute("select cash from users where id = %s",
                    session["user_id"])
        cashLeft = float(currentCash[0]['cash']) - (int(quantity) * float(info['price']))
        if (cashLeft) < 0:
            return apology("not enough money", 403)
        inTable = db.execute("select * from stocks where id=%s and symbol=%s",
                    session["user_id"], request.form.get("symbol").upper())
        if len(inTable) == 0:
            db.execute("insert into stocks (id, symbol, name, quantity, initCost) values(?, ?, ?, ?, ?)",
                        session["user_id"], request.form.get("symbol").upper(), info['name'], request.form.get("quantity"), info['price'] * float(request.form.get("quantity")))
        else:
            db.execute("update stocks set quantity = %s, initCost = %s where id = %s and symbol = %s",
                        inTable[0]['quantity'] + float(request.form.get("quantity")), inTable[0]['initCost'] + info['price'] * float(request.form.get("quantity")), session["user_id"], request.form.get("symbol").upper())
        db.execute("insert into transactions (datetime, id, name, symbol, bought, quantity, pricePer, total) values(?, ?, ?, ?, ?, ?, ?, ?)",
                    datetime.now(), session["user_id"], info['name'], request.form.get("symbol").upper(), True, request.form.get("quantity"), info['price'], info['price'] * float(request.form.get("quantity")))
        db.execute("update users set cash = %s where id = %s",
                    cashLeft, session["user_id"])

        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("select * from transactions where id = %s order by datetime desc",
                        session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide a symbol")
        info = lookup(request.form.get("symbol"))
        if info == None:
            return apology("must provide a valid symbol")
        print(info, file=sys.stderr)
        return render_template("quote.html", submitted=True, name=info['name'], symbol=info['symbol'], price=info['price'])
    else:
        return render_template("quote.html", submitted=False)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        if not request.form.get("username"):
            return apology("must provide username", 403)

        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("passwordComf"):
            return apology("must confirm password", 403)

        elif request.form.get("password") != request.form.get("passwordComf"):
            return apology("passwords must match", 403)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        if len(rows) != 0:
            return apology("account with username already exists", 403)

        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)",
                    request.form.get("username"), generate_password_hash(request.form.get("password")))

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("quantity"):
            return apology("must provide quantity", 403)
        stock = db.execute("select * from stocks where id = %s and symbol = %s",
                            session['user_id'], request.form.get("stocks"))
        if int(request.form.get("quantity")) > stock[0]['quantity']:
            return apology("you don't own that many shares", 403)
        info = lookup(stock[0]['symbol'])
        currentCash = db.execute("select cash from users where id = %s",
                                    session['user_id'])
        db.execute("update users set cash = %s where id = %s",
                    info['price'] * float(request.form.get("quantity")) + currentCash[0]['cash'], session['user_id'])
        newQuantity = stock[0]['quantity'] - int(request.form.get("quantity"))
        if newQuantity == 0:
            db.execute("delete from stocks where id = %s and symbol = %s",
                        session['user_id'], request.form.get("stocks"))
        else:
            db.execute("update stocks set quantity = %s, initCost = %s where id = %s and symbol = %s",
                        newQuantity, (stock[0]['initCost'] / stock[0]['quantity']) * newQuantity, session['user_id'], request.form.get("stocks"))
        db.execute("insert into transactions (datetime, id, name, symbol, bought, quantity, pricePer, total) values(?, ?, ?, ?, ?, ?, ?, ?)",
                    datetime.now(), session["user_id"], info['name'], request.form.get("stocks"), False, request.form.get("quantity"), info['price'], info['price'] * float(request.form.get("quantity")))
        return redirect("/")
    else:
        stocks = db.execute("select symbol from stocks where id = %s",
                            session["user_id"])
        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
