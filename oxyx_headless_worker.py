import json, time, hashlib, uuid, requests, sqlite3, redis, os, threading

# Konfigurasi
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
DB_PATH = 'oxyx.db'
API_BASE = "https://ff.garena.com/api/v1"   # Endpoint internal (rekayasa)
SECRET_KEY = "oxyx_master_key_10x"

r = redis.from_url(REDIS_URL)

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

def update_db(uid, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k, v in kwargs.items():
        c.execute(f'UPDATE accounts SET {k}=? WHERE uid=?', (v, uid))
    conn.commit()
    conn.close()

def guest_login(uid, password):
    """Login via API, dapatkan token session."""
    payload = {
        "guest_uid": uid,
        "guest_password": password,
        "device_id": str(uuid.uuid4()),
        "app_version": "1.102.1",
        "os": "android"
    }
    headers = {"X-OxyX-Sign": hashlib.sha256(json.dumps(payload).encode()).hexdigest()}
    resp = requests.post(f"{API_BASE}/auth/guest", json=payload, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token")
    return None

def start_match(token):
    """Masuk antrian dan dapatkan match_id."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{API_BASE}/match/start", json={"mode": "solo_ranked"}, headers=headers)
    return resp.json().get("match_id")

def simulate_match(token, match_id, uid):
    """
    Kirim heartbeat dan hasil akhir match palsu: selalu menang, EXP maksimum.
    """
    headers = {"Authorization": f"Bearer {token}"}
    # Durasi match simulasi: langsung kirim hasil
    result = {
        "match_id": match_id,
        "uid": uid,
        "placement": 1,
        "kills": 99,
        "damage": 9999,
        "survival_time": 1200,
        "exp_gain": 5000   # EXP besar
    }
    resp = requests.post(f"{API_BASE}/match/result", json=result, headers=headers)
    return resp.json().get("success", False)

def process_account(task):
    uid = task['uid']
    pwd = task['password']
    target = task['target_level']
    update_db(uid, status='running')
    token = guest_login(uid, pwd)
    if not token:
        update_db(uid, status='error')
        return
    current_level = 1
    while current_level < target:
        match_id = start_match(token)
        if match_id:
            if simulate_match(token, match_id, uid):
                # Update level berdasarkan EXP (di sini disederhanakan)
                current_level += 1
                update_db(uid, current_level=current_level)
        time.sleep(2)  # delay biar tidak overload
    update_db(uid, status='completed')

def worker_loop():
    """Ambil task dari Redis, proses langsung."""
    while True:
        _, task_raw = r.blpop('bot:task')
        task = json.loads(task_raw)
        threading.Thread(target=process_account, args=(task,)).start()

if __name__ == '__main__':
    # Jalankan API Flask di thread terpisah (jika ingin gabung)
    from oxyx_api import app as flask_app
    threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=5000, debug=False)).start()
    worker_loop()