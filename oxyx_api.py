from flask import Flask, request, jsonify
import json, sqlite3, redis, os

app = Flask(__name__)
r = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379'))
DB_PATH = 'oxyx.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts
                 (uid TEXT PRIMARY KEY, password TEXT, target_level INTEGER,
                  current_level INTEGER DEFAULT 1, status TEXT DEFAULT 'queued',
                  created_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/start', methods=['POST'])
def start_bot():
    if 'datfile' in request.files:
        file = request.files['datfile']
        raw = file.read().decode('utf-8')
        data = json.loads(raw)
    elif request.form.get('guest_json'):
        data = json.loads(request.form['guest_json'])
    else:
        return jsonify({'error': 'No data'}), 400

    guest_info = data['guest_account_info']
    uid = guest_info['com.garena.msdk.guest_uid']
    pwd = guest_info['com.garena.msdk.guest_password']
    target = int(request.form.get('target_level', 50))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO accounts (uid, password, target_level, current_level, status, created_at) VALUES (?,?,?,1,"queued",datetime("now"))',
              (uid, pwd, target))
    conn.commit()
    conn.close()

    task = {'uid': uid, 'password': pwd, 'target_level': target}
    r.rpush('bot:task', json.dumps(task))
    return jsonify({'message': f'Akun {uid} dimasukkan ke antrian.'})

@app.route('/api/status/all')
def status_all():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT uid, current_level, target_level, status FROM accounts ORDER BY created_at DESC LIMIT 50')
    rows = c.fetchall()
    conn.close()
    return jsonify([{'uid': r[0], 'current_level': r[1], 'target_level': r[2], 'status': r[3]} for r in rows])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)