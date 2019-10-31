#!/usr/bin/env python3
'''Our DB maps mail to its top-level parent, and each parent to a) a merge request and b) one of the threads in that merge request
   the thread can either be the default one, a user-created thread, or an auto-generated thread for a patch
'''
import sqlite3
from collections import namedtuple

import cfg

DB_CONNECTION = sqlite3.connect(cfg.THREAD_DATABASE_PATH / 'threads.db')
DB_CURSOR = DB_CONNECTION.cursor()

#TODO: store an optional commit hash that the thread is referring to
DB_CURSOR.execute(r'CREATE TABLE IF NOT EXISTS threads (msg_id text, mr_id int, disc_id binary)')
DB_CURSOR.execute(r'CREATE TABLE IF NOT EXISTS children (child_id text, parent_id text)')
DB_CURSOR.execute(r'CREATE TABLE IF NOT EXISTS versions (mr_id int PRIMARY KEY, version int)')
DB_CURSOR.execute(r'CREATE TABLE IF NOT EXISTS commits (commit_hash binary PRIMARY KEY, mr_id int)')
DB_CONNECTION.commit()

Discussion = namedtuple('Discussion', 'mr_id disc_id')

def lookup_discussion(msg_id):
  DB_CURSOR.execute('SELECT * FROM threads WHERE msg_id=?', (msg_id,))
  row = DB_CURSOR.fetchone()
  return Discussion(row[1], row[2]) if row is not None else None

def lookup_mail_thread(discussion):
  DB_CURSOR.execute('SELECT * FROM threads WHERE mr_id=? AND disc_id=?', (discussion.mr_id, discussion.disc_id))
  row = DB_CURSOR.fetchone()
  return row[0] if row is not None else None

def link_discussion_to_mail(discussion, msg_id):
  DB_CURSOR.execute('INSERT INTO threads VALUES(?,?,?)', (msg_id, discussion.mr_id, discussion.disc_id))
  DB_CONNECTION.commit()

###

def get_root_msg_id(msg_id):
  DB_CURSOR.execute('SELECT * FROM children WHERE child_id=?', (msg_id,))
  row = DB_CURSOR.fetchone()
  return row[1] if row is not None else msg_id

def add_child(parent_msg_id, child_msg_id):
  DB_CURSOR.execute('INSERT INTO children VALUES(?,?)', (child_msg_id, parent_msg_id))
  DB_CONNECTION.commit()

###

def get_mr_version(mr_id):
  DB_CURSOR.execute('SELECT * FROM versions WHERE mr_id=?', (mr_id,))
  row = DB_CURSOR.fetchone()
  return row[1] if row is not None else None

def make_version_entry(mr_id):
  DB_CURSOR.execute('INSERT INTO versions VALUES(?,1)', (mr_id,))
  DB_CONNECTION.commit()

def set_mr_version(mr_id, version):
  DB_CURSOR.execute('UPDATE versions SET version=? WHERE mr_id=?', (version, mr_id))
  DB_CONNECTION.commit()

###

# inserts the commit and mr_id into the table and returns whether it was already present
def remember_commit_hash(mr_id, commit_hash):
  DB_CURSOR.execute('SELECT commit_hash FROM commits WHERE commit_hash=? AND mr_id=?', (commit_hash, mr_id))
  if DB_CURSOR.fetchone():
    return True
  DB_CURSOR.execute('INSERT INTO commits VALUES(?,?)', (commit_hash, mr_id))
  DB_CONNECTION.commit()
  return False
