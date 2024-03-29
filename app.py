from flask import Flask, render_template, url_for, redirect, request, send_from_directory, jsonify, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_heroku import Heroku
import re
import random
import html
import os
import sys
import numpy as np
import random as r
# from numba import njit
import json
import random
import time
import hashlib
from base64 import b64encode
from os import urandom

from flask_socketio import SocketIO, send, join_room, leave_room



app = Flask(__name__)
app.secret_key = "ZpWNmtZBqTeLrJu6SWx6BueHGKWYxfD4fLz7CKTfcerZj4ffVhEG"

# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/bingogames'
heroku = Heroku(app)

app.config['SECRET_KEY'] = 'secret!'


socketio = SocketIO(app)




#      _       _        _
#   __| | __ _| |_ __ _| |__   __ _ ___  ___
#  / _` |/ _` | __/ _` | '_ \ / _` / __|/ _ \
# | (_| | (_| | || (_| | |_) | (_| \__ \  __/
#  \__,_|\__,_|\__\__,_|_.__/ \__,_|___/\___|
#


db = SQLAlchemy(app)

class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True, unique=True, autoincrement=True)
    players = db.Column(db.Text)
    board = db.Column(db.Text)
    host = db.Column(db.Text)
    date = db.Column(db.Text)
    last = db.Column(db.Text)
    open = db.Column(db.Boolean)

    def __init__(self, host):
        self.players = '{}'
        self.board = '0' * 75
        self.open = False
        self.host = host
        self.date = time.asctime(time.localtime(time.time()))
        self.last = '&nbsp;'
        self.open = True

    def get_players(self):
        return eval(self.players)

    def flip_square(self, num):
        b = list(self.board)
        b[num - 1] = str(1 - int(b[num - 1]))
        self.board = "".join(b)
        if b[num - 1] == '1':
            self.last = num_to_bingo(num)
        else:
            self.last = '&nbsp;'
        db.session.commit()

    def reset_board(self):
        self.board = '0' * 75
        self.last = '&nbsp;'
        db.session.commit()

    def add_player(self, player):
        pdict = self.get_players()
        pdict[player] = []
        self.players = str(pdict)
        db.session.commit()

    def remove_player(self, player):
        pdict = self.get_players()
        pdict.pop(player)
        self.players = str(pdict)
        db.session.commit()

    def deal(self, num_cards, players):
        # get new cards, and check that none of them are the same as the past cards
        pdict = self.get_players()
        oldCardIDs = []
        for player in pdict:
            oldCardIDs += pdict[player]
        newCardIDs = []
        num = num_cards + len(oldCardIDs)
        while len(list(set(oldCardIDs + newCardIDs))) < num:
            # this is not efficient,
            # ... but there is about a 0% chance this will ever be executed
            newCardIDs = get_n_cards(len(players) * num_cards)
        new_cardIDs_dict = {}
        for i, player in enumerate(players):
            newPlayerCardIDs = newCardIDs[i * num_cards : (i + 1) * num_cards]
            pdict[player] += newPlayerCardIDs
            new_cardIDs_dict[player] = newPlayerCardIDs
        self.players = str(pdict)
        db.session.commit()
        return new_cardIDs_dict

    def clear_cards(self, players):
        pdict = self.get_players()
        for player in players:
            pdict[player] = []
        self.players = str(pdict)
        db.session.commit()

    def delete_card(self, cardID):
        pdict = self.get_players()
        for player in pdict:
            if cardID in pdict[player]:
                pdict[player].remove(cardID)
                break
        self.players = str(pdict)
        db.session.commit()

    def set_open(self, open):
        self.open = open
        db.session.commit()

    def get_code(self):
        return id_to_code(self.id)

    def has_player(self, player):
        return player in self.get_players()



def id_to_code(id):
    return base_10_to_26(100 * id + 26**3)

def code_to_id(code):
    return int((base_26_to_10(code) - 26**3) / 100)

def get_game(code):
    id = code_to_id(code)
    return db.session.query(Game).filter(Game.id == id)[0]

def is_game(code):
    return len(list(db.session.query(Game).filter(Game.id == code_to_id(code)))) != 0


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text)
    salt = db.Column(db.Text)
    hashed_password = db.Column(db.Text)
    games = db.Column(db.Text)

    def __init__(self, username, password):
        self.username = username
        self.set_password(password)
        self.games = ''

    def set_password(self, password):
        self.salt = get_salt(12)
        self.hashed_password = SHA1(password + self.salt)
        db.session.commit()

    def add_game(self, game):
        g = [] if self.games == '' else self.games.split(',')
        g.append(game.get_code())
        self.games = ",".join(g)
        db.session.commit()

    def remove_game(self, code):
        g = self.games.split(',')
        g.remove(code)
        self.games = ",".join(g)
        db.session.commit()

    def has_game(self, game):
        return game.get_code() in self.games.split(',')


def is_user(username):
    return len(list(db.session.query(User).filter(User.username == username))) != 0

def get_user(username):
    return db.session.query(User).filter(User.username == username)[0]

def delete_game(code):
    db.session.query(Game).filter(Game.id == code_to_id(code)).delete()
    for user in db.session.query(User):
        if code in user.games.split(','):
            user.remove_game(code)
            break
    db.session.commit()

def delete_user(username):
    user = get_user(username)
    for code in user.games.split(','):
        delete_game(code)
    db.session.query(User).filter(User.username == username).delete()
    db.session.commit()



#  _          _
# | |__   ___| |_ __   ___ _ __ ___
# | '_ \ / _ | | '_ \ / _ | '__/ __|
# | | | |  __| | |_) |  __| |  \__ \
# |_| |_|\___|_| .__/ \___|_|  |___/
#              |_|



four = np.fromfile('board_encoding/four.dat', dtype=int).reshape(32760,4)
five = np.fromfile('board_encoding/five.dat', dtype=int).reshape(360360,5)


# @njit
def base_10_to_26(n):
    digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s = ""
    while n != 0:
        r = n % 26
        s = digits[r] + s
        n = n // 26
    return s

def base_26_to_10(s):
    s = s.upper()
    arr = [el for el in s][::-1]
    digits = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    n = 0
    while len(arr) != 0:
        n = digits.index(arr.pop()) + n * 26
    return n


# @njit
def find(row):
    if len(row) == 4:
        for i in range(32760):
            if row[0] == four[i][0] and row[1] == four[i][1] and row[2] == four[i][2] and row[3] == four[i][3]:
                return i
    else:
        for i in range(360360):
            if row[0] == five[i][0] and row[1] == five[i][1] and row[2] == five[i][2] and row[3] == five[i][3] and row[4] == five[i][4]:
                return i

def to_base_62(n):
    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    s = ""
    while n!=0:
        r = n % 62
        s = digits[r] + s
        n = n // 62
    return s

def to_base_10(base_62):
    base_62_arr = [el for el in base_62][::-1]
    digits = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    n = 0
    while len(base_62_arr) != 0:
        n = digits.index(base_62_arr.pop()) + n * 62
    return n

def encode(cardArray):
    card = cardArray.copy()

    for col in range(5):
        card.T[col] -= 15 * col + 1

    B = card.T[0]
    I = card.T[1]
    N = np.delete(card.T[2],2)
    G = card.T[3]
    O = card.T[4]

    num = 0
    for row in [B, I, N, G, O]:
        num = find(row) + 360360 * num

    return to_base_62(num)

def decode(base_62_num):
    card = np.zeros((5,5))
    base_10 = to_base_10(base_62_num)
    for i in range(5):
        num = base_10 % 360360
        if i == 2:
            card[2] = np.insert(four[num],2,-31)
        else:
            card[4 - i] = five[num]
        base_10 = base_10 // 360360

    cardArray = card.T
    for col in range(5):
        card[col] += 15 * col + 1

    return np.array(card, dtype=int).T

def get_random_card_id():

    B = r.sample(range(1,16), 5)
    I = r.sample(range(16,31), 5)
    N = r.sample(range(31,46), 5)
    G = r.sample(range(46,61), 5)
    O = r.sample(range(61,76), 5)

    cardArray = np.array([B, I, N, G, O]).T
    cardArray[2][2] = 0

    cardID = encode(cardArray)

    return cardID

def num_to_bingo(num):
    return 'BINGO'[(num - 1) // 15] + ' ' + str(num)

def get_n_cards(n):
    cardIDs = []
    while len(cardIDs) < n:
        num = 0
        for i in range(5):
            num = r.randint(1,(32760 if i == 2 else 360360) - 1) + 360360 * num
        cardID = to_base_62(num)
        if cardID not in cardIDs:
            cardIDs.append(cardID)
    return cardIDs


BINGO_TYPES = {
    "classic":
        [[[r,c] for c in range(5) if [r,c] != [2,2]] for r in range(5)]
      + [[[r,c] for r in range(5) if [r,c] != [2,2]] for c in range(5)]
      + [[[0,0],[1,1],[3,3],[4,4]]]
      + [[[0,4],[1,3],[3,1],[4,0]]],
    "blackout": [[[r,c] for c in range(5) for r in range(5) if [r,c] != [2,2]]]
}

def check_card(cardID, board, types):
    # print(board)
    out = []
    cardArray = decode(cardID)
    # print(cardArray)
    for t in types:
        for square_set in BINGO_TYPES[t]:
            # print("square_set =", square_set)
            for square in square_set:
                # print("cardnum =", cardArray[square[0]][square[1]])
                # print("board @ cn = ", board[cardArray[square[0]][square[1]] - 1])
                if board[cardArray[square[0]][square[1]] - 1] != '1':
                    break
            else:
                out.append(t)
                break
    return out


def get_cardHTML_array(cardIDs):
    cardHTML_array = []
    for cardID in cardIDs:
        cardHTML = f"<div id='{cardID}'>"
        cardHTML += ('<br>' * 5) + ('<br class="print">' * 5) + render_template('card.html', cardID=cardID, cardArray=decode(cardID).tolist())
        if cardID != cardIDs[-1]:
            cardHTML += '<div class="pagebreak"></div>'
        cardHTML += "</div>"
        cardHTML_array.append(cardHTML)
    return cardHTML_array


def SHA1(string):
    return hashlib.sha1(string.encode()).hexdigest()

def get_salt(n):
    return b64encode(urandom(n)).decode('utf-8')





#              _     _ _
#  _ __  _   _| |__ | (_) ___
# | '_ \| | | | '_ \| | |/ __|
# | |_) | |_| | |_) | | | (__
# | .__/ \__,_|_.__/|_|_|\___|
# |_|



@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', account_bar=get_account_bar())


@app.route('/new_cards/<int:num>')
def new_cards(num):
    return redirect('/cards/' + ','.join(get_n_cards(num)))


@app.route('/caller')
def caller():
    return render_template('caller.html')








#                  _             _
#   ___ ___  _ __ | |_ ___ _ __ | |_
#  / __/ _ \| '_ \| __/ _ | '_ \| __|
# | (_| (_) | | | | ||  __| | | | |_
#  \___\___/|_| |_|\__\___|_| |_|\__|



def get_account_bar():
    username = ''
    if 'username' in session:
        username = session['username']
    return render_template(
        'account_bar.html',
        loggedin=('username' in session),
        username=username,
        games=db.session.query(Game).filter(Game.host == username)
    )


@app.route('/game/<string:code>')
def game(code):
    if not is_game(code):
        return "No game found."
    game = get_game(code)
    if 'username' in session:
        if get_user(session['username']).has_game(game) or session['username'] == 'admin':
            return render_template(
                'game.html',
                account_bar = get_account_bar(),
                mode = 'host',
                code = game.get_code(),
                board = game.board,
                players = game.players,
                open = game.open
            )
    return render_template(
        'game.html',
        account_bar = get_account_bar(),
        mode = 'player',
        code = game.get_code(),
        board = game.board
    )


@app.route('/cards/<string:cardIDstrings>')
def cards(cardIDstrings):
    cardIDs = cardIDstrings.split(',')
    return render_template(
        'cards.html',
        mode='blank',
        num=len(cardIDs),
        cardHTML_array=get_cardHTML_array(cardIDs)
    )


@app.route('/play')
def play_blank():
    return render_template('join.html', account_bar=get_account_bar(), code="")


@app.route('/play/<string:code>')
def play(code):
    if not is_game(code):
        return f"No Game with code '{code}' found.", 404
    game = get_game(code)
    # if player has been in game
    if 'player-' + code in session:
        # if game currently has player
        if get_game(code).has_player(session['player-' + code]):
            cardIDs = game.get_players()[session['player-' + code]]
            return render_template(
                'play.html',
                code=code,
                mode='player',
                player=session['player-' + code],
                num=len(cardIDs),
                cardHTML_array=get_cardHTML_array(cardIDs)
            )
        # otherwise, player was removed from game, so remove from session
        session.pop('player-' + code, None)
    # otherwise, show form to join
    return render_template('join.html', account_bar=get_account_bar(), code=code)





#            _           _
#   __ _  __| |_ __ ___ (_)_ __
#  / _` |/ _` | '_ ` _ \| | '_ \
# | (_| | (_| | | | | | | | | | |
#  \__,_|\__,_|_| |_| |_|_|_| |_|



def initialize():
    db.drop_all()
    db.create_all()
    users = [
        ['a','7he9J08ghw9hr','f998a13487d4f1b7f273e80716fcebc02f1d69fd'],
        ['b','9f7Jge5jr6jSRj','b09007d934e774ab5a59194b52676503a157dfbd'],
        ['admin','8G13yNDvBowbFi4g','0dc86609d94f4098f01281f2427f29c19021d916']
    ]
    for username, salt, hash in users:
        u = User(username, 'blahblahblah')
        u.salt = salt
        u.hashed_password = hash
        db.session.add(u)
        db.session.commit()
    return 'Initialization is done.'



@app.route('/admin/<string:s>', methods=['POST', 'GET'])
def admin(s):
    if not is_user('admin'):
        return redirect('/')
    if 'username' not in session or session['username'] != 'admin':
        return 'Access denied.', 403

    if s == 'access' and request.method == 'GET':
        return render_template('admin.html', account_bar=get_account_bar(), all_games=db.session.query(Game), all_users=db.session.query(User))

    if s == 'delete_user' and request.method == 'POST':
        username = request.form['username']
        if not is_user(username):
            return jsonify({'success':'false', 'error':'no username exists'})
        if username == 'admin':
            return jsonify({'success':'false', 'error':"You can't delete the admin account."})
        delete_user(username)
        return jsonify({'success':'true'})


    return 'Access denied.', 403



#    __ _  ___ ___ ___ ___ ___
#   / _` |/ __/ __/ _ / __/ __|
#  | (_| | (_| (_|  __\__ \__ \
#   \__,_|\___\___\___|___|___/





@app.route('/host_access/<string:function>', methods=['POST'])
def host_access(function):
    if 'username' not in session:
        return jsonify({'success':'false', 'error':"You are not logged in."})
    if not is_user(session['username']):
        return jsonify({'success':'false', 'error':"You are logged into a user that no longer exists."})
    code = request.form['code']
    if not is_game(code):
        return jsonify({'success':'false', 'error':'No Game Found.'})
    game = get_game(code)
    if (not get_user(session['username']).has_game(game)) and session['username'] != 'admin':
        return jsonify({'success':'false', 'error':"You don't have access to edit this game."})

    if function == "get_players":
        pdict_old = game.get_players()
        pdict = {}
        for player in pdict_old:
            pdict[player] = [[cardID, decode(cardID).tolist()] for cardID in pdict_old[player]]
        return jsonify({'success':'true', 'player_dict':pdict})
    elif function == "get_open":
        return jsonify({'success':'true', 'open':game.open})

    elif function == "flip_square":
        game.flip_square(int(request.form['num']))
        socketio.emit('update board', room='game-'+code)
        return jsonify({'success':'true'})
    elif function == "reset_board":
        game.reset_board()
        socketio.emit('update board', room='game-'+code)
        return jsonify({'success':'true'})
    elif function == "remove_players":
        for p in request.form['players'].split(","):
            game.remove_player(p)
        socketio.emit('reload', {'players':request.form['players']}, room='player-'+code)
        socketio.emit('update players', room='game-'+code)
        return jsonify({'success':'true'})
    elif function == "check_for_bingo":
        bingo_dict = {}
        pdict = game.get_players()
        for p in request.form['players'].split(","):
            player_cardIDs = pdict[p]
            for cardID in player_cardIDs:
                check = check_card(cardID, game.board, BINGO_TYPES)
                if len(check) > 0:
                    if p not in bingo_dict:
                        bingo_dict[p] = []
                    bingo_dict[p].append([cardID, check])
        return jsonify({'success':'true', 'bingo_dict': bingo_dict})
    elif function == "deal":
        players = request.form['players']
        player_list = players.split(',')
        new_cardIDs_dict = game.deal(int(request.form['num_cards']), player_list)
        player_new_cardHTML_dict = {}
        for player in player_list:
            player_new_cardHTML_dict[player] = ''.join(get_cardHTML_array(new_cardIDs_dict[player]))
        socketio.emit('update players', room='game-'+code)
        socketio.emit('deal', {'players':players, 'player_new_cardHTML_dict':player_new_cardHTML_dict}, room='player-'+code)
        return jsonify({'success':'true'})
    elif function == "clear_cards":
        game.clear_cards(request.form['players'].split(','))
        socketio.emit('update players', room='game-'+code)
        socketio.emit('reload', {'players':request.form['players']}, room='player-'+code)
        return jsonify({'success':'true'})
    elif function == "delete_card":
        game.delete_card(request.form['cardID'])
        socketio.emit('update players', room='game-'+code)
        socketio.emit('delete card', {'player':request.form['player'],'cardID':request.form['cardID']}, room='player-'+code)
        return jsonify({'success':'true'})
    elif function == "set_open":
        game.set_open(bool(int(request.form['open'])))
        socketio.emit('update open', room='game-'+code)
        return jsonify({'success':'true', 'open':'true' if game.open else 'false'})
    elif function == "delete_game":
        delete_game(code)
        socketio.emit('reload', room='game-'+code)
        return jsonify({'success':'true'})
    else:
        return jsonify({'success':'false', 'error':"The function you tried to access doesn't exist."})




@app.route('/new_game', methods=['POST'])
def new_game():
    if 'username' not in session:
        return jsonify({'success':'false', 'error':"You're not logged in."})

    game = Game(host=session['username'])

    if not is_user(session['username']):
        return jsonify({'success':'false', 'error':"You are logged into a user that no longer exists."})
    db.session.add(game)
    db.session.commit()
    get_user(session['username']).add_game(game)
    return jsonify({'success':'true', 'code':game.get_code()})






@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    if not username.isalnum():
        return jsonify({'success':'false','error':'Username must contain only alphanumeric characters.'})
    if len(list(db.session.query(User).filter(User.username == request.form['username']))) != 0:
        return jsonify({'success':'false','error':'A user with this username already exists.'})
    db.session.add(User(request.form['username'],request.form['password']))
    db.session.commit()
    return jsonify({'success':'true'})



@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'success':'false', 'error':"You are not logged in."})
    if not is_user(session['username']):
        return jsonify({'success':'false', 'error':"You are logged into a user that no longer exists."})
    get_user(session['username']).set_password(request.form['password'])
    return jsonify({'success':'true'})






@app.route('/login', methods=['POST'])
def login():
    if not is_user(request.form['username']):
        return jsonify({'success':'false','error':'No user with this username exists.'})
    user = get_user(request.form['username'])
    if user.hashed_password != SHA1(request.form['password'] + user.salt):
        return jsonify({'success':'false','error':'The entered password is incorrect.'})
    session['username'] = request.form['username']
    return jsonify({'success':'true'})





@app.route('/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'success':'true'})







@app.route('/board_access', methods=['POST'])
def board_access():
    if not is_game(request.form['code']):
        return "No game found.",404
    game = get_game(request.form['code'])
    return jsonify({'success':'true', 'board':game.board, 'last':game.last})


@socketio.on('join game board room')
def join_game_board_room(data):
    join_room('game-' + data['code'])






@app.route('/join_game', methods=['POST'])
def join_game():
    code = request.form['code']
    if not is_game(code):
        return jsonify({'success':'false', 'error':'No game found.'})
    game = get_game(code)
    if not game.open:
        return jsonify({'success':'false', 'error':'This game is not open to be joined.'})
    if game.has_player(request.form['player']):
        return jsonify({'success':'false', 'error':'This name is already in use. Try another!'})
    if 'player-' + code in session and game.has_player(session['player-' + code]):
        return jsonify({'success':'false', 'error':f'You are already playing in this game with name <u>{session["player-" + code]}</u>.<br><br>Click <a href="/play/{code}">here</a> to play.'})
    session['player-' + code] = request.form['player']
    game.add_player(request.form['player'])
    socketio.emit('update players', room='game-'+code)
    return jsonify({'success':'true', 'code':code})


@socketio.on('join game room')
def join_game_room(data):
    join_room('player-' + data['code'])







@app.route('/leave_game', methods=['POST'])
def leave_game():
    code = request.form['code']
    game = get_game(code)
    if 'player-' + code in session:
        player = session['player-' + code]
        if game.has_player(player):
            game.remove_player(player)
        session.pop('player-' + code, None)
    socketio.emit('update players', room='game-'+code)
    return jsonify({'success':'true'})


@socketio.on('leave game room')
def leave_game_room(data):
    leave_room('player-' + data['code'])








if __name__ == "__main__":
    app.debug = True
    # app.run()
    socketio.run(app)
