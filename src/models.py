#!/usr/bin/python

"""
Model for challenges and solutions.

In order to backup the local data store, first create DataStore stats using the local Admin console and then
run the following command:

These commands are working on Python 2.5.4 as of now. There are known issues with default installations of
python on MacOS and serialization of floats.

Download from local datastore into a file
appcfg.py download_data --url=http://localhost:8080/remote_api --filename=localdb

Upload from a file into production:
appcfg.py upload_data --url=http://jeeqsy.appspot.com/remote_api --filename=localdb

"""

from google.appengine.ext import db

__author__ = 'akhavan'

class Jeeqser(db.Model):
    """ A Jeeqs User """
    username = db.StringProperty()
    user = db.UserProperty()

class Challenge(db.Model):
    """Models a challenge"""

    name = db.StringProperty()
    content = db.TextProperty()
    template_code = db.StringProperty(multiline=True)
    attribution = db.StringProperty(multiline=True)
    source = db.LinkProperty()

class Attempt(db.Model):
    """Models a Submission for a Challenge """
    challenge = db.ReferenceProperty(Challenge)
    author = db.ReferenceProperty(Jeeqser)
    content = db.StringProperty(multiline=True)
    date = db.DateTimeProperty(auto_now_add=True)
    stdout = db.StringProperty(multiline=True)
    stderr = db.StringProperty(multiline=True)
    # List of users who voted for this submission
    users_voted = db.ListProperty(db.Key)
    vote_count = db.IntegerProperty(default=0)
    vote_sum = db.FloatProperty(default=float(0))
    vote_average = db.FloatProperty(default=float(0))
    # is this the active submission for review ?
    active = db.BooleanProperty(default=False)
    submitted = db.BooleanProperty(default=False)

class Feedback(db.Model):
    """Models feedback for submission """
    attempt = db.ReferenceProperty(Attempt)
    author = db.ReferenceProperty(Jeeqser, collection_name='feedback_out')
    # Denormalizing the attempt author
    attempt_author = db.ReferenceProperty(Jeeqser, collection_name='feedback_in')
    content = db.StringProperty(multiline=True)
    date = db.DateTimeProperty(auto_now_add=True)
    vote = db.StringProperty()

class TestCase(db.Model):
    """ Models a test case"""
    challenge = db.ReferenceProperty(Challenge, collection_name='testcases')
    statement = db.StringProperty(multiline=True)
    expected = db.StringProperty(multiline=True)

    '''
    c = Challenge.get('agpkZXZ-amVlcXN5cg8LEglDaGFsbGVuZ2UYAQw')
    test = TestCase(challenge=c, statement='factorial(3)')
    '''

