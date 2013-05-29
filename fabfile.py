# Mostly from django-fab-deploy

import os
import sys
from subprocess import Popen, PIPE

import yaml

from fabric.api import env, run, sudo, task, put
from fabric.context_managers import cd
from fabric.contrib import files


# helpers
def _sanitize(s):
    s = s.replace(':', '_')
    s = s.replace('-', '_')
    s = s.replace('/', '_')
    s = s.replace('"', '_')
    s = s.replace("'", '_')
    return s


def _config_get(service_name):
    yaml_conf = Popen(['juju', 'get', service_name], stdout=PIPE)
    conf = yaml.safe_load(yaml_conf.stdout)
    orig_conf = yaml.safe_load(open('config.yaml', 'r'))['options']
    return {k: (v['value'] if v['value'] is not None else orig_conf[k]['default']) for k,v in conf['settings'].iteritems()}

def _find_django_admin_cmd():
    for cmd in ['django-admin.py', 'django-admin']:
        remote_environ = run('echo $PATH')
        for path in remote_environ.split(':'):
            path = path.strip('"')
            path = os.path.join(path, cmd)
            if files.exists(path):
                return path

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


env.service_name = env.roles[0].split('/')[0]
env.sanitized_service_name = _sanitize(env.service_name)
env.conf = _config_get(env.service_name)
env.project_dir = os.path.join(env.conf['install_root'], env.sanitized_service_name)
env.django_settings_modules = '.'.join([env.sanitized_service_name, env.conf['django_settings']])


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
    with cd(env.project_dir):
        for req_file in env.conf['requirements_apt_files'].split(','):
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
    with cd(env.project_dir):
        for req_file in env.conf['requirements_pip_files'].split(','):
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
    with cd(env.project_dir):
        if env.conf['vcs'] is 'bzr':
            run('bzr pull %s' % env.conf['repos_url'])
        if env.conf['vcs'] is 'git':
            run('git pull %s' % env.conf['repos_url'])
        if env.conf['vcs'] is 'hg':
            run('hg pull -u %s' % env.conf['repos_url'])
        if env.conf['vcs'] is 'svn':
            run('svn up %s' % env.conf['repos_url'])

        delete_pyc()
    reload()


# Gunicorn
@task
def reload():
    """
    Reload gunicorn.
    """
    sudo('service %s reload' % env.sanitized_service_name)


# Django
@task
def manage(command):
    """ Runs management commands."""
    django_admin_cmd = _find_django_admin_cmd()
    sudo('%s %s --pythonpath=%s --settings=%s' % \
      (django_admin_cmd, command, env.conf['install_root'], env.django_settings_modules), \
         user=env.conf['wsgi_user'])

@task
def load_fixture(fixture_path):
    """ Upload and load a fixture file"""
    fixture_file = fixture_path.split('/')[-1]
    put(fixture_path, '/tmp/')
    manage('loaddata %s' % os.path.join('/tmp/', fixture_file))
    run('rm %s' % os.path.join('/tmp/', fixture_file))

# Utils
@task
def delete_pyc():
    """ Deletes *.pyc files from project source dir """

    with env.project_dir:
        run("find . -name '*.pyc' -delete")
 
