Task
====

Cli modelled on task warrior:

* https://taskwarrior.org/docs/design/cli.html

Pre-requisites
==============

~~~
pip3 install -U google-api-python-client
pip3 install -U google-auth-httplib2
pip3 install -U google-auth-oauthlib
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
time of a task, even though their own tools can do this. See "due":
   https://developers.google.com/tasks/v1/reference/tasks
   https://stackoverflow.com/questions/55251751/tasks-now-have-a-due-time-as-well-as-date-but-api-still-says-000000
