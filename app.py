"""
VillageCare+ Full Demo Prototype (PWA + Offline Sync + Admin)
"""
from flask import Flask, request, jsonify, render_template, send_from_directory
from datetime import datetime
import uuid
import os

app = Flask(__name__, static_folder='static', template_folder='templates')

# In-memory 'database'
PATIENTS = {}
VISITS = {}

# --- Helper function for triage ---
def triage_score(vitals):
    score = 0
    reasons = []
    age = vitals.get('age', 30)
    if age >= 60:
        score += 2
        reasons.append('Age >= 60')
    elif age >= 40:
        score += 1

    bp_sys = vitals.get('bp_sys')
    bp_dia = vitals.get('bp_dia')
    if bp_sys and bp_dia:
        if bp_sys >= 180 or bp_dia >= 120:
            score += 4
            reasons.append('Hypertensive crisis')
        elif bp_sys >= 140 or bp_dia >= 90:
            score += 2
            reasons.append('High blood pressure')
        elif bp_sys < 90 or bp_dia < 60:
            score += 2
            reasons.append('Low blood pressure')

    spo2 = vitals.get('spo2')
    if spo2 is not None:
        if spo2 < 90:
            score += 4
            reasons.append('Low SpO2')
        elif spo2 < 95:
            score += 2
            reasons.append('Slightly low SpO2')

    temp = vitals.get('temperature')
    if temp is not None:
        if temp >= 39.0:
            score += 3
            reasons.append('High fever')
        elif temp >= 37.5:
            score += 1
            reasons.append('Mild fever')

    glucose = vitals.get('glucose')
    if glucose:
        if glucose >= 300:
            score += 4
            reasons.append('Very high glucose')
        elif glucose >= 200:
            score += 2
            reasons.append('High glucose')

    symptoms = [s.lower() for s in vitals.get('symptoms', [])]
    for s in symptoms:
        if 'breath' in s or 'chest' in s:
            score += 3
            reasons.append('Severe symptom: ' + s)
        elif 'bleed' in s or 'faint' in s or 'unconscious' in s:
            score += 4
            reasons.append('Emergency symptom: ' + s)
        elif s:
            score += 0.5

    if score >= 7:
        level = 'Emergency'
        rec = 'Immediate referral to hospital / call ambulance'
    elif score >= 4:
        level = 'High'
        rec = 'Arrange urgent teleconsult and consider referral'
    elif score >= 2:
        level = 'Medium'
        rec = 'Schedule teleconsult; monitor vitals'
    else:
        level = 'Low'
        rec = 'Advice: home care, follow-up'

    return {'score': score, 'risk_level': level, 'recommendation': rec, 'reasons': reasons}

# --- ROUTES ---
@app.route('/')
def index():
    return render_template('INDEX.html')

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/api/patient', methods=['GET','POST'])
def api_patient():
    if request.method == 'POST':
        data = request.get_json() or {}
        patient_id = str(uuid.uuid4())
        patient = {
            'id': patient_id,
            'name': data.get('name','Anonymous'),
            'age': int(data.get('age',30)),
            'created_at': datetime.utcnow().isoformat()
        }
        PATIENTS[patient_id] = patient
        return jsonify(patient)
    else:
        return jsonify(list(PATIENTS.values()))

@app.route('/api/triage', methods=['POST'])
def api_triage():
    data = request.get_json() or {}
    patient_id = data.get('patient_id')
    patient = PATIENTS.get(patient_id)
    vitals = {
        'age': patient.get('age') if patient else data.get('age',30),
        'bp_sys': data.get('bp_sys'),
        'bp_dia': data.get('bp_dia'),
        'spo2': data.get('spo2'),
        'temperature': data.get('temperature'),
        'glucose': data.get('glucose'),
        'symptoms': data.get('symptoms', [])
    }
    result = triage_score(vitals)
    visit = {
        'id': str(uuid.uuid4()),
        'patient_id': patient_id,
        'vitals': vitals,
        'triage': result,
        'ts': datetime.utcnow().isoformat()
    }
    VISITS[visit['id']] = visit
    if patient:
        patient.setdefault('visits', []).append(visit)
    return jsonify(result)

@app.route('/api/teleconsult', methods=['POST'])
def api_teleconsult():
    data = request.get_json() or {}
    pid = data.get('patient_id')
    meeting = {
        'meeting_id': str(uuid.uuid4()),
        'patient_id': pid,
        'doctor': 'Dr. Prototype',
        'scheduled_at': datetime.utcnow().isoformat(),
        'join_url': 'https://example.com/tele/' + str(uuid.uuid4())
    }
    return jsonify(meeting)

@app.route('/api/emergency', methods=['POST'])
def api_emergency():
    data = request.get_json() or {}
    pid = data.get('patient_id')
    event = {
        'id': str(uuid.uuid4()),
        'patient_id': pid,
        'location': data.get('location'),
        'type': data.get('type'),
        'status': 'alerted',
        'ts': datetime.utcnow().isoformat()
    }
    print('EMERGENCY:', event)
    return jsonify(event)

@app.route('/api/sync/batch', methods=['POST'])
def api_sync_batch():
    items = request.get_json().get('items', [])
    acks = []
    for it in items:
        if it.get('type') == 'visit':
            visit = it.get('payload', {})
            visit_id = str(uuid.uuid4())
            record = {
                'id': visit_id,
                'patient_id': visit.get('patient_id'),
                'vitals': {k: visit.get(k) for k in ['bp_sys','bp_dia','spo2','temperature','glucose']},
                'symptoms': visit.get('symptoms',[]),
                'ts': visit.get('ts')
            }
            VISITS[visit_id] = record
            pid = visit.get('patient_id')
            if pid in PATIENTS:
                PATIENTS[pid].setdefault('visits', []).append(record)
            acks.append({'temp_id': it.get('temp_id'), 'server_id': visit_id})
    return jsonify({'acks': acks, 'received': len(acks)})

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/admin/data')
def api_admin_data():
    return jsonify({'patients': list(PATIENTS.values()), 'visits': list(VISITS.values())})

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=10000)

