Task
====

Cli to interact with google tasks

Pre-requisites
==============

~~~
sudo apt install python3-googleapi python3-google-auth-oauthlib
~~~


Or:

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

Once this file is installed, just use the task command and you
will be prompted to visit a URL to provide access to your Google
tasks.

Multi-account management
========================

To set up additional accounts, install credentials for each account as:
`$HOME/.config/tasks/app-credentials.json.<AccountName>` (with `$HOME/.config/tasks/app-credentials.json` being the `"default"` account).

By default, `task` connects to all configured accounts simultaneously:
* Projects are prefixed with `<account>:<project>` (e.g. `work:Inbox`, `personal:Inbox`).
* Short IDs (`pXX`, `tXXX`) are globally unique across all accounts.
* Use `a:<account>` or `account:<account>` to filter by account.
* Use `p:<account>:<project>` to scope queries to a specific account's project.
* Commands like `task add "Buy milk"` add to the designated inbox in the default account (or disambiguate using default account if multiple accounts have an `Inbox`).
* In `task bulk`, tasks can be moved across accounts by simply editing the project header under which they appear.
* Use `-A <AccountName>` to restrict an invocation strictly to a single account.
* Create `$HOME/.config/tasks/default-account` containing the name of your primary account to designate a specific default account name other than `"default"`.

User-defined commands
=====================

Any number of user-defined commands can be set up. If the command
is run with one of these names as the very first argument, it will be
expanded before and any other arguments supplied are appended.

You can use any command for a user-defined command, although at present
the functionality is quite basic and the most obvious use is for saved
searches.

The program automatically creates `$HOME/.config/tasks/user-defined-commands`
with some defaults if it does not exist:

```
NEXT ls @na NOT p:Admin OR @monitor NOT p:Admin OR due:today NOT p:Admin
ADMIN ls @wait OR p:Admin @na OR p:Admin @monitor OR p:Admin due:today
```

These work well in a work setting, where you only want to do admin and follow
up tasks once a day.

Run `task NEXT` to list any non-admin next action (@na),
closely monitored (@monitor), and due today tasks.
The @tags are just included in the task name.

Run `task ADMIN` to list tasks in the `Admin` project (which you must create
manually) which are @na, @monitor, or due today, or which, regardless
of project, are waiting on someone or something (@wait) and so might need
following up.

The distinction between admin and other tasks does not serve me well at home,
so I use the following:

```
NEXT ls @na OR due:today
ADMIN ls @wait OR @monitor
```

Thus the `task ADMIN` is all about follow-up and `task NEXT` is everything
else. I could define different commands, but I find they have a similar
meaning, just my approach to them makes a different search preferable.

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
