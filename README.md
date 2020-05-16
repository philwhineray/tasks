Task
====

Cli to interact with google tasks

Pre-requisites
==============

Python 3 Pip

~~~
sudo apt install python3-pip
~~~

~~~
python3 -m pip install --user google-api-python-client
python3 -m pip install --user google-auth-httplib2
python3 -m pip install --user google-auth-oauthlib
~~~

App authentication
===================

Create a new project in Google:

* https://console.developers.google.com/cloud-resource-manager

Select credentials from the APIs and Services submenu under the burger
button, then set up:

* A basic OAuth consent screen (just fill in a name and click save)
* An OAuth client ID: Application Type = Other, Name = Task client

Choose to edit the newly created token and download the JSON as
`$HOME/.config/tasks/app-credentials.json`.

Limitations
===========

At present the google tasks API does not show / permit setting the
time or repetition of a task, even though their own tools can do this.
See "due":

* https://developers.google.com/tasks/v1/reference/tasks
* https://stackoverflow.com/questions/55251751/tasks-now-have-a-due-time-as-well-as-date-but-api-still-says-000000

In practice, setting the date of a task will lose its time, if it
had one. The repetition does not get modified as far as I can see.
The tool tries to warn you if you edit a date.

Things can get pretty confused if you delete the date for a
repeating task, and we can't warn about that because the API does not
expose that information.
