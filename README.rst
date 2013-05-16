Juju charm python-django
========================

:Author: Patrick Hetu <patrick@koumbit.org> and Bruno Girin

Overview
--------

Django is a high-level web application framework that loosely follows
the model-view-controller design pattern.  Python's equivalent to Ruby
on Rails, Django lets you build complex data-driven websites quickly
and easily - Django focuses on automating as much as possible and
adhering to the "Don't Repeat Yourself" (DRY) principle.  Django
additionally emphasizes reusability and "pluggability" of components;
many generic third-party "applications" are available to enhance
projects or to simply to reduce development time even further.

Notable features include: 

* An object-relational mapper (ORM)
* Automatic admin interface
* Elegant URL dispatcher
* Form serialization and validation system
* Templating system
* Lightweight, standalone web server for development and testing
* Internationalization support * Testing framework and client


Quick start
-----------

Simply::

    juju bootstrap
    juju deploy python-django

    juju deploy postgresql
    juju add-relation python-django postgresql:db

    juju deploy gunicorn
    juju add-relation python-django gunicorn
    juju expose gunicorn

In a couple of minute, your new (vanilla) Django site should be ready at
the public address of gunicorn. You can find it in the output of the
`juju status` command.  

This is roughtly equivalent to the `Creating a project` step in Django's
tutorial there:

  https://docs.djangoproject.com/en/1.5/intro/tutorial01/#creating-a-project

Customising the deployment
---------------------------

To customise the deployment, you need to create a configuration file
written in the YAML language.

Relations
---------

Example: Deploying using site a template
----------------------------------------

Setup your Django specific parameters in my_django_site.yaml like this one::

    my_django_site:
         project_template_url: https://github.com/xenith/django-base-template/zipball/master
         project_template_extension: py,md,rst

Note: 

    If your using juju-core you must remove the first line
    of the file and indent the rest according to that.

2. Deployment with `Gunicorn`::

    juju bootstrap
    juju deploy --config my_django_site.yaml my_django_site

    juju deploy postgresql
    juju add-relation my_django_site postgresql:db

    juju deploy gunicorn
    juju add-relation my_django_site gunicorn
    juju expose gunicorn


Example: Deploying using code repository
----------------------------------------

1. Setup your Django specific parameters in my_django_site.yaml like this one::

    my_django_site:
        vcs: bzr
        repos_url: lp:~patrick-hetu/my_site

Note: 

    If your using juju-core you must remove the first line
    of the file and indent the rest according to that.

2. Deployment with `Gunicorn`::

    juju bootstrap
    juju deploy --config my_django_site.yaml python-django

    juju deploy postgresql
    juju add-relation python-django postgresql:db

    juju deploy gunicorn
    juju add-relation python-django gunicorn
    juju expose gunicorn

Note:

    If your using juju-core you must add --upload-tools to the
    `juju bootstrap` command.

3. Accessing your new Django site should be ready at the public address of
   Gunicorn. To find it look for it in the output of the `juju status` command.  


Project layout and code injection
---------------------------------

Taking the previous example, your web site should be on the Django node at::

  /srv/python-django/

As you can see there the charm have inject some code at the end of your settings.py
file (or created it if it was not there) to be able to import what's in the
`juju_settings/` directory.

It's recommended to make your vcs to ignore database and secret files or
any files that have information that you don't want to be publish.


Upgrade the charm
-----------------

This charm allow you to upgrade your deployment using the Juju's
`upgrade-charm` command. This command will:

* upgrade Django
* upgrade using your requirements files
* upgrade additionnal pip packages
* upgrade additionnal Debian packages

Management with Fabfile
-----------------------

To make Juju more PAAS'ish the charm include a Fabric script that use Juju's
output to populate env.roledefs with Services and Units.

So, with a python-django service deployed you can run commands on all units::

    fab -R python-django pull
    [10.0.0.2] Executing task 'pull'
    [10.0.0.2] run: bzr pull lp:~my_name/django_code/my_site
    ...
    [10.0.0.2] run: invoke-rc.d gunicorn restart
    ...

Or you can also specify a single unit:

    fab -R python-django/0 pull
    [10.0.0.2] Executing task 'pull'
    [10.0.0.2] run: bzr pull lp:~my_name/django_code/my_site
    ...
    [10.0.0.2] run: invoke-rc.d gunicorn restart
    ...


fabfile.py include the following commands:

* apt_install
* apt_update
* apt_dist_upgrade
* apt_install_r
* pip_install
* pip_install_r
* adduser
* ssh_add_key
* pull
* reload
* manage
* migrate
* syncdb
* collectstatic
* delete_pyc


Limitation:

* You can only execute task for one role (service) at the time.

Security
--------

Note that if your using a *requirement.txt* file the packages will
be downloaded with *pip* and it doesn't do any cryptographic
verification of its downloads.

Writing application charm
-------------------------

To create an application subordinate charm that works with this one you need
at least to have an interface named `directory-path` in your `metadate.yaml` file
for example::

  [...]
  requires:
    python-django:
       interface: directory-path
       scope: container
       optional: true

With those hooks you will be able to get those relation variables:

* settings_dir_path
* urls_dir_path
* django_admin_cmd
* install_root

then be informed where to add new settings and urls files and how to run additionnal Django
commands. When the hook will be finish, the Django charm will reload Gunicorn to catch the changes.

Changelog
---------

3:

  Notable changes:

    * Rewrite the charm using python instead of BASH scripts
    * Django projects now need no modification to work with the charm
    * Use the `django-admin startproject` command with configurable arguments if no repos is specified
    * Juju's generated settings and urls files are now added in a juju_settings
      and a juju_urls directories by default
    * New MongoDB relation (server side is yet to be done)
    * New upgrade hook that upgrade pip and debian packages

  Configuration changes:

    * default user and group is now ubuntu
    * new install_root option
    * new django_version option
    * new additional_pip_packages option
    * new repos_branch,repos_username,repos_password options
    * new project_name, project_template_extension, project_template_url options
    * new urls_dir_name and settings_dir_name options
    * new project_template_url and project_template_extension options
    * database, uploads, static, secret and cache settings locations are now configurable
    * extra_deb_pkg was renamed additional_distro_packages
    * requirements was renamed requirements_pip_files and now support multiple files
    * if python_path is empty set as install_root
    
  Backwards incompatible changes:

    * swift support was moved to a subordinate charm
    * postgresql relation hook was rename pgsql instead of db

2:

  Notable changes:

  * You can configure all wsgi (Gunicorn) settings via the config.yaml file
  * Juju compatible Fabric fabfile.py is included for PAAS commands
  * Swift storage backend is now optional

  Backwards incompatible changes:

    * Use splited settings and urls
    * Permissons are now based on WSGI's user and group instead of just being www-data
    * media and static files are now in new directories ./uploads and ./static/
    * Deprecated configuration variables: site_domain, site_username, site_password, site_admin_email


1:

  Initial release

Inspiration
-----------

* http://www.deploydjango.com
* http://lincolnloop.com/django-best-practices/
* https://github.com/30loops/djangocms-on-30loops.git
* https://github.com/openshift/django-example
* http://lincolnloop.com/blog/2013/feb/15/django-settings-parity-youre-doing-it-wrong/
* http://tech.yipit.com/2011/11/02/django-settings-what-to-do-about-settings-py/
* http://www.rdegges.com/the-perfect-django-settings-file/
* https://github.com/xenith/django-base-template.git
* https://github.com/transifex/transifex/blob/devel/transifex/settings.py
