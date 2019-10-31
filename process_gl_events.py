#!/usr/bin/env python3
'''Processes recent GitLab events to inform folks on the mailing list'''
import re
import time
import datetime

import dateutil.parser
import git
import gitlab

import cfg
import db_helper
import mail_helper

LOCAL_REPO = git.Repo(cfg.LOCAL_REPO_PATH)
assert not LOCAL_REPO.bare
assert not LOCAL_REPO.is_dirty()
assert LOCAL_REPO.head.ref == LOCAL_REPO.heads.master
LOCAL_REPO_GIT = LOCAL_REPO.git
# Ensure we are up to date
LOCAL_REPO_GIT.fetch('upstream')
LOCAL_REPO_GIT.merge('upstream/master')
# repo owner
GITLAB = gitlab.Gitlab.from_config(cfg.ADMIN_LOGIN_CFG_NAME, [])
assert GITLAB is not None
MAIN_REPO = GITLAB.projects.get(cfg.MAIN_REPO_ID)

#assumes that the remote of the source branch has been added
def find_mr_initial_hash(mr):
  source_project = GITLAB.projects.get(mr.source_project_id)
  initial_hash = source_project.branches.get(mr.source_branch).commit['id']
  # get the events of the source project again
  for event in source_project.events.list(sort='asc', all=True):
    if (dateutil.parser.parse(event.created_at) > dateutil.parser.parse(mr.created_at)) and event.action_name == 'pushed to':
      initial_hash = event.push_data['commit_from']
      break
  return initial_hash

# TODO: instead of using native git facilities to get the formatted patches, we should probably use the gitlab API so that we don't have to create a branch in the user's repo
def process_mr_event(event, mr):
  if (event.action_name == 'opened' or event.action_name == 'pushed to') and not mr.work_in_progress:
    if (mr.author['id'] == cfg.BOT_GITLAB_ID):
      return
    # Forward merge request as patchset to mailing list when it is created or updated
    print('updating ML')
    # Lookup the merge request to get info about how to send it to the ML
    primary_discussion = db_helper.Discussion(mr.id, 0)
    msg_id = db_helper.lookup_mail_thread(primary_discussion)
    version = None
    if msg_id is None:
      # This means we haven't already sent a version of this MR to the mailing list, so we send the header and setup the row
      # TODO: if the MR only has one patch, batch up the MR description w/ the commit description and use that as the header/prologue
      msg_id = mail_helper.send_mail(mr.title, mr.description + '\n\nMerge-Request Link: ' + mr.web_url)
      db_helper.link_discussion_to_mail(primary_discussion, msg_id)
      db_helper.make_version_entry(mr.id)
      version = 1
    else:
      version = db_helper.get_mr_version(mr.id) + 1
      db_helper.set_mr_version(mr.id, version)
    patch_prefix = 'PATCH v' + str(version) if version != 1 else 'PATCH'

    # If this is an opening event, and the MR has been updated since, we have problems
    top_hash = event.push_data['commit_to'] if event.action_name == 'pushed to' else find_mr_initial_hash(mr)

    # Add a branch referencing the top commit to ensure we can access this version
    source_project = GITLAB.projects.get(mr.source_project_id)
    source_project.branches.create({'branch': 'temporary_scraper_branch', 'ref': top_hash})
    # Add the project as a remote
    LOCAL_REPO_GIT.remote('add', 'mr_source', source_project.http_url_to_repo)
    LOCAL_REPO_GIT.fetch('mr_source')

    # Format patches for submission
    LOCAL_REPO_GIT.format_patch('origin..'+top_hash, subject_prefix=patch_prefix)

    # Remove the remote
    LOCAL_REPO_GIT.remote('remove', 'mr_source')

    # Remove the branch
    source_project.branches.delete('temporary_scraper_branch')

    #send them
    #TODO: if a patch was deleted, we won't end up sending anything, maybe send a notification about the deletions instead?
    for file_path in sorted(cfg.LOCAL_REPO_PATH.iterdir()):
      if file_path.name.endswith('.patch'):
        # Create the discussion and the thread, then link them

        with file_path.open() as patch_file:
          contents = patch_file.read()

        search = re.search(r'^From (?P<commithash>\w*)', contents)
        assert search is not None
        commit_hash = search.group('commithash')
        assert commit_hash is not None

        if db_helper.remember_commit_hash(mr, commit_hash):
          # We have already sent this patch, skip it
          continue

        patch_discussion = mr.discussions.create({'body': 'Discussion on commit ' + commit_hash})

        search = re.search(r'(?m)^Subject: (?P<subject>.*)$', contents)
        assert search is not None
        patch_subject = search.group('subject')
        assert patch_subject is not None
        patch_msg_id = mail_helper.send_mail(patch_subject, contents.split('\n\n', 1)[1], in_reply_to=msg_id)

        db_helper.link_discussion_to_mail(db_helper.Discussion(mr.id, patch_discussion.id), patch_msg_id)
    # Clean Up
    LOCAL_REPO_GIT.reset('origin/master', hard=True)
    LOCAL_REPO_GIT.clean(force=True)
    return

  if mr.author['id'] == cfg.BOT_GITLAB_ID:
    # Turn MR events into emails sent back to the submitter
    print('TODO')

def process_comment_event(event):
  if event.note['noteable_type'] != 'MergeRequest' or event.author_id == cfg.BOT_GITLAB_ID:
    return

  mr = MAIN_REPO.mergerequests.get(event.note['noteable_id'])
  note = mr.notes.get(event.target_id)
  print(note)

  # Find discussion object
  discussion_id = None
  if event.target_type == 'Note':
    # Not part of a discussion, just find the root email for the MR
    discussion_id = 0
  if event.target_type == 'DiscussionNote':
    # Find the discussion, by finding which discussion contains the note
    for discussion in mr.discussions.list(all=True):
      for discussion_note in discussion.attributes['notes']:
        print(discussion_note)
        if discussion_note['id'] == note.id:
          discussion_id = discussion.id
          break
      if discussion_id is not None:
        break
  if event.target_type == 'DiffNote':
    discussion_id = note.position['start_sha']
  assert discussion_id is not None

  discussion_entry = db_helper.Discussion(mr.id, discussion_id)
  mail_thread = db_helper.lookup_mail_thread(discussion_entry)
  mr_thread = db_helper.lookup_mail_thread(db_helper.Discussion(mr.id, 0))
  child = mail_thread is not None

  comment_body = note.body
  if not child and event.target_type == 'DiffNote':
    comment_body = '> `TODO: put diff information here`\n\n' + comment_body

  sent_msg_id = mail_helper.send_mail('Gitlab Merge-Request Comment', comment_body, in_reply_to=mail_thread if child else mr_thread)
  if child:
    db_helper.add_child(mail_thread, sent_msg_id)
  else:
    db_helper.link_discussion_to_mail(discussion_entry, sent_msg_id)

def process_event(event):
  print('Processing Event:\n'+str(event))
  if event.target_type == 'MergeRequest' or (event.project_id != cfg.MAIN_REPO_ID and event.action_name == 'pushed to'):
    mr = MAIN_REPO.mergerequests.get(event.target_id)
    process_mr_event(event, mr)
  if event.action_name == 'commented on':
    print('Processing Comment')
    process_comment_event(event)

def main():
  # find the time of the most recent event we have processed

  try:
    last_time_file = open('.last-time', "rt+")
    last_time_iso = last_time_file.read()
    last_time_file.close()
    last_time = dateutil.parser.parse(last_time_iso)
  except (FileNotFoundError, ValueError):
    last_time = datetime.datetime.now(datetime.timezone.utc)

  # TODO: Only ask for event in past few days
  # the GitLab API has extremely strange where some events are exclusive to the sorting order
  all_events = MAIN_REPO.events.list(sort='asc', all=True) + MAIN_REPO.events.list(sort='desc', all=True)

  # also get push events from the repos used in MRs, as the gitlab API docs are wrong and we can't rely on MR update events
  for mr in MAIN_REPO.mergerequests.list(all=True):
    source_project = GITLAB.projects.get(mr.source_project_id)
    # get the events
    for event in source_project.events.list(sort='asc', all=True):
      if (event.action_name == 'pushed to' and event.push_data['ref'] == mr.source_branch and
          dateutil.parser.parse(event.created_at) > dateutil.parser.parse(mr.created_at)):
        # HACK: set target_id to the MR ID, we should probably use commit.merge_requests() instead
        event.target_id = mr.id
        # insert the event into all_events based on the event time
        all_events.append(event)

  def sort_by_time(event):
    return dateutil.parser.parse(event.created_at)

  all_events.sort(key=sort_by_time)
  # Remove duplicates
  event_dictionary = {e.created_at: e for e in all_events}
  all_events = list(event_dictionary.values())

  for event in all_events:
    event_time = dateutil.parser.parse(event.created_at)
    if event_time > last_time:
      process_event(event)
      last_time = event_time

  last_time_file = open('.last-time', "wt")
  last_time_file.write(last_time.isoformat())
  last_time_file.close()

main()
