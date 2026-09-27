import os
import re
import sqlite3
import math
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'loja.db')
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'troque-esta-chave')
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '1234')


def now_iso():
    return datetime.now().isoformat(timespec='seconds')


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def ensure_column(con, table, column, definition):
    cols = {r['name'] for r in con.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in cols:
        con.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

