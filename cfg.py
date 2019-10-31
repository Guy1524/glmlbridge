#!/usr/bin/env python3
'''Configuration file, suited for wine by default'''
import pathlib
import datetime

# configuration name to be found in the config files
BOT_LOGIN_CFG_NAME = 'bot'
# we need this to a) read unreferenced commits and b) lock merge requests
ADMIN_LOGIN_CFG_NAME = 'admin'

# paths
# path to output of `filter` script
PATCHES_PATH = pathlib.Path.home() / 'patches/'
LOCAL_REPO_PATH = pathlib.Path.home() / 'wine'
THREAD_DATABASE_PATH = pathlib.Path.home()

BOT_NAME = 'Gitlab Bot'
BOT_MAIL_ADDRESS = 'bot@localhost'
# Login information of the bot, matches git's sendemail.*
smtpServer = 'localhost'
smtpServerPort = 1025
smtpUser = None
smtpPass = None
smtpEncryption = None

# Address of the mailing list where patches are submitted
MAILING_LIST_ADDRESS = 'dereklesho52@Gmail.com'

# ID of the gitlab bot which submits mail
BOT_GITLAB_ID = 2

# ID of main repo
MAIN_REPO_ID = 3
# ID of bot's fork
FORK_REPO_ID = 4

# Time at which incomplete patchsets are considered stale
PATCH_PROCESS_TIMEOUT = datetime.datetime.now() - datetime.timedelta(minutes=15)

# Whether to allow two-way communication between GitLab and the ML
BIDIRECTIONAL_COMM = True
