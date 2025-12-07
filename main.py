from flask import Flask, render_template, url_for, request, redirect, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user, logout_user, login_required, current_user, UserMixin, LoginManager
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import timedelta, datetime
import schedule
from collections import defaultdict
from battle_logic import simulate_battle, BattleResult

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

user_hero_history = db.Table('user_hero_history',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('hero_id', db.Integer, db.ForeignKey('hero.id'), primary_key=True),
    db.Column('acquired_at', db.DateTime, default=datetime.utcnow))

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
    security_question = db.Column(db.String(200), nullable=True)
    security_answer_hash = db.Column(db.String(200), nullable=True)
    battle_wins = db.Column(db.Integer, default=0)
    battle_losses = db.Column(db.Integer, default=0)


    heroes = db.relationship('Hero', secondary=user_heroes, backref="owners")
    heroes_history = db.relationship('Hero', secondary=user_hero_history, backref="historical_owners")
    achievements = db.relationship("Achievement", secondary=user_achievements, backref="owners")

class Hero(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    image = db.Column(db.String(1000), nullable=False)
    rarity = db.Column(db.String(50), nullable=False)
    greek_type = db.Column(db.String(50), nullable=True)
    
    base_hp = db.Column(db.Integer, default=100)
    base_attack = db.Column(db.Integer, default=10)
    base_defense = db.Column(db.Integer, default=5)


class Achievement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Integer, default=0)
    difficulty = db.Column(db.String(50), nullable=False)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    offeredHero_id = db.Column(db.Integer, db.ForeignKey('hero.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requestedHero_id = db.Column(db.Integer, db.ForeignKey('hero.id'), nullable=False)
    status = db.Column(db.String(50), default="pending")

    sender = db.relationship("User", foreign_keys=[sender_id])
    receiver = db.relationship("User", foreign_keys=[receiver_id])
    offered_hero = db.relationship("Hero", foreign_keys=[offeredHero_id])
    requested_hero = db.relationship("Hero", foreign_keys=[requestedHero_id])

class LineUp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    hero_1 = db.Column(db.Integer, db.ForeignKey('hero.id'), nullable=True)
    hero_2 = db.Column(db.Integer, db.ForeignKey('hero.id'), nullable=True)
    hero_3 = db.Column(db.Integer, db.ForeignKey('hero.id'), nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_queued = db.Column(db.Boolean, default=False)       
    is_challenger = db.Column(db.Boolean, default=False)    

    last_battle_log = db.Column(db.Text, nullable=True)
    last_battle_winner = db.Column(db.String(50), nullable=True)
    last_battle_loser = db.Column(db.String(50), nullable=True)
    last_battle_unseen = db.Column(db.Boolean, default=False)

    hero1 = db.relationship("Hero", foreign_keys=[hero_1])
    hero2 = db.relationship("Hero", foreign_keys=[hero_2])
    hero3 = db.relationship("Hero", foreign_keys=[hero_3])

class CombatHero:
    def __init__(self, hero):
        self.id = hero.id
        self.name = hero.name
        self.greek_type = hero.greek_type
        self.base_hp = hero.base_hp
        self.base_attack = hero.base_attack
        self.base_defense = hero.base_defense
        self.attack = hero.base_attack
        self.defense = hero.base_defense
        self.health = hero.base_hp

    def basehp(self):
        return self.base_hp

def no_security_question_set():
    users = User.query.all()
    for user in users:
        if not user.security_question or not user.security_answer_hash:
            return render_template('set_security.html', user=user)
        elif not user.battle_wins and not user.battle_losses:
            user.battle_wins = 0
            user.battle_losses = 0
            db.session.commit()
    return

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('index.html')  

@app.route('/set_security_question/<int:user_id>', methods=['GET', 'POST'])
def set_security_question(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('register'))

    if request.method == 'POST':
        security_question = request.form.get('question')
        security_answer = request.form.get('answer')

        if not security_question or not security_answer:
            flash("Both security question and answer are required.", "warning")
            return redirect(url_for('set_security_question', user_id=user_id))

        hashed_answer = generate_password_hash(security_answer.strip().lower(), method='pbkdf2:sha256')

        user.security_question = security_question
        user.security_answer_hash = hashed_answer
        db.session.commit()

        flash("Security question and answer set successfully!", "success")
        return redirect(url_for('login'))

    return render_template('set_security.html', user=user)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get("username")
        user = User.query.filter_by(username=username).first()
        
        if not user:
            flash("User not found.", "password_info")
            return redirect(url_for('forgot_password'))

        if not user.security_question or not user.security_answer_hash:
            flash("Security question and answer not set for this user.", "error")
            return redirect(url_for('forgot_password'))
        
        return redirect(url_for('answer_security', user_id=user.id))
    return render_template('forgot_password.html')

@app.route('/answer_security/<int:user_id>', methods=['GET', 'POST'])
def answer_security(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        security_answer = request.form.get('answer')

        if not security_answer:
            flash("Security answer is required.", "warning")
            return redirect(url_for('answer_security', user_id=user_id))

        if check_password_hash(user.security_answer_hash, security_answer.strip().lower()):
            flash("Security answer verified! You can now reset your password.", "success")
            return redirect(url_for('reset_password', user_id=user_id))
        else:
            flash("Incorrect security answer. Please try again.", "warning")
            return redirect(url_for('answer_security', user_id=user_id))

    return render_template('answer_security.html', user=user)

@app.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if new_password != confirm:
            flash("Passwords do not match!", "warning")
            return redirect(url_for('reset_password', user_id=user_id))

        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        user.password = hashed_password
        db.session.commit()

        flash("Password reset successfully! You can now log in with your new password.", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html', user=user)
    
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
        flash("You have successfully registered!", "info")
        return redirect(url_for('set_security_question', user_id=new_user.id))
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
    no_security_question_set()
    today = datetime.utcnow().date()
    last_claim = current_user.last_daily_claim.date()
    if today > last_claim:
        current_user.tokens += 25
        current_user.last_daily_claim = datetime.utcnow()
        flash("You have claimed your daily 25 tokens!", "success")
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
                'rarity': hero.rarity,
                'image': hero.image
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
    requested_hero_id = int(request.form.get("requested_hero_id"))
    receiverHasHero = False

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
    for hero in receiver.heroes:
        if requested_hero_id == hero.id:
            receiverHasHero = True
            break
        else:
            pass
    if not receiverHasHero:
        flash("That user does not own that hero!", "danger")
        return redirect(url_for('trade'))
        
    
    existing_trade = Trade.query.filter_by(sender_id=current_user.id, receiver_id=receiver_id, offeredHero_id=offered_hero_id, requestedHero_id=requested_hero_id, status="pending").first()

    if existing_trade:
        flash("This trade already exists!", "danger")
        return redirect(url_for('trade'))
    
    new_trade = Trade(sender_id=current_user.id, receiver_id=receiver_id, offeredHero_id=offered_hero_id, requestedHero_id=requested_hero_id, status="pending")
    db.session.add(new_trade)
    db.session.commit()
    flash("The trade was sent successfully!", "success")
    return redirect(url_for("trade"))
    
@app.route('/accept_trade/<int:trade_id>', methods=["POST"])
@login_required
def accept_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()
    receiverHasHero = False
    
    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('trade'))
    
    if current_user.id != trade.receiver_id:
        flash("You can't accept this trade!", "danger")
        redirect(url_for('trade'))

    if trade.status != "pending":
        flash("This trade no longer is available", "error")
        redirect(url_for('trade'))
    
    sender = User.query.get(trade.sender_id)

    for hero in sender.heroes:
        if trade.offeredHero_id == hero.id:
            receiverHasHero = True
            break
        else:
            pass
    if not receiverHasHero:
        flash("The other user no longer owns that hero!", "error")
        trade.status = "cancelled"
        db.session.commit()
        return redirect(url_for('trade'))
        
    
    offered_hero = Hero.query.get(trade.offeredHero_id)
    requested_hero = Hero.query.get(trade.requestedHero_id)


    current_user.heroes.remove(requested_hero)
    sender.heroes.remove(offered_hero)

    current_user.heroes.append(offered_hero)
    sender.heroes.append(requested_hero)

    trade.status = "accepted"
    db.session.commit()

    flash("The trade was completed successfully!", "info")
    return redirect(url_for('dashboard'))

@app.route('/decline_trade/<int:trade_id>', methods=["POST"])
@login_required
def decline_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()

    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('trade'))
    
    if current_user.id != trade.receiver_id:
        flash("You cannot deny this trade!", "danger")
        return redirect(url_for('trade'))
    
    if trade.status != "pending":
        flash("This trade no longer exists!", "error")
        return redirect(url_for('trade'))

    trade.status = "declined"
    db.session.commit()
    flash("The trade was declined.", "info")
    return redirect(url_for("trade"))

@app.route('/cancel_trade/<int:trade_id>', methods=["POST"])
@login_required
def cancel_trade(trade_id):
    trade = Trade.query.filter_by(id=trade_id).first()

    if not trade:
        flash("This trade does not exist!", "error")
        return redirect(url_for('trade'))
    
    if current_user.id != trade.sender_id:
        flash("You cannot deny this trade!", "danger")
        return redirect(url_for('trade'))
    
    if trade.status != "pending":
        flash("This trade no longer exists!", "error")
        return redirect(url_for('trade'))

    trade.status = "cancelled"
    db.session.commit()
    flash("The trade was successfully cancelled.", "info")
    return redirect(url_for('trade'))

@app.route('/roll')
@login_required
def roll():
    return render_template('roll.html')

def rolling(chosen_rarity):
    numHeroes = Hero.query.filter_by(rarity=chosen_rarity).count()
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
    if chosen_hero.id not in [hero.id for hero in current_user.heroes_history]:
        current_user.heroes_history.append(chosen_hero)
        flash("New hero added to your collection!", "info")
        db.session.commit()
    
    else:
        flash("You got a duplicate!", "dupe")
        if chosen_rarity == "common":
            current_user.tokens += 5
            flash("You got 5 tokens!", "dupe")
        elif chosen_rarity == "rare":
            current_user.tokens += 10
            flash("You got 10 tokens!", "dupe")
        elif chosen_rarity == "epic":
            current_user.tokens += 15
            flash("You got 15 tokens!", "dupe")
        elif chosen_rarity == "legendary":
            current_user.tokens += 25
            flash("You got 25 tokens!", "dupe")
        elif chosen_rarity == "godly":
            current_user.tokens += 50
            flash("You got 50 tokens!", "dupe")
        db.session.commit()
    check_achievements()
    return redirect(url_for('roll'))

@app.route('/achievements')
@login_required
def achievements():
    check_achievements()
    all_achievements = Achievement.query.order_by(Achievement.type, Achievement.value, Achievement.id).all()
    user_achievements = current_user.achievements
    user_achievement_ids = {a.id for a in user_achievements}
    achievements_by_type = defaultdict(list)

    def current_value_for(achievement):
        if achievement.type == "hero_collection":
            return len(current_user.heroes)
        if achievement.type == "roll_count":
            return current_user.rolls_done
        if achievement.type == "tokens_spent":
            return current_user.tokens_spent
        if achievement.type == "battle_wins":
            return current_user.battle_wins
        if achievement.type == "goku":
            return 1 if any(hero.name == "Goku" for hero in current_user.heroes) else 0
        if achievement.type == "creator":
            return 1 if any(hero.name == "The Creator" for hero in current_user.heroes) else 0
        return 0

    for achievement in all_achievements:
        is_unlocked = achievement.id in user_achievement_ids
        target_value = achievement.value or 0
        if achievement.type in ("goku", "creator") and target_value == 0:
            target_value = 1

        current_value = current_value_for(achievement)
        progress_percent = 0
        if target_value > 0:
            progress_percent = int((current_value / target_value) * 100)
        if progress_percent > 100:
            progress_percent = 100
        if is_unlocked:
            progress_percent = 100

        achievements_by_type[achievement.type].append({
            "achievement": achievement,
            "is_unlocked": is_unlocked,
            "target_value": target_value,
            "current_value": current_value,
            "progress_percent": progress_percent
        })

    newly_unlocked_achievements = []
    ordered_types = sorted(achievements_by_type.keys())
    
    return render_template('achievement.html',
        all_achievements=all_achievements,
        user_achievements=user_achievements,
        user_achievement_ids=user_achievement_ids,
        newly_unlocked_achievements=newly_unlocked_achievements,
        achievements_by_type=achievements_by_type,
        ordered_types=ordered_types
    )

def check_achievements():
    all_achievements = Achievement.query.all()
    amount_of_heroes = len(current_user.heroes)
    obtained_any = False

    def unlock(achievement):
        nonlocal obtained_any
        current_user.achievements.append(achievement)
        obtained_any = True

    for achievement in all_achievements:
        if achievement in current_user.achievements:
            continue

        if achievement.type == "hero_collection":
            if amount_of_heroes >= achievement.value:
                unlock(achievement)

        elif achievement.type == "roll_count":
            if current_user.rolls_done >= achievement.value:
                unlock(achievement)

        elif achievement.type == "tokens_spent":
            if current_user.tokens_spent >= achievement.value:
                unlock(achievement)

        elif achievement.type == "goku":
            if any(hero.name == "Goku" for hero in current_user.heroes):
                unlock(achievement)
        
        elif achievement.type == "creator":
            if any(hero.name == "The Creator" for hero in current_user.heroes):
                unlock(achievement)
        
        elif achievement.type == "battle_wins":
            if current_user.battle_wins >= achievement.value:
                unlock(achievement)

    if obtained_any:
        db.session.commit()
        flash("You have unlocked an achievement!", "success")

    return

                
    

@app.route('/hero_index', methods=['GET'])
@login_required
def hero_index():
    user_heroes = current_user.heroes
    user_hero_history = current_user.heroes_history
    all_heroes = Hero.query.all()
    return render_template("hero_index.html", user_heroes=user_heroes, all_heroes=all_heroes, user_hero_history=user_hero_history)

@app.route('/type_index', methods=['GET'])
@login_required
def type_index():
    user_heroes = current_user.heroes
    all_heroes = Hero.query.all()
    greek_types = set(hero.greek_type for hero in all_heroes if hero.greek_type)
    return render_template("type_index.html", user_heroes=user_heroes, all_heroes=all_heroes, greek_types=greek_types)

@app.route("/arena", methods=['GET', 'POST'])
@login_required
def arena():
    roster = list(current_user.heroes)
    queued_lineup = LineUp.query.filter_by(is_queued=True).order_by(LineUp.timestamp.desc()).first()
    queued_owner = User.query.get(queued_lineup.user_id) if queued_lineup else None
    queued_heroes = [queued_lineup.hero1, queued_lineup.hero2, queued_lineup.hero3] if queued_lineup else []
    users_queued_lineups = LineUp.query.filter_by(is_queued=False, user_id=current_user.id).order_by(LineUp.timestamp.desc()).first()

    if users_queued_lineups and users_queued_lineups.last_battle_unseen:
        battle_log = []
        if users_queued_lineups.last_battle_log:
            battle_log = users_queued_lineups.last_battle_log.split("\n")
        battle_result = BattleResult(
            users_queued_lineups.last_battle_winner,
            users_queued_lineups.last_battle_loser,
            battle_log
        )
        users_queued_lineups.last_battle_unseen = False
        db.session.commit()
        return render_template("battle_result.html", battle_result=battle_result, battle_log=battle_log, team_a=None, team_b=None)
            

    if request.method == 'POST':
        intent = request.form.get('intent')

        if intent == 'queue':
            hero_ids = [request.form.get('team_a_hero1'), request.form.get('team_a_hero2'), request.form.get('team_a_hero3')]
            if not all(hero_ids):
                flash("Select three heroes to queue.", "warning")
                return redirect(url_for('arena'))

            hero_ids = [int(hid) for hid in hero_ids]
            if len(set(hero_ids)) < 3:
                flash("Use different heroes in each slot.", "warning")
                return redirect(url_for('arena'))

            owned_ids = {hero.id for hero in roster}
            if not set(hero_ids).issubset(owned_ids):
                flash("You can only queue heroes you own.", "danger")
                return redirect(url_for('arena'))

            if LineUp.query.filter_by(is_queued=True).first():
                flash("There is already a lineup queued in the arena! Challenge them or wait!", "warning")
                return redirect(url_for('arena'))

            LineUp.query.filter_by(is_queued=True).update({"is_queued": False})
            new_lineup = LineUp(
                user_id=current_user.id,
                hero_1=hero_ids[0],
                hero_2=hero_ids[1],
                hero_3=hero_ids[2],
                is_queued=True,
                is_challenger=False,
                timestamp=datetime.utcnow()
            )
            db.session.add(new_lineup)
            db.session.commit()
            flash("Your lineup is now waiting in the arena.", "success")
            return redirect(url_for('arena'))

        elif intent == 'challenge':
            if not queued_lineup:
                flash("No lineup is currently queued to challenge.", "warning")
                return redirect(url_for('arena'))

            challenger_ids = [request.form.get('team_b_hero1'), request.form.get('team_b_hero2'), request.form.get('team_b_hero3')]
            if not all(challenger_ids):
                flash("Select three heroes to challenge with.", "warning")
                return redirect(url_for('arena'))

            challenger_ids = [int(hid) for hid in challenger_ids]
            if len(set(challenger_ids)) < 3:
                flash("Use different heroes in each challenger slot.", "warning")
                return redirect(url_for('arena'))

            owned_ids = {hero.id for hero in roster}
            if not set(challenger_ids).issubset(owned_ids):
                flash("You can only challenge with heroes you own.", "danger")
                return redirect(url_for('arena'))

            team_a_models = [queued_lineup.hero1, queued_lineup.hero2, queued_lineup.hero3]
            if not all(team_a_models):
                flash("The queued lineup is incomplete.", "warning")
                return redirect(url_for('arena'))

            team_b_models = [Hero.query.get(hid) for hid in challenger_ids]
            if not all(team_b_models):
                flash("One of the selected challenger heroes could not be found.", "danger")
                return redirect(url_for('arena'))

            team_a = [CombatHero(hero) for hero in team_a_models]
            team_b = [CombatHero(hero) for hero in team_b_models]
            raw_result = simulate_battle(team_a, team_b, queued_owner.username, current_user.username)

            winner_name = queued_owner.username if raw_result.winner == queued_owner.username else current_user.username
            loser_name = current_user.username if raw_result.winner == queued_owner.username else queued_owner.username
            result = BattleResult(winner_name, loser_name, raw_result.log)

            if winner_name == queued_owner.username:
                queued_owner.battle_wins += 1
                current_user.battle_losses += 1
                queued_owner.tokens += 15
                current_user.tokens += 5
            else:
                current_user.battle_wins += 1
                queued_owner.battle_losses += 1
                queued_owner.tokens += 5
                current_user.tokens += 15

            queued_lineup.last_battle_log = "\n".join(raw_result.log)
            queued_lineup.last_battle_winner = winner_name
            queued_lineup.last_battle_loser = loser_name
            queued_lineup.last_battle_unseen = True

            team_a_state = [{
                "name": hero.name,
                "greek_type": hero.greek_type,
                "hp": max(hero.health, 0),
                "base_hp": hero.base_hp,
                "attack": hero.attack,
                "defense": hero.defense
            } for hero in team_a]

            team_b_state = [{
                "name": hero.name,
                "greek_type": hero.greek_type,
                "hp": max(hero.health, 0),
                "base_hp": hero.base_hp,
                "attack": hero.attack,
                "defense": hero.defense
            } for hero in team_b]

            queued_lineup.is_queued = False
            db.session.commit()

            return render_template(
                "battle_result.html",
                battle_result=result,
                battle_log=raw_result.log,
                team_a={
                    "label": "Posted Lineup",
                    "owner": queued_owner.username if queued_owner else "Unknown",
                    "heroes": team_a_state
                },
                team_b={
                    "label": "Challenger",
                    "owner": current_user.username,
                    "heroes": team_b_state
                }
            )

    return render_template(
        "arena.html",
        user_heroes=roster,
        available_heroes=roster,
        queued_heroes=queued_heroes,
        queued_owner=queued_owner.username if queued_owner else None,
        challenger_heroes=roster,
        battle_wins=current_user.battle_wins,
        battle_losses=current_user.battle_losses
    )

@app.route('/add_heroes', methods=['GET', 'POST'])
@login_required
def add_heroes():
    if current_user.username != ADMIN:
        flash("You are not allowed on there!", "danger")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        name = request.form.get("name")
        description = request.form.get("description")
        rarity = request.form.get("rarity")
        image = request.form.get("image")
    
        if not name:
            flash("Hero name is required", "warning")
            return redirect(url_for("add_heroes"))
        
        if not description:
            flash("Hero description is required", "warning")
            return redirect(url_for('add_heroes'))
        
        if not rarity:
            flash("Hero rarity is required", "warning")
            return redirect(url_for('add_heroes'))
        
        if not image:
            flash("Hero image is required", "warning")
            return redirect(url_for('add_heroes'))
        
        new_hero = Hero(name=name, description=description, rarity=rarity, image=image)
        db.session.add(new_hero)
        db.session.commit()
        flash("The hero was successfully added!", "success")
        return redirect(url_for('add_heroes'))
    return render_template("add_heroes.html")


@app.route('/add_achievements', methods=['GET', 'POST'])
@login_required
def add_achievements():
    if current_user.username != ADMIN:
        flash("You are not allowed on there!", "danger")
        return redirect(url_for('home'))

    if request.method == "POST":
        name = request.form.get('name')
        description = request.form.get('description')
        type = str(request.form.get('type'))
        value = request.form.get('value')
        difficulty = request.form.get('difficulty')
    
        if not name:
            flash("Achievement name is needed.", "warning")
            return redirect(url_for('add_achievements'))
        
        if not description:
            flash("Achievement description is needed.", "warning")
            return redirect(url_for('add_achievements'))
        
        if not type:
            flash("Achievement type is needed.", "warning")
            return redirect(url_for('add_achievements'))

        if not value:
            flash("Achievement value is needed.", "warning")
            return redirect(url_for('add_achievements'))
        
        if not difficulty:
            flash("Achievement difficulty is needed.", "warning")
            return redirect(url_for('add_achievements'))
        
        new_achievement = Achievement(name=name, description=description, type=type, value=value, difficulty=difficulty)
        db.session.add(new_achievement)
        db.session.commit()
        flash("The achievement was successfully added!", "success")
    
    return render_template("add_achievements.html")


if __name__ == '__main__':
    app.run(host="0.0.0.0", port="5000", debug=True) 
