#!/usr/bin/python

"""
A program for managing challenges, attempt and solutions.

"""

# TODO: change all imports to be import <module> instead of from <module> import <function>
# [It increases quality of code searching]
import os
import sys

import webapp2
import program_handler
import review_handler
import rpc_handler
import jeeqs_request_handler

sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))

from models import *
from status_code import *
from program_tester import *
from user_handler import UserHandler

from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import ndb

import lib.markdown as markdown

import core

## This for enabling ctypes to improve jinja2 error messages, which is unfortunately not working!
## see: http://stackoverflow.com/a/3694434/195579
#if os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
#  # Enable ctypes for Jinja debugging
#  import sys
#  from google.appengine.tools.dev_appserver import HardenedModulesHook
#  assert isinstance(sys.meta_path[0], HardenedModulesHook)
#  sys.meta_path[0]._white_list_c_modules += ['_ctypes', 'gestalt']

# Set to True if stack traces should be shown in the browser, etc.
# TODO: should this be changed into an environment variable ?
_DEBUG = True

ATTEMPTS_PER_PAGE = 5

class FrontPageHandler(jeeqs_request_handler.JeeqsRequestHandler):
    """renders the home.html template
    """

    @core.authenticate(False)
    def get(self):
        # get available challenges
        
        all_challenges = Challenge.query().fetch(100)
        all_challenges.sort(
          cmp = exercise_cmp,
          key = lambda challenge:challenge.exercise_number_persisted)

        jeeqser_challenges = []
        if self.jeeqser:
          jeeqser_challenges = Jeeqser_Challenge\
              .query()\
              .filter(Jeeqser_Challenge.jeeqser == self.jeeqser.key)\
              .fetch(100)

        active_submissions = {}
        for jc in jeeqser_challenges:
            active_submissions[jc.challenge] = jc

        injeeqs = None

        if self.jeeqser:
            for ch in all_challenges:
                if active_submissions.get(ch.key):
                    jc = active_submissions[ch.key]
                    ch.submitted = True
                    ch.status = jc.status
                    ch.jc = jc

                else:
                    ch.submitted = False

            injeeqs = Feedback\
                            .query()\
                            .filter(Feedback.attempt_author == self.jeeqser.key)\
                            .filter(Feedback.flagged == False)\
                            .order(Feedback.flag_count)\
                            .order(-Feedback.date)\
                            .fetch(10)
            core.prettify_injeeqs(injeeqs)

        all_activities = Activity.query().order(-Activity.date).fetch(10)

        vars = core.add_common_vars({
                'challenges': all_challenges,
                'injeeqs': injeeqs,
                'activities' : all_activities,
                'jeeqser': self.jeeqser,
                'login_url': users.create_login_url(self.request.url),
                'logout_url': users.create_logout_url(self.request.url)
        })

        template = core.jinja_environment.get_template('home.html')
        rendered = template.render(vars)
        self.response.write(rendered)

class AboutHandler(jeeqs_request_handler.JeeqsRequestHandler):
    """Renders the About page """

    @core.authenticate(required=False)
    def get(self):
        vars = core.add_common_vars({
                'jeeqser' : self.jeeqser,
                'gravatar_url' : self.jeeqser.gravatar_url if self.jeeqser else None,
                'login_url': users.create_login_url(self.request.url),
                'logout_url': users.create_logout_url(self.request.url)
        })

        template = core.jinja_environment.get_template('about.html')
        rendered = template.render(vars)
        self.response.write(rendered)

class ChallengeHandler(jeeqs_request_handler.JeeqsRequestHandler):
    """renders the solve_a_challenge.html template
    """

    @core.authenticate(False)
    def get(self):
        # show this user's previous attempts
        attempts = None
        feedbacks = None
        submission = None
        draft = None

        # get the challenge
        ch_key = self.request.get('ch')
        if not ch_key:
            self.error(StatusCode.forbidden)
            return

        challenge = None

        try:
            challenge = ndb.Key(urlsafe=ch_key).get()
        finally:
            if not challenge:
                self.error(StatusCode.forbidden)
                return

        if not challenge.content and challenge.markdown:
            challenge.content = markdown.markdown(challenge.markdown, ['codehilite', 'mathjax'])
            challenge.put()

        attempt = None
        attempt_key = self.request.get('att')
        if attempt_key:
            attempt = submission = ndb.Key(urlsafe=attempt_key).get()

        if (self.jeeqser):
            attempts_q = Attempt.query()\
                .filter(Attempt.author == self.jeeqser.key)\
                .filter(Attempt.challenge == challenge.key)\
                .order(-Attempt.date)

            cursor = self.request.get('cursor') if self.request.get('cursor') else ''
            if cursor and cursor != "None" and cursor != '':
                # a cursor was passed along with the request, we're in
                # the middle of the list of attempts, show "Next" button
                # to navigate to the earlier attempts
                qo = ndb.QueryOptions(start_cursor=ndb.Cursor(urlsafe=cursor))
                has_next = True
            else:
                # no cursor was passed, we are at the beginning of the list
                # of attempts already and shouldn't display "Next" button
                qo = ndb.QueryOptions()
                has_next = False

            attempts, cursor, more = attempts_q.fetch_page(ATTEMPTS_PER_PAGE,
                                                           options=qo)
            if cursor and more:
                cursor = cursor.urlsafe()
            else:
                cursor = ''

            if not submission:
                # fetch user's active submission
                submissions = Attempt.query()\
                    .filter(Attempt.author == self.jeeqser.key)\
                    .filter(Attempt.challenge == challenge.key)\
                    .filter(Attempt.active == True)\
                    .order(-Attempt.date)\
                    .fetch(1)

                if submissions:
                    submission = submissions[0]

                else:
                    submission = None

            if submission:
                feedbacks = Feedback.query()\
                                    .filter(Feedback.attempt == submission.key)\
                                    .filter(Feedback.flagged == False)\
                                    .order(Feedback.flag_count)\
                                    .order(-Feedback.date)\
                                    .fetch(10)

            if feedbacks:
                core.prettify_injeeqs(feedbacks)

            # Fetch saved draft
            try:
                draft = Draft.query().filter(
                    Draft.author == self.jeeqser.key,
                    Draft.challenge == challenge.key).fetch(1)[0]
            except IndexError:
                draft = None

        vars = core.add_common_vars({
                'server_software': os.environ['SERVER_SOFTWARE'],
                'python_version': sys.version,
                'jeeqser': self.jeeqser,
                'login_url': users.create_login_url(self.request.url),
                'logout_url': users.create_logout_url(self.request.url),
                'attempts': attempts,
                'cursor': cursor,
                'has_next': has_next,
                'challenge' : challenge,
                'challenge_key' : challenge.key,
                'template_code': challenge.template_code,
                'submission' : submission,
                'feedbacks' : feedbacks,
                'draft': draft,
                'attempt': attempt
        })

        template = core.jinja_environment.get_template('solve_a_challenge.html')
        rendered = template.render(vars)
        self.response.write(rendered)

class MoreAttempts(jeeqs_request_handler.JeeqsRequestHandler):
    """Renders 'Your Recent Submissions' part of the challenge page."""

    @core.authenticate(False)
    def get(self):
        # show this user's previous attempts
        attempts = None

        # get the challenge
        ch_key = self.request.get('ch')
        if not ch_key:
            self.error(StatusCode.forbidden)
            return

        challenge = None

        try:
            challenge = ndb.Key(urlsafe=ch_key).get()
        finally:
            if not challenge:
                self.error(StatusCode.forbidden)
                return

        if (self.jeeqser):
            attempts_q = Attempt.query()\
                .filter(Attempt.author == self.jeeqser.key)\
                .filter(Attempt.challenge == challenge.key)\
                .order(-Attempt.date)

            cursor = self.request.get('cursor') if self.request.get('cursor') else ''
            if cursor and cursor != "None" and cursor != '':
                # a cursor was passed along with the request, we're in
                # the middle of the list of attempts, show "Next" button
                # to navigate to the earlier attempts
                qo = ndb.QueryOptions(start_cursor=ndb.Cursor(urlsafe=cursor))
                has_next = True
            else:
                # no cursor was passed, we are at the beginning of the list
                # of attempts already and shouldn't display "Next" button
                qo = ndb.QueryOptions()
                has_next = False

            attempts, cursor, more = attempts_q.fetch_page(ATTEMPTS_PER_PAGE,
                                                           options=qo)
            if cursor and more:
                cursor = cursor.urlsafe()
            else:
                cursor = ''

        vars = core.add_common_vars({
                'jeeqser': self.jeeqser,
                'attempts': attempts,
                'cursor': cursor,
                'has_next': has_next,
                'challenge' : challenge,
                'challenge_key' : challenge.key,
                'template_code': challenge.template_code,
        })

        template = core.jinja_environment.get_template('recent_attempts_contents.html')
        rendered = template.render(vars)
        self.response.write(rendered)


def main():
    application = webapp2.WSGIApplication(
        [('/', FrontPageHandler),
            ('/challenge/', ChallengeHandler),
            ('/attempts/', MoreAttempts),
            ('/challenge/shell.runProgram', program_handler.ProgramHandler),
            ('/review/', review_handler.ReviewHandler),
            ('/rpc', rpc_handler.RPCHandler),
            ('/user/', UserHandler),
            ('/about/', AboutHandler)])
    run_wsgi_app(application)


if __name__ == '__main__':
    main()
