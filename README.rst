Juju charm python-django
========================

:Author: Patrick Hetu <patrick@koumbit.org>

.. caution::
    This charm is under heavy development; expect some bumps on your road.

Example deployment
------------------

1. Setup your Django specific parameters in my_django_site.yaml like this one::

    my_django_site:
        vcs: bzr
        repos_url: lp:~patrick-hetu/my_site
        additional_distro_packages: python-dateutils

Note: 

    If your using juju-core you must remove the first line
    of the file and indent the rest according to that.

2. Deployment with `Gunicorn`::

    juju bootstrap
    juju deploy --config my_django_site.yaml my_django_site

    juju deploy postgresql
    juju add-relation my_django_site:db postgresql:db

    juju deploy gunicorn
    juju add-relation my_django_site gunicorn
    juju expose gunicorn

Note:

    If your using juju-core you must add --upload-tools to the
    `juju bootstrap` command.

3. Accessing your new Django site should be ready at::

       http://<machine-addr>/ 

   To find out the public address of gunicorn, look for it in the output of the
   `juju status` command.  

What the charm does
-------------------

During the `install` hook:

* installs Django
* clones your Django site from the repo specified in `repos_url`
* installs the extra Debian packages
* installs python packages from extra pip options and from requirements files
* sits back and waits to be joined to a database

when related to a `gunicorn` service, the charm

* configures gunicorn
* start or restart Gunicorn

when related to a `postgresql` service, the charm

* configures db access 
* restart Gunicorn

Management with Fabfile
-----------------------

To make Juju more PAAS'ish the charm include a Fabric script that use Juju's
output to populate env.roledefs with Services and Units.

So, with a python-django service deployed you can do things like::

    fab -R python-django pull
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
* db_list
* db_backup
* db_restore
* delete_pyc

Project Layout
--------------

Be sure to have the settings directory in your repos and be sure to include
those lines or something equivalent in your settings.py::

    import glob
    from os.path import abspath, dirname, join

    PROJECT_DIR = abspath(dirname(__file__))

    conffiles = glob.glob(join(PROJECT_DIR, 'settings', '*.py'))
    conffiles.sort()

    for f in conffiles:
        execfile(abspath(f))


Security
--------

Note that if your using a *requirement.txt* file the packages will
be downloaded with *pip* and it doesn't do any cryptographic
verification of its downloads.

Changelog
---------

3:

  * Rewrite the charm using python instead of BASH scripts
  * Default project template is available if no repos is specified

  Configuration changes:

    * default user and group is now ubuntu
    * new install_root option
    * new additional_pip_packages option
    * new repos_branch,repos_username,repos_password options
    * database, uploads, static, secret and cache settings locations are now configurable
    * extra_deb_pkg was renamed additional_distro_packages
    * requirements was renamed requirements_pip_files and now support multiple files
    
  Backwards incompatible changes:

    * swift support was moved to a subordinate charm
2:

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
