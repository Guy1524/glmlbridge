#!/usr/bin/env python3
'''Sends mail to address specified in config'''
import ssl
import smtplib
import email.utils
import email.message

import cfg

ssl_ctx = ssl.create_default_context()
server = smtplib.SMTP(cfg.smtpServer, cfg.smtpServerPort)
if cfg.smtpEncryption == 'ssl' or cfg.smtpEncryption == 'tls':
  server.starttls(ssl_ctx)
if cfg.smtpUser:
  server.login(cfg.smtpUser, cfg.smtpPass if cfg.smtpPass is not None else '')

def send_mail(subject, body, in_reply_to=None):
  msg_id = email.utils.make_msgid()
  msg = email.message.EmailMessage()

  msg['Subject'] = subject
  msg['From'] = cfg.BOT_NAME + ' <{0}>'.format(cfg.BOT_MAIL_ADDRESS)
  msg['To'] = cfg.MAILING_LIST_ADDRESS
  if in_reply_to is not None:
    msg['In-Reply-To'] = in_reply_to
  msg['Message-ID'] = msg_id

  if not cfg.BIDIRECTIONAL_COMM:
    body = 'This message was generated from a Gitlab event, do not reply!\n\n' + body

  msg.set_content(body)
  server.sendmail(cfg.BOT_MAIL_ADDRESS, cfg.MAILING_LIST_ADDRESS, msg.as_string())
  return msg_id
