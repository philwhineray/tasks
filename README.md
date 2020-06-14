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

Saved Searches
==============

Any number of searches can be defined for use with `ls`.

The program automatically creates `$HOME/.config/tasks/saved-searches` with
some defaults if it does not exist:

```
NEXT @na NOT p:Admin OR @monitor NOT p:Admin OR due:today NOT p:Admin
ADMIN @wait OR p:Admin @na OR p:Admin @monitor OR p:Admin due:today
```

These work well in a work setting, where you only want to do admin and follow
up tasks once a day.

Run `task ls NEXT` for any non-admin next action (@na),
closely monitored (@monitor), and due today tasks. The @tags are just included
in the task name.

Run `task ls ADMIN` for tasks in the `Admin` list (which you must create
manually) which are @na, @monitor, or due today, or which, regardless
of list, are waiting on someone or something (@wait) and so might need
following up.

The distinction between admin and other tasks does not serve me well at home,
so I use the following:

```
NEXT @na OR due:today
ADMIN @wait OR @monitor
```

Thus the `ADMIN` search is all about follow-up and the `NEXT` search is everything
else. I could define different search names, but I find it easier to remember
by redefining their meaning.


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
