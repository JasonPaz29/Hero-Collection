from flask import Flask, render_template, url_for, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import timedelta, datetime
import schedule

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = "XhTFLPqVmjMjs5cMyBLpNpcfC"
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=1)
db = SQLAlchemy(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
ADMIN = "ADMIN_JASON"

user_heroes = db.Table('user_heroes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('hero_id', db.Integer, db.ForeignKey('hero.id'), primary_key=True))

user_achievements = db.Table('user_achievements',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('achievement_id', db.Integer, db.ForeignKey('achievement.id'), primary_key=True))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), nullable=False)
    password = db.Column(db.String(70), nullable=False)
    tokens = db.Column(db.Integer, default=50)
    tokens_spent = db.Column(db.Integer, default=0)
    rolls_done = db.Column(db.Integer, default=0)
    last_daily_claim = db.Column(db.DateTime, default=datetime.utcnow)

    heroes = db.relationship('Hero', secondary=user_heroes, backref="owners")
    achievements = db.relationship("Achievement", secondary=user_achievements, backref="owners")

class Hero(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(1000), nullable=False)
    rarity = db.Column(db.String(50), nullable=False)


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Integer, default=0)
    difficulty = db.Column(db.String(50), nullable=False)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    offeredHero_id = db.Column(db.Integer, db.ForeignKey('hero.id'), primary_key=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    requestedHero_id = db.Column(db.Integer, db.ForeignKey('hero.id'), primary_key=True)
    status = db.Column(db.String(50), default="pending")

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])
    offered_hero = db.relationship("Hero", foreign_keys=[offeredHero_id])
    requested_hero = db.relationship("Hero", foreign_keys=[requestedHero_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))



@app.route('/')
def home():
    return render_template('index.html')  
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
    
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash("That username is already taken, please choose a different one!", "info")
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
    
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("You have successfully logged in", "success")
            return redirect(url_for('dashboard'))
        
        else:
            flash("The username or password do not match, try again", "info")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', category='info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.utcnow().date()
    last_claim = current_user.last_daily_claim.date()
    if today > last_claim:
        current_user.tokens += 50
        current_user.last_daily_claim = datetime.utcnow()
        db.session.commit()
    user_heroes = current_user.heroes
    return render_template('dashboard.html', user_heroes=user_heroes)

@app.route('/trade')
@login_required
def trade():
    other_users = []
    all_users = User.query.filter(User.id != current_user.id).all()
    for user in all_users:
        for hero in user.heroes:
            other_users.append({
                'owner': user.username,
                'hero': hero.name,
                'hero_id': hero.id,
                'owner_id': user.id,
                'rarity': hero.rarity
            })
    
    user_heroes = current_user.heroes
    incoming_trades = Trade.query.filter_by(receiver_id=current_user.id, status="pending").all()
    outgoing_trades = Trade.query.filter_by(sender_id=current_user.id).all()

    return render_template("trade.html", 
                         other_users=other_users, 
                         user_heroes=user_heroes,
                         incoming_trades=incoming_trades,
                         outgoing_trades=outgoing_trades)

@app.route('/create_trade', methods=['POST'])
@login_required
def create_trade():
    receiver_id = int(request.form.get("receiver_id"))
    offered_hero_id = int(request.form.get("offered_hero_id"))
    request_hero_id = int(request.form.get("request_hero_id"))

    sender_hero = Hero.query.filter_by(id=offered_hero_id).first()

    if not sender_hero:
        flash("This hero does not exist", "danger")
        return redirect(url_for('trade'))
    
    if sender_hero not in current_user.heroes:
        flash("You do not own this hero!", "danger")
        return redirect(url_for('trade'))
    
    if receiver_id == current_user.id:
        flash("You can't trade with yourself!", "danger")
        return redirect(url_for('trade'))
    
    receiver = User.query.filter_by(id=receiver_id).first()
    if request_hero_id not in receiver.heroes:
            flash("That user does not own that hero!", "danger")
            return redirect(url_for('trade'))
    
    existing_trade = Trade.query.filter_by(sender_id=current_user.id, receiver_id=receiver_id, offeredHero_id=offered_hero_id, requestHero_id=request_hero_id, status="pending").first()

    if existing_trade:
        flash("This trade already exists!", "danger")
        return redirect(url_for('trade'))
    
    new_trade = Trade(sender_id=current_user.id, receiver_id=receiver_id, offeredHero_id=offered_hero_id, requestHero_id=request_hero_id, status="pending")
    db.session.add(new_trade)
    db.session.commit()
    flash("The trade was sent successfully!", "success")
    return redirect(url_for("trade"))
    
@app.route('/accept_trade/<int:trade_id>')
@login_required
def accept_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()
    
    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('dashboard'))
    
    if current_user.id != trade.receiver_id:
        flash("You can't accept this trade!", "danger")
        redirect(url_for('dashboard'))

    if trade.status != "pending":
        flash("This trade no longer is available", "error")
        redirect(url_for('dashboard'))
    
    sender = User.query.get(trade.sender_id)

    if trade.offeredHero_id not in sender.heroes:
        flash("The other player no longer owns that hero!", "error")
        trade.status = "cancelled"
        return redirect(url_for('dashboard'))
    
    offered_hero = Hero.query.get(trade.offeredHero_id)
    requested_hero = Hero.query.get(trade.requestHero_id)


    current_user.heroes.remove(requested_hero)
    sender.heroes.remove(offered_hero)

    current_user.heroes.append(offered_hero)
    sender.heroes.append(requested_hero)

    trade.status = "accepted"
    db.session.commit()

    flash("The trade was completed successfully!", "info")
    return redirect(url_for('dashboard'))

@app.route('/decline_trade/<int:trade_id>')
@login_required
def decline_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()

    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('dashboard'))
    
    if current_user.id != trade.receiver_id:
        flash("You cannot deny this trade!", "danger")
        return redirect(url_for('dashboard'))
    
    if trade.status != "pending":
        flash("This trade no longer exists!", "error")
        return redirect(url_for('dashboard'))

    trade.status = "declined"
    db.session.commit()
    flash("The trade was declined.", "info")
    return redirect(url_for("dashboard"))

@app.route('/cancel_trade/<int:trade_id>')
@login_required
def cancel_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()

    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('dashboard'))
    
    if current_user.id != trade.receiver_id:
        flash("You cannot deny this trade!", "danger")
        return redirect(url_for('dashboard'))
    
    if trade.status != "pending":
        flash("This trade no longer exists!", "error")
        return redirect(url_for('dashboard'))

    trade.status = "cancelled"
    db.session.commit()
    flash("The trade was successfully cancelled.", "info")
    return redirect(url_for('dashboard'))

@app.route('/roll')
@login_required
def roll():
    return render_template('roll.html')

def rolling(chosen_rarity):
    numHeroes = Hero.query.count(rarity=chosen_rarity)
    index = random.randint(0, numHeroes-1)
    chosen_hero = Hero.query.filter_by(rarity=chosen_rarity).offset(index).first()
    return chosen_hero


@app.route('/perform_roll', methods=['POST'])
@login_required
def perform_roll():
    roll_type = request.form.get('roll_type')
    
    if roll_type == "basic":
        roll = random.randint(1, 100)
        if roll <= 50:
            chosen_rarity = "common"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 51 and roll <= 80:
            chosen_rarity = "rare"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 81 and roll <= 95:
            chosen_rarity = "epic"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 96:
            chosen_rarity = "legendary"
            chosen_hero = rolling(chosen_rarity)
        current_user.tokens -= 10
        current_user.tokens_spent += 10
    
    elif roll_type == "premium":
        roll = random.randint(1, 100)
        if roll <= 20:
            chosen_rarity = "common"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 21 and roll <= 65:
            chosen_rarity = "rare"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 66 and roll <= 90:
            chosen_rarity = "epic"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 91:
            chosen_rarity = "legendary"
            chosen_hero = rolling(chosen_rarity)
        current_user.tokens -= 25
        current_user.tokens_spent += 25
        
    elif roll_type == "legendary":
        roll = random.randint(1, 100)
        if roll <= 5:
            chosen_rarity = "common"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 6 and roll <= 40:
            chosen_rarity = "rare" 
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 41 and roll <= 75:
            chosen_rarity = "epic"
            chosen_hero = rolling(chosen_rarity)
        elif roll >= 76 and roll <= 99:
            chosen_rarity = "legendary"
            chosen_hero = rolling(chosen_rarity)
        elif roll == 100:
            chosen_rarity = "godly"
            chosen_hero = rolling(chosen_rarity)
        current_user.tokens -= 50
        current_user.tokens_spent += 50
    
    flash(f"You got {chosen_hero.name}! Which is a {chosen_hero.rarity}.", "success")
    current_user.rolls_done += 1
    if chosen_hero.id not in [hero.id for hero in current_user.heroes]:
        current_user.heroes.append(chosen_hero)
        db.session.commit()
    
    else:
        flash("You got a duplicate!", "dupe")
        if chosen_rarity == "common":
            current_user.tokens += 5
        elif chosen_rarity == "rare":
            current_user.tokens += 10
        elif chosen_rarity == "epic":
            current_user.tokens += 15
        elif chosen_rarity == "legendary":
            current_user.tokens += 25
        db.session.commit()
    return redirect(url_for('roll'))

@app.route('/achievements')
@login_required
def achievements():
    all_achievements = Achievement.query.all()
    user_achievements = current_user.achievements
    user_achievement_ids = [a.id for a in user_achievements]
    newly_unlocked_achievements = []
    
    return render_template('achievement.html',
        all_achievements=all_achievements,
        user_achievements=user_achievements,
        user_achievement_ids=user_achievement_ids,
        newly_unlocked_achievements=newly_unlocked_achievements
    )

@app.route('/check_achievements', methods=['POST'])
@login_required
def check_achievements():
    allAchivements = Achievement.query.all()

    for achievement in allAchivements:
        if achievement in current_user.achievements:
            pass
        else:
            if achievement.type == "hero_collection":
                if achievement.value == 1 and current_user.heroes.count() >= 1:
                    current_user.achievements.append(achievement)
                elif achievement.value == 5 and current_user.heroes.count() >= 5:
                    current_user.achievements.append(achievement)
                elif achievement.value == 10 and current_user.heroes.count() >= 10:
                    current_user.achievements.append(achievement)
                elif achievement.value == 20 and current_user.heroes.count() >= 20:
                    current_user.achievements.append(achievement)
                elif achievement.value == 25 and current_user.heroes.count() >= 25:
                    current_user.achievements.append(achievement)
            elif achievement.type == "roll_count":
                if achievement.value == 1 and current_user.rolls_done >= 1:
                    current_user.achievements.append(achievement)
                elif achievement.value == 10 and current_user.rolls_done >= 10:
                    current_user.achievements.append(achievement)
                elif achievement.value == 25 and current_user.rolls_done >= 25:
                    current_user.achievements.append(achievement)
                elif achievement.value == 50 and current_user.rolls_done >= 50:
                    current_user.achievements.append(achievement)
                elif achievement.value == 100 and current_user.rolls_done >= 100:
                    current_user.achievements.append(achievement)
            elif achievement.type == "tokens_spent":
                if achievement.value == 10 and current_user.tokens_spent >= 10:
                    current_user.achievements.append(achievement)
                elif achievement.value == 25 and current_user.tokens_spent >= 25:
                    current_user.achievements.append(achievement)
                elif achievement.value == 50 and current_user.tokens_spent >= 50:
                    current_user.achievements.append(achievement)
                elif achievement.value == 100 and current_user.tokens_spent >= 100:
                    current_user.value.achievements.append(achievement)
                elif achievement.value == 250 and current_user.tokens_spent >= 250:
                    current_user.achievements.append(achievement)
                elif achievement.value == 500 and current_user.tokens_spent >= 500:
                    current_user.achievements.append(achievement)
            elif achievement.type == "goku":
                for hero in current_user.heroes:
                    if hero.name == 'goku':
                        current_user.achievements.append(achievement)
    return redirect(url_for('achievements'))

@app.route('/hero_index')
@login_required
def hero_index():
    user_heroes = current_user.heroes
    all_heroes = Hero.query.all()
    return render_template("hero_index.html", user_heroes=user_heroes, all_heroes=all_heroes)

@app.route('/add_heroes')
@login_required
def add_heroes():
    if current_user.username != ADMIN:
        flash("You are not allowed on there!", "danger")
        return redirect(url_for('home'))
                #Finish the achievements, make the Goku character, make an index for the heroes so the User can see which heroes he has and doesn't, hide Goku
                #Fix the daily token issue, patch out issues with the achievement page, update the navbar, !!Maybe update the User database to add trade_count
                #After that, debugging begins!!!


#Make either the shop(maybe a way to get tokens?) or the achievements.

    #Goals For Today:
#Make the Home Page Look Nice, and Have links to most parts,
#Make the Registration and Login Page, Little to no AI Usage if possible
#Set up a dashboard Page that can handle: Collected Heroes, Trade Requests, and A link to the rolling page.





#Account Signup and Login System
#Turn this code into a Card Collecting game where you have to collect all the heroes from a 
#wheel and each hero has a different rarity (ex. Goku has a 1/100k and Luffy has a 1/3). A Token System where you get tokens from duplicates and also buy spins
#Implement a trading system where you can offer trades between another user
if __name__ == '__main__':
    app.run(debug=True) 