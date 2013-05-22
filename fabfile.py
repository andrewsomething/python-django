# Mostly from django-fab-deploy

import os
import sys
from subprocess import Popen, PIPE

import yaml

from fabric.api import env, run, sudo, task
from fabric.context_managers import cd
from fabric.contrib import files


# Initialisation

env.user = 'ubuntu'

d = yaml.safe_load(Popen(['juju','status'],stdout=PIPE).stdout)

services = d.get("services", {})
if services is None:
    sys.exit(0)

env.roledefs = {}
for service in services.items():
    if service is None:
        continue

    units = services.get(service[0], {}).get("units", {})
    if units is None:
        continue

    for unit in units.items():
        if 'public-address' in unit[1].keys():
            env.roledefs.setdefault(service[0], []).append(unit[1]['public-address'])
            env.roledefs.setdefault(unit[0], []).append(unit[1]['public-address'])

# helpers
def _config_get(role):
    conf = yaml.safe_load(Popen('./juju get %s' % (role), stdout=PIPE).stdout)
    return {k : v['value'] for k,v in conf['setting'].iteritems()}

def _find_django_admin_cmd():
    for cmd in ['django-admin.py', 'django-admin']:
        remote_environ = run('echo $PATH')
        for path in remote_environ.split(':'):
            path = path.strip('"')
            path = os.path.join(path, cmd)
            if files.exists(path):
                return path


# Debian
@task()
def apt_install(packages):
    """
    Install one or more packages.
    """
    sudo('apt-get install -y %s' % packages)

@task
def apt_update():
    """
    Update APT package definitions.
    """
    sudo('apt-get update')

@task
def apt_dist_upgrade():
    """
    Upgrade all packages.
    """
    sudo('apt-get dist-upgrade -y')

@task
def apt_install_r():
    """
    Install one or more packages listed in your requirements_apt_files.
    """
    conf = _config_get(env.roles[0])
    project_dir = os.path.join(conf['install_root'], env.roles[0])
    with cd(project_dir):
        for req_file in conf['requirements_apt_files'].split(','):
            sudo("apt-get install -y $(cat %s | tr '\\n' ' '" % req_file)

# Python
@task
def pip_install(packages):
    """
    Install one or more packages.
    """
    sudo("pip install %s" % packages)

@task
def pip_install_r():
    """
    Install one or more python packages listed in your requirements_pip_files.
    """
    conf = _config_get(env.roles[0])
    project_dir = os.path.join(conf['install_root'], env.roles[0])
    with cd(project_dir):
        for req_file in conf['requirements_pip_files'].split(','):
            sudo("pip install -r %s" % req_file)

# Users
@task
def adduser(username):
    """
    Adduser without password.
    """
    sudo('adduser %s --disabled-password --gecos ""' % username)

@task
def ssh_add_key(pub_key_file, username=None):
    """
    Add a public SSH key to the authorized_keys file on the remote machine.
    """
    with open(os.path.normpath(pub_key_file), 'rt') as f:
        ssh_key = f.read()

    if username is None:
        run('mkdir -p .ssh')
        files.append('.ssh/authorized_keys', ssh_key)
    else:
        run('mkdir -p /home/%s/.ssh' % username)
        files.append('/home/%s/.ssh/authorized_keys' % username, ssh_key)
        run('chown -R %s:%s /home/%s/.ssh' % (username, username, username))


# VCS

@task
def pull():
    """
    pull or update your project code on the remote machine.
    """
    conf = _config_get(env.roles[0])
    project_dir = os.path.join(conf['install_root'], env.roles[0])
    with cd(project_dir):
        if conf['vcs'] is 'bzr':
            run('bzr pull %s' % conf['repos_url'])
        if conf['vcs'] is 'git':
            run('git pull %s' % conf['repos_url'])
        if conf['vcs'] is 'hg':
            run('hg pull -u %s' % conf['repos_url'])
        if conf['vcs'] is 'svn':
            run('svn up %s' % conf['repos_url'])

        delete_pyc()
    gunicorn_reload()


# Gunicorn
@task
def gunicorn_reload():
    """
    Reload gunicorn.
    """
    sudo('invoke-rc.d gunicorn reload')


# Django
@task
def manage(command):
    """ Runs management commands."""
    conf = _config_get(env.roles[0])
    project_dir = os.path.join(conf['install_root'], env.roles[0])
    django_admin_cmd = _find_django_admin_cmd()
    run('%s %s --pythonpath=%s --settings=%s' % \
      (django_admin_cmd, command, conf['install_root'], env.roles[0] + 'settings'))


# Utils
@task
def delete_pyc():
    """ Deletes *.pyc files from project source dir """

    conf = _config_get(env.roles[0])
    project_dir = os.path.join(conf['install_root'], env.roles[0])
    with project_dir:
        run("find . -name '*.pyc' -delete")
 
