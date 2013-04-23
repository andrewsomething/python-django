#!/usr/bin/env python
# vim: et ai ts=4 sw=4:

import json
import os
import re
import subprocess
import sys
import time
from pwd import getpwnam
from grp import getgrnam
from random import choice


# jinja2 may not be importable until the install hook has installed the
# required packages.
def Template(*args, **kw):
    from jinja2 import Template
    return Template(*args, **kw)


###############################################################################
# Supporting functions
###############################################################################
MSG_CRITICAL = "CRITICAL"
MSG_DEBUG = "DEBUG"
MSG_INFO = "INFO"
MSG_ERROR = "ERROR"
MSG_WARNING = "WARNING"


def juju_log(level, msg):
    subprocess.call(['juju-log', '-l', level, msg])

#------------------------------------------------------------------------------
# run: Run a command, return the output
#------------------------------------------------------------------------------
def run(command, exit_on_error=True):
    try:
        juju_log(MSG_DEBUG, command)
        return subprocess.check_output(
            command, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError, e:
        juju_log(MSG_ERROR, "status=%d, output=%s" % (e.returncode, e.output))
        if exit_on_error:
            sys.exit(e.returncode)
        else:
            raise


#------------------------------------------------------------------------------
# install_file: install a file resource. overwites existing files.
#------------------------------------------------------------------------------
def install_file(contents, dest, owner="root", group="root", mode=0600):
    uid = getpwnam(owner)[2]
    gid = getgrnam(group)[2]
    dest_fd = os.open(dest, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, mode)
    os.fchown(dest_fd, uid, gid)
    with os.fdopen(dest_fd, 'w') as destfile:
        destfile.write(str(contents))


#------------------------------------------------------------------------------
# install_dir: create a directory
#------------------------------------------------------------------------------
def install_dir(dirname, owner="root", group="root", mode=0700):
    command = \
    '/usr/bin/install -o {} -g {} -m {} -d {}'.format(owner, group, oct(mode),
        dirname)
    return run(command)

#------------------------------------------------------------------------------
# config_get:  Returns a dictionary containing all of the config information
#              Optional parameter: scope
#              scope: limits the scope of the returned configuration to the
#                     desired config item.
#------------------------------------------------------------------------------
def config_get(scope=None):
    try:
        config_cmd_line = ['config-get']
        if scope is not None:
            config_cmd_line.append(scope)
        config_cmd_line.append('--format=json')
        config_data = json.loads(subprocess.check_output(config_cmd_line))
    except:
        config_data = None
    finally:
        return(config_data)


#------------------------------------------------------------------------------
# relation_json:  Returns json-formatted relation data
#                Optional parameters: scope, relation_id
#                scope:        limits the scope of the returned data to the
#                              desired item.
#                unit_name:    limits the data ( and optionally the scope )
#                              to the specified unit
#                relation_id:  specify relation id for out of context usage.
#------------------------------------------------------------------------------
def relation_json(scope=None, unit_name=None, relation_id=None):
    command = ['relation-get', '--format=json']
    if relation_id is not None:
        command.extend(('-r', relation_id))
    if scope is not None:
        command.append(scope)
    else:
        command.append('-')
    if unit_name is not None:
        command.append(unit_name)
    output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    return output or None


#------------------------------------------------------------------------------
# relation_get:  Returns a dictionary containing the relation information
#                Optional parameters: scope, relation_id
#                scope:        limits the scope of the returned data to the
#                              desired item.
#                unit_name:    limits the data ( and optionally the scope )
#                              to the specified unit
#------------------------------------------------------------------------------
def relation_get(scope=None, unit_name=None, relation_id=None):
    j = relation_json(scope, unit_name, relation_id)
    if j:
        return json.loads(j)
    else:
        return None


def relation_set(keyvalues, relation_id=None):
    args = []
    if relation_id:
        args.extend(['-r', relation_id])
    args.extend(["{}='{}'".format(k, v or '') for k, v in keyvalues.items()])
    run("relation-set {}".format(' '.join(args)))

    ## Posting json to relation-set doesn't seem to work as documented?
    ## Bug #1116179
    ##
    ## cmd = ['relation-set']
    ## if relation_id:
    ##     cmd.extend(['-r', relation_id])
    ## p = Popen(
    ##     cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    ##     stderr=subprocess.PIPE)
    ## (out, err) = p.communicate(json.dumps(keyvalues))
    ## if p.returncode:
    ##     juju_log(MSG_ERROR, err)
    ##     sys.exit(1)
    ## juju_log(MSG_DEBUG, "relation-set {}".format(repr(keyvalues)))


def relation_list(relation_id=None):
    """Return the list of units participating in the relation."""
    if relation_id is None:
        relation_id = os.environ['JUJU_RELATION_ID']
    cmd = ['relation-list', '--format=json', '-r', relation_id]
    json_units = subprocess.check_output(cmd).strip()
    if json_units:
        return json.loads(subprocess.check_output(cmd))
    return []


#------------------------------------------------------------------------------
# relation_ids:  Returns a list of relation ids
#                optional parameters: relation_type
#                relation_type: return relations only of this type
#------------------------------------------------------------------------------
def relation_ids(relation_types=('db',)):
    # accept strings or iterators
    if isinstance(relation_types, basestring):
        reltypes = [relation_types, ]
    else:
        reltypes = relation_types
    relids = []
    for reltype in reltypes:
        relid_cmd_line = ['relation-ids', '--format=json', reltype]
        json_relids = subprocess.check_output(relid_cmd_line).strip()
        if json_relids:
            relids.extend(json.loads(json_relids))
    return relids


#------------------------------------------------------------------------------
# relation_get_all:  Returns a dictionary containing the relation information
#                optional parameters: relation_type
#                relation_type: limits the scope of the returned data to the
#                               desired item.
#------------------------------------------------------------------------------
def relation_get_all(*args, **kwargs):
    relation_data = []
    relids = relation_ids(*args, **kwargs)
    for relid in relids:
        units_cmd_line = ['relation-list', '--format=json', '-r', relid]
        json_units = subprocess.check_output(units_cmd_line).strip()
        if json_units:
            for unit in json.loads(json_units):
                unit_data = \
                    json.loads(relation_json(relation_id=relid,
                        unit_name=unit))
                for key in unit_data:
                    if key.endswith('-list'):
                        unit_data[key] = unit_data[key].split()
                unit_data['relation-id'] = relid
                unit_data['unit'] = unit
                relation_data.append(unit_data)
    return relation_data


#------------------------------------------------------------------------------
# apt_get_install( packages ):  Installs package(s)
#------------------------------------------------------------------------------
def apt_get_install(packages=None):
    if packages is None:
        return(False)
    cmd_line = ['apt-get', '-y', 'install', '-qq']
    cmd_line.extend(packages)
    return(subprocess.call(cmd_line))


#------------------------------------------------------------------------------
# pip_install( package ):  Installs a python package
#------------------------------------------------------------------------------
def pip_install(packages=None):
    if packages is None:
        return(False)
    cmd_line = ['pip', 'install']
    cmd_line.append(packages)
    return(subprocess.call(cmd_line))

#------------------------------------------------------------------------------
# pip_install_req( path ):  Installs a requirements file
#------------------------------------------------------------------------------
def pip_install_req(path=None):
    if path is None:
        return(False)
    cmd_line = ['pip', 'install', '-r']
    cmd_line.append(path)
    cwd = os.path.dirname(path)
    return(subprocess.call(cmd_line, cwd=cwd))

#------------------------------------------------------------------------------
# open_port:  Convenience function to open a port in juju to
#             expose a service
#------------------------------------------------------------------------------
def open_port(port=None, protocol="TCP"):
    if port is None:
        return(None)
    return(subprocess.call(['open-port', "%d/%s" %
        (int(port), protocol)]))


#------------------------------------------------------------------------------
# close_port:  Convenience function to close a port in juju to
#              unexpose a service
#------------------------------------------------------------------------------
def close_port(port=None, protocol="TCP"):
    if port is None:
        return(None)
    return(subprocess.call(['close-port', "%d/%s" %
        (int(port), protocol)]))


#------------------------------------------------------------------------------
# update_service_ports:  Convenience function that evaluate the old and new
#                        service ports to decide which ports need to be
#                        opened and which to close
#------------------------------------------------------------------------------
def update_service_port(old_service_port=None, new_service_port=None):
    if old_service_port is None or new_service_port is None:
        return(None)
    if new_service_port != old_service_port:
        close_port(old_service_port)
        open_port(new_service_port)

#
# Utils
#

def install_or_append(contents, dest, owner="root", group="root", mode=0600):
    if os.path.exists(dest):
        uid = getpwnam(owner)[2]
        gid = getgrnam(group)[2]
        dest_fd = os.open(dest, os.O_APPEND, mode)
        os.fchown(dest_fd, uid, gid)
        with os.fdopen(dest_fd, 'a') as destfile:
            destfile.write(str(contents))
    else:
        install_file(contents, dest, owner, group, mode)

def token_sql_safe(value):
    # Only allow alphanumeric + underscore in database identifiers
    if re.search('[^A-Za-z0-9_]', value):
        return False
    return True

def sanitize(s):
    s = s.replace(':', '_')
    s = s.replace('-', '_')
    s = s.replace('/', '_')
    s = s.replace('"', '_')
    s = s.replace("'", '_')
    return s

def user_name(relid, remote_unit, admin=False, schema=False):
    components = [sanitize(relid), sanitize(remote_unit)]
    if admin:
        components.append("admin")
    elif schema:
        components.append("schema")
    return "_".join(components)

def get_relation_host():
    remote_host = run("relation-get ip")
    if not remote_host:
        # remote unit $JUJU_REMOTE_UNIT uses deprecated 'ip=' component of
        # interface.
        remote_host = run("relation-get private-address")
    return remote_host


def get_unit_host():
    this_host = run("unit-get private-address")
    return this_host.strip()

def process_template(template_name, template_vars, destination):
    # --- exported service configuration file
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))

    template = \
        template_env.get_template(template_name).render(template_vars)

    with open(destination, 'w') as inject_file:
        inject_file.write(str(template))

###############################################################################
# Hook functions
###############################################################################
def install(run_pre=True):
    packages = ["python-django", "python-imaging", "python-docutils", "python-psycopg2",
                "python-pip", "python-jinja2", "mercurial", "git-core", "subversion", "bzr",
                "python-tz", "postgresql-client"]

    apt_get_install(packages)
            
    if extra_deb_pkgs:
        apt_get_install(extra_deb_pkgs.split(','))

    if extra_pip_pkgs:
        for package in extra_pip_pkgs.split(','):
            pip_install(package)

    if repos_username:
        m = re.match(".*://([^/]+)/.*", repos_url)
        if m is not None:
            repos_domain = m.group(1)
            template_vars = {
                'repos_domain': repos_domain,
                'repos_username': repos_username,
                'repos_password': repos_password
            }
            from os.path import expanduser
            process_template('netrc.tmpl', template_vars, expanduser('~/.netrc'))
        else:
            juju_log(MSG_ERROR, '''Failed to process repos_username and repos_password:\n
                                   cannot identify domain in URL {0}'''.format(repos_url))
        
    if vcs == 'hg' or vcs == 'mercurial':
        run('hg clone %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'git' or vcs == 'git-core':
        if repos_branch:
            run('git clone %s -b %s %s' % (repos_url, repos_branch, vcs_clone_dir))
        else:
            run('git clone %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'bzr' or vcs == 'bazaar':
        run('bzr branch %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == 'svn' or vcs == 'subversion':
        run('svn co %s %s' % (repos_url, vcs_clone_dir))
    elif vcs == '' and repos_url == '':
        juju_log(MSG_INFO, "No version control using django-admin startproject")
        cmd = 'django-admin startproject'
        if project_template_url:
            cmd = " ".join(cmd, '--template', project_template_url)
        if project_template_extension:
            cmd = " ".join(cmd, '--extension', project_template_extension)
        run('%s %s' % (cmd, working_dir))
        run('chown -R %s:%s %s' % (wsgi_user,wsgi_group, working_dir))
    else:
        juju_log(MSG_ERROR, "Unknown version control")
        sys.exit(1)


    #FIXME: Upgrades/pulls will mess this files
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))

    template = \
        template_env.get_template('settings.tmpl').render()

    with open(settings_py_path, 'a') as inject_file:
        inject_file.write(str(template))

    if requirements_pip_files:
       for req_file in requirements_pip_files.split(','):
            pip_install_req(os.path.join(working_dir,req_file))

    install_dir(django_run_dir, owner=wsgi_user, group=wsgi_group, mode=0755)
    install_dir(django_logs_dir, owner=wsgi_user, group=wsgi_group, mode=0755)

def config_changed(config_data):
    if not site_secret_key:
        site_secret_key = ''.join([choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50)])

    # --- exported service configuration file
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))
    templ_vars = {
       'site_secret_key': site_secret_key,
    }

    template = \
        template_env.get_template('secret.tmpl').render(templ_vars)

    with open(settings_secret_path, 'w') as inject_file:
        inject_file.write(str(template))

    run("%s collectstatic --noinput || true" % manage_path)

    # Trigger WSGI reloading
    for relid in relation_ids('wsgi'):
        relation_set({'wsgi_timestamp': time.time()}, relation_id=relid)

def django_settings_relation_joined_changed():
    relation_set({'working_dir':working_dir})

def django_settings_relation_broken():
    pass

def db_relation_joined_changed():
    database = relation_get("database")
    if not database:
        return

    # --- exported service configuration file
    from jinja2 import Environment, FileSystemLoader
    template_env = Environment(
        loader=FileSystemLoader(os.path.join(os.environ['CHARM_DIR'],
        'templates')))
    templ_vars = {
       'db_database': database,
       'db_user': relation_get("user"),
       'db_password': relation_get("password"),
       'db_host': relation_get("host"),
    }

    template = \
        template_env.get_template('engine.tmpl').render(templ_vars)

    with open(settings_database_path, 'w') as inject_file:
        inject_file.write(str(template))

    run("%s syncdb --noinput || true" % manage_path)

def db_relation_broken():
    pass

def database_relation_joined_changed():
    pass

def database_relation_broken():
    pass

def wsgi_relation_joined_changed():
    relation_set({'working_dir':working_dir})

    for var in config_data:
        if var.startswith('wsgi_') or var in ['env_extra', 'django_settings', 'python_path', 'port']:
            relation_set({var: config_data[var]})

# def website_relation_joined_changed():
#if [ -e /etc/gunicorn.d/${unit_name}.conf ]; then
#
#   bind_line=$(grep "bind=0.0.0.0:" /etc/gunicorn.d/${unit_name}.conf)
#       PORT=$(echo ${bind_line} | grep -o ":[0-9]*" | sed -e "s/://")
#
#            juju-log "PORT=${PORT}"
#
#                relation-set port="${PORT}" hostname=`unit-get private-address`
#


###############################################################################
# Global variables
###############################################################################
config_data = config_get()

vcs = config_data['vcs']
repos_url = config_data['repos_url']
repos_username = config_data['repos_username']
repos_password = config_data['repos_password']
repos_branch = config_data['repos_branch']

project_template_extension = config_data['project_template_extension']
project_template_url = config_data['project_template_url']

extra_deb_pkgs = config_data['additional_distro_packages']
extra_pip_pkgs = config_data['additional_pip_packages']
requirements_pip_files = config_data['requirements_pip_files']
site_secret_key = config_data['site_secret_key']
wsgi_user = config_data['wsgi_user']
wsgi_group = config_data['wsgi_group']
install_root = config_data['install_root']
application_path = config_data['application_path']

unit_name = os.environ['JUJU_UNIT_NAME'].split('/')[0]
vcs_clone_dir = os.path.join(install_root, unit_name)
if application_path:
    working_dir = os.path.join(vcs_clone_dir, application_path)
else:
    working_dir = vcs_clone_dir
manage_path = os.path.join(working_dir, 'manage.py')
django_run_dir = os.path.join(working_dir, "run/")
django_logs_dir = os.path.join(working_dir, "logs/")
settings_py_path = os.path.join(working_dir, 'settings.py')
settings_path = os.path.join(working_dir, 'settings/')
settings_secret_path = os.path.join(working_dir, config_data["settings_secret_key_path"])
settings_database_path = os.path.join(working_dir, config_data["settings_database_path"])
hook_name = os.path.basename(sys.argv[0])

###############################################################################
# Main section
###############################################################################
def main():
    juju_log(MSG_INFO, "Running {} hook".format(hook_name))
    if hook_name == "install":
        install()

    elif hook_name == "config-changed":
       config_changed(config_data)

    elif hook_name == "upgrade-charm":
        install(run_pre=False)
        config_changed(config_data)

    elif hook_name in ["django-settings-relation-joined", "django-settings-relation-changed"]:
        django_settings_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "django-settings-relation-broken":
        django_settings_relation_broken()
        config_changed(config_data)

    elif hook_name in ["db-relation-joined", "db-relation-changed"]:
        db_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "db-relation-broken":
        db_relation_broken()
        config_changed(config_data)

    elif hook_name in ["database-relation-joined", "database-relation-changed"]:
        database_relation_joined_changed()
        config_changed(config_data)

    elif hook_name == "database-relation-broken":
        database_relation_broken()
        config_changed(config_data)

    elif hook_name in ["wsgi-relation-joined", "wsgi-relation-changed"]:
        wsgi_relation_joined_changed()

    else:
        print "Unknown hook {}".format(hook_name)
        raise SystemExit(1)


if __name__ == '__main__':
    raise SystemExit(main())
