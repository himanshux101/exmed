from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from tempfile import gettempdir
import datetime

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    stocks = db.execute("SELECT t.stock, t.numstocks, u.cash FROM 'transaction' t, users u WHERE t.id = :uid GROUP BY t.time" ,\
                      uid=session["user_id"])
    final_stocks = {}
    total_cash = 0
    remaining_cash = 0
    
    if not stocks:
        return apology("error in showing the index")
        
    for stock in stocks:
        remaining_cash = stock['cash']
        total_cash = remaining_cash
        stock_info = lookup(stock['stock'])
        if stock_info != None and stock_info['name'] not in final_stocks:
            stock_info = lookup(stock['stock'])
            final_stocks[stock_info['name']] = stock
            final_stocks[stock_info['name']]['symbol'] = stock_info['symbol']
            final_stocks[stock_info['name']]['name'] = stock_info['name']
            final_stocks[stock_info['name']]['cur_price'] = float(stock_info['price'])
            final_stocks[stock_info['name']]['numstocks'] = float(stock['numstocks'])
            final_stocks[stock_info['name']]['total_price'] = float(stock_info['price']) * float(stock['numstocks'])
        elif stock_info != None:
            stock_info = lookup(stock['stock'])
            final_stocks[stock_info['name']]['numstocks'] += float(stock['numstocks'])
            final_stocks[stock_info['name']]['total_price'] += float(stock_info['price']) * float(stock['numstocks'])
        
        
    for stock in final_stocks.values():
        total_cash += stock['total_price']
        stock['cur_price'] = usd(stock['cur_price'])
        stock['total_price'] = usd(stock['total_price'])
        

    remaining_cash = usd(remaining_cash)
    total_cash = usd(total_cash)
    return render_template("index.html", stocks=final_stocks, remaining_cash=remaining_cash, total_cash=total_cash)
    
    

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    
    if request.method == "POST":
        if not request.form.get("stock"):
            return apology("Please enter a stock")
            
        if not request.form.get("numstocks"):
            return apology("Enter valid number of stocks")
            
        if int(request.form.get("numstocks")) < 0:
            return apology("Enter valid number of stocks")
            
        stock = lookup(request.form.get("stock"))
        
        
        if not stock:
            return apology("Enter a valid stock")
            
        result = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        cash_left = result[0]["cash"]
        now = datetime.datetime.now()
        f = '%Y-%m-%d %H:%M:%S'
        date = now.strftime(f)
        
        if cash_left < stock["price"]:
            return apology("not enough cash")
            
        add = db.execute("INSERT INTO 'transaction' (id, stock, numstocks, price, time) VALUES(:id, :stock, :numstocks, :price, :time)", \
                         id=session["user_id"], stock=request.form.get("stock").upper(), numstocks=request.form.get("numstocks"), \
                         price=stock["price"]*float(request.form.get("numstocks")), time=date )
        if not add:
            return apology("Error in adding transaction")
        
        sum = db.execute("UPDATE users SET cash = cash - :value", value=stock["price"]*float(request.form.get("numstocks")) )
        if not sum:
            return apology("error in updating the main tabel")
            
        return redirect(url_for("index"))

    else:
        return render_template("buy.html")
            

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = db.execute("SELECT stock, numstocks, price, time FROM 'transaction' WHERE id = :user_id GROUP BY TIME",\
                          user_id=session["user_id"])
                          
    for hist in history:
        if hist != None:
            stock_info = lookup(hist["stock"])
            hist["prev_price"] = hist["price"] / hist["numstocks"]
            hist["prev_price"] = usd(hist["prev_price"])
    
    if not history:
        return apology("Error in history")
        
    return render_template("history.html", history=history )

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or request.form.get("password") != rows[0]["hash"]:
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    if request.method == "POST":
        
        if not request.form.get("quote"):
            return apology("please enter your quote")
            
        quote = lookup(request.form.get("quote"))
        
        
        return render_template("quoted.html", quote=quote)
        
        
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    session.clear()
    
    if request.method == "POST":
        
        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password1"):
            return apology(request.form.get("password1"))
            
        # ensure conform password was submitted
        elif not request.form.get("password2"):
            return apology("must provide password again")
            
        if request.form.get("password1") != request.form.get("password2"):
            return apology("Password don't match. Try Again!!!")
            
        
        result = db.execute("INSERT INTO users (username, hash) values (:username, :hash)", username=request.form.get("username"), hash=request.form.get("password1"))
        
        if not result:
            return apology("SQL error")
            
        session["user_id"] = result
        
        return redirect(url_for("index"))



    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        if not request.form.get("stock"):
            return apology("Please enter a stock")
            
        if not request.form.get("numstocks"):
            return apology("Enter valid number of stocks")
            
        if int(request.form.get("numstocks")) < 0:
            return apology("Enter valid number of stocks")
            
        stocks_to_sell = float((-1)* int(request.form.get("numstocks")))
        stock = lookup(request.form.get("stock"))
        
        
        if not stock:
            return apology("Enter a valid stock")
            
        result = db.execute("SELECT * FROM users WHERE id = :id", id=session["user_id"])
        cash_left = result[0]["cash"]
        now = datetime.datetime.now()
        f = '%Y-%m-%d %H:%M:%S'
        date = now.strftime(f)
        
        # if cash_left < stock["price"]:
        #     return apology("not enough cash")
            
        sell = db.execute("INSERT INTO 'transaction' (id, stock, numstocks, price, time) VALUES(:id, :stock, :numstocks, :price, :time)", \
                         id=session["user_id"], stock=request.form.get("stock").upper(), numstocks=(-1)*float(request.form.get("numstocks")), \
                         price=stock["price"]*float(stocks_to_sell), time=date )
        if not sell:
            return apology("Error in adding transaction")
        
        update_price = db.execute("UPDATE users SET cash = cash + :value", value=stock["price"]*float(request.form.get("numstocks")) )
        if not update_price:
            return apology("error in updating the main tabel")
            
        return redirect(url_for("index"))

    else:
        return render_template("sell.html")
        
@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        return apology("do it man")
        # do something
    else:
        return render_template("account.html")
    
        
        
        
        

