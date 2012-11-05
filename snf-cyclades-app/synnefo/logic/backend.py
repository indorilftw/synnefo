# Copyright 2011 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

import json

from django.conf import settings
from django.db import transaction
from datetime import datetime

from synnefo.db.models import (Backend, VirtualMachine, Network,
                               BackendNetwork, BACKEND_STATUSES,
                               pooled_rapi_client, BridgePoolTable,
                               MacPrefixPoolTable, VirtualMachineDiagnostic)
from synnefo.logic import utils
from synnefo import quotas

from logging import getLogger
log = getLogger(__name__)


_firewall_tags = {
    'ENABLED': settings.GANETI_FIREWALL_ENABLED_TAG,
    'DISABLED': settings.GANETI_FIREWALL_DISABLED_TAG,
    'PROTECTED': settings.GANETI_FIREWALL_PROTECTED_TAG}

_reverse_tags = dict((v.split(':')[3], k) for k, v in _firewall_tags.items())


@quotas.uses_commission
@transaction.commit_on_success
def process_op_status(serials, vm, etime, jobid, opcode, status, logmsg):
    """Process a job progress notification from the backend

    Process an incoming message from the backend (currently Ganeti).
    Job notifications with a terminating status (sucess, error, or canceled),
    also update the operating state of the VM.

    """
    # See #1492, #1031, #1111 why this line has been removed
    #if (opcode not in [x[0] for x in VirtualMachine.BACKEND_OPCODES] or
    if status not in [x[0] for x in BACKEND_STATUSES]:
        raise VirtualMachine.InvalidBackendMsgError(opcode, status)

    vm.backendjobid = jobid
    vm.backendjobstatus = status
    vm.backendopcode = opcode
    vm.backendlogmsg = logmsg

    # Notifications of success change the operating state
    state_for_success = VirtualMachine.OPER_STATE_FROM_OPCODE.get(opcode, None)
    if status == 'success' and state_for_success is not None:
        vm.operstate = state_for_success

    # Special case: if OP_INSTANCE_CREATE fails --> ERROR
    if opcode == 'OP_INSTANCE_CREATE' and status in ('canceled', 'error'):
        vm.operstate = 'ERROR'
        vm.backendtime = etime
    elif opcode == 'OP_INSTANCE_REMOVE':
        # Set the deleted flag explicitly, cater for admin-initiated removals
        # Special case: OP_INSTANCE_REMOVE fails for machines in ERROR,
        # when no instance exists at the Ganeti backend.
        # See ticket #799 for all the details.
        #
        if status == 'success' or (status == 'error' and
                                   vm.operstate == 'ERROR'):
            # Issue commission
            serial = quotas.issue_vm_commission(vm.userid, vm.flavor,
                                                delete=True)
            serials.append(serial)
            vm.serial = serial
            serial.accepted = True
            serial.save()
            release_instance_nics(vm)
            vm.nics.all().delete()
            vm.deleted = True
            vm.operstate = state_for_success
            vm.backendtime = etime

    # Update backendtime only for jobs that have been successfully completed,
    # since only these jobs update the state of the VM. Else a "race condition"
    # may occur when a successful job (e.g. OP_INSTANCE_REMOVE) completes
    # before an error job and messages arrive in reversed order.
    if status == 'success':
        vm.backendtime = etime

    vm.save()


@transaction.commit_on_success
def process_net_status(vm, etime, nics):
    """Process a net status notification from the backend

    Process an incoming message from the Ganeti backend,
    detailing the NIC configuration of a VM instance.

    Update the state of the VM in the DB accordingly.
    """

    ganeti_nics = process_ganeti_nics(nics)
    if not nics_changed(vm.nics.order_by('index'), ganeti_nics):
        log.debug("NICs for VM %s have not changed", vm)

    release_instance_nics(vm)

    for nic in ganeti_nics:
        ipv4 = nic.get('ipv4', '')
        if ipv4:
            net = nic['network']
            net.reserve_address(ipv4)

        nic['dirty'] = False
        vm.nics.create(**nic)
        # Dummy save the network, because UI uses changed-since for VMs
        # and Networks in order to show the VM NICs
        net.save()

    vm.backendtime = etime
    vm.save()


def process_ganeti_nics(ganeti_nics):
    """Process NIC dict from ganeti hooks."""
    new_nics = []
    for i, new_nic in enumerate(ganeti_nics):
        network = new_nic.get('network', '')
        n = str(network)
        pk = utils.id_from_network_name(n)

        net = Network.objects.get(pk=pk)

        # Get the new nic info
        mac = new_nic.get('mac', '')
        ipv4 = new_nic.get('ip', '')
        ipv6 = new_nic.get('ipv6', '')

        firewall = new_nic.get('firewall', '')
        firewall_profile = _reverse_tags.get(firewall, '')
        if not firewall_profile and net.public:
            firewall_profile = settings.DEFAULT_FIREWALL_PROFILE

        nic = {
               'index': i,
               'network': net,
               'mac': mac,
               'ipv4': ipv4,
               'ipv6': ipv6,
               'firewall_profile': firewall_profile}

        new_nics.append(nic)
    return new_nics


def nics_changed(old_nics, new_nics):
    """Return True if NICs have changed in any way."""
    if len(old_nics) != len(new_nics):
        return True
    for old_nic, new_nic in zip(old_nics, new_nics):
        if not (old_nic.ipv4 == new_nic['ipv4'] and\
                old_nic.ipv6 == new_nic['ipv6'] and\
                old_nic.mac == new_nic['mac'] and\
                old_nic.firewall_profile == new_nic['firewall_profile'] and\
                old_nic.index == new_nic['index'] and\
                old_nic.network == new_nic['network']):
            return True
    return False


def release_instance_nics(vm):
    for nic in vm.nics.all():
        net = nic.network
        if nic.ipv4:
            net.release_address(nic.ipv4)
        nic.delete()
        net.save()


@transaction.commit_on_success
def process_network_status(back_network, etime, jobid, opcode, status, logmsg):
    if status not in [x[0] for x in BACKEND_STATUSES]:
        raise Network.InvalidBackendMsgError(opcode, status)

    back_network.backendjobid = jobid
    back_network.backendjobstatus = status
    back_network.backendopcode = opcode
    back_network.backendlogmsg = logmsg

    # Notifications of success change the operating state
    state_for_success = BackendNetwork.OPER_STATE_FROM_OPCODE.get(opcode, None)
    if status == 'success' and state_for_success is not None:
        back_network.operstate = state_for_success

    if status in ('canceled', 'error') and opcode == 'OP_NETWORK_CREATE':
        utils.update_state(back_network, 'ERROR')
        back_network.backendtime = etime

    if opcode == 'OP_NETWORK_REMOVE':
        if status == 'success' or (status == 'error' and
                                   back_network.operstate == 'ERROR'):
            back_network.operstate = state_for_success
            back_network.deleted = True
            back_network.backendtime = etime

    if status == 'success':
        back_network.backendtime = etime
    back_network.save()
    # Also you must update the state of the Network!!
    update_network_state(back_network.network)


@quotas.uses_commission
def update_network_state(serials, network):
    old_state = network.state

    backend_states = [s.operstate for s in network.backend_networks.all()]
    if not backend_states:
        network.state = 'PENDING'
        network.save()
        return

    all_equal = len(set(backend_states)) <= 1
    network.state = all_equal and backend_states[0] or 'PENDING'

    # Release the resources on the deletion of the Network
    if old_state != 'DELETED' and network.state == 'DELETED':
        log.info("Network %r deleted. Releasing link %r mac_prefix %r",
                 network.id, network.mac_prefix, network.link)
        network.deleted = True
        if network.mac_prefix and network.type == 'PRIVATE_MAC_FILTERED':
            mac_pool = MacPrefixPoolTable.get_pool()
            mac_pool.put(network.mac_prefix)
            mac_pool.save()

        if network.link and network.type == 'PRIVATE_VLAN':
            bridge_pool = BridgePoolTable.get_pool()
            bridge_pool.put(network.link)
            bridge_pool.save()

        # Issue commission
        serial = quotas.issue_network_commission(network.userid, delete=True)
        serials.append(serial)
        network.serial = serial
        serial.accepted = True
        serial.save()

    network.save()


@transaction.commit_on_success
def process_network_modify(back_network, etime, jobid, opcode, status,
                           add_reserved_ips, remove_reserved_ips):
    assert (opcode == "OP_NETWORK_SET_PARAMS")
    if status not in [x[0] for x in BACKEND_STATUSES]:
        raise Network.InvalidBackendMsgError(opcode, status)

    back_network.backendjobid = jobid
    back_network.backendjobstatus = status
    back_network.opcode = opcode

    if add_reserved_ips or remove_reserved_ips:
        net = back_network.network
        pool = net.get_pool()
        if add_reserved_ips:
            for ip in add_reserved_ips:
                pool.reserve(ip, external=True)
        if remove_reserved_ips:
            for ip in remove_reserved_ips:
                pool.put(ip, external=True)
        pool.save()

    if status == 'success':
        back_network.backendtime = etime
    back_network.save()


@transaction.commit_on_success
def process_create_progress(vm, etime, progress):

    percentage = int(progress)

    # The percentage may exceed 100%, due to the way
    # snf-image:copy-progress tracks bytes read by image handling processes
    percentage = 100 if percentage > 100 else percentage
    if percentage < 0:
        raise ValueError("Percentage cannot be negative")

    # FIXME: log a warning here, see #1033
#   if last_update > percentage:
#       raise ValueError("Build percentage should increase monotonically " \
#                        "(old = %d, new = %d)" % (last_update, percentage))

    # This assumes that no message of type 'ganeti-create-progress' is going to
    # arrive once OP_INSTANCE_CREATE has succeeded for a Ganeti instance and
    # the instance is STARTED.  What if the two messages are processed by two
    # separate dispatcher threads, and the 'ganeti-op-status' message for
    # successful creation gets processed before the 'ganeti-create-progress'
    # message? [vkoukis]
    #
    #if not vm.operstate == 'BUILD':
    #    raise VirtualMachine.IllegalState("VM is not in building state")

    vm.buildpercentage = percentage
    vm.backendtime = etime
    vm.save()


def create_instance_diagnostic(vm, message, source, level="DEBUG", etime=None,
    details=None):
    """
    Create virtual machine instance diagnostic entry.

    :param vm: VirtualMachine instance to create diagnostic for.
    :param message: Diagnostic message.
    :param source: Diagnostic source identifier (e.g. image-helper).
    :param level: Diagnostic level (`DEBUG`, `INFO`, `WARNING`, `ERROR`).
    :param etime: The time the message occured (if available).
    :param details: Additional details or debug information.
    """
    VirtualMachineDiagnostic.objects.create_for_vm(vm, level, source=source,
            source_date=etime, message=message, details=details)


def create_instance(vm, public_nic, flavor, image, password, personality):
    """`image` is a dictionary which should contain the keys:
            'backend_id', 'format' and 'metadata'

        metadata value should be a dictionary.
    """

    if settings.IGNORE_FLAVOR_DISK_SIZES:
        if image['backend_id'].find("windows") >= 0:
            sz = 14000
        else:
            sz = 4000
    else:
        sz = flavor.disk * 1024

    # Handle arguments to CreateInstance() as a dictionary,
    # initialize it based on a deployment-specific value.
    # This enables the administrator to override deployment-specific
    # arguments, such as the disk template to use, name of os provider
    # and hypervisor-specific parameters at will (see Synnefo #785, #835).
    #
    kw = settings.GANETI_CREATEINSTANCE_KWARGS
    kw['mode'] = 'create'
    kw['name'] = vm.backend_vm_id
    # Defined in settings.GANETI_CREATEINSTANCE_KWARGS

    # Identify if provider parameter should be set in disk options.
    # Current implementation support providers only fo ext template.
    # To select specific provider for an ext template, template name
    # should be formated as `ext_<provider_name>`.
    provider = None
    disk_template = flavor.disk_template
    if flavor.disk_template.startswith("ext"):
        disk_template, provider = flavor.disk_template.split("_", 1)

    kw['disk_template'] = disk_template
    kw['disks'] = [{"size": sz}]
    if provider:
        kw['disks'][0]['provider'] = provider

        if provider == 'vlmc':
            kw['disks'][0]['origin'] = image['backend_id']

    kw['nics'] = [public_nic]
    if settings.GANETI_USE_HOTPLUG:
        kw['hotplug'] = True
    # Defined in settings.GANETI_CREATEINSTANCE_KWARGS
    # kw['os'] = settings.GANETI_OS_PROVIDER
    kw['ip_check'] = False
    kw['name_check'] = False
    # Do not specific a node explicitly, have
    # Ganeti use an iallocator instead
    #
    #kw['pnode'] = rapi.GetNodes()[0]
    kw['dry_run'] = settings.TEST

    kw['beparams'] = {
        'auto_balance': True,
        'vcpus': flavor.cpu,
        'memory': flavor.ram}

    kw['osparams'] = {
        'img_id': image['backend_id'],
        'img_passwd': password,
        'img_format': image['format']}
    if personality:
        kw['osparams']['img_personality'] = json.dumps(personality)

    if provider != None and provider == 'vlmc':
        kw['osparams']['img_id'] = 'null'

    kw['osparams']['img_properties'] = json.dumps(image['metadata'])

    # Defined in settings.GANETI_CREATEINSTANCE_KWARGS
    # kw['hvparams'] = dict(serial_console=False)
    log.debug("Creating instance %s", utils.hide_pass(kw))
    with pooled_rapi_client(vm) as client:
        return client.CreateInstance(**kw)


def delete_instance(vm):
    with pooled_rapi_client(vm) as client:
        return client.DeleteInstance(vm.backend_vm_id, dry_run=settings.TEST)


def reboot_instance(vm, reboot_type):
    assert reboot_type in ('soft', 'hard')
    with pooled_rapi_client(vm) as client:
        return client.RebootInstance(vm.backend_vm_id, reboot_type,
                                     dry_run=settings.TEST)


def startup_instance(vm):
    with pooled_rapi_client(vm) as client:
        return client.StartupInstance(vm.backend_vm_id, dry_run=settings.TEST)


def shutdown_instance(vm):
    with pooled_rapi_client(vm) as client:
        return client.ShutdownInstance(vm.backend_vm_id, dry_run=settings.TEST)


def get_instance_console(vm):
    # RAPI GetInstanceConsole() returns endpoints to the vnc_bind_address,
    # which is a cluster-wide setting, either 0.0.0.0 or 127.0.0.1, and pretty
    # useless (see #783).
    #
    # Until this is fixed on the Ganeti side, construct a console info reply
    # directly.
    #
    # WARNING: This assumes that VNC runs on port network_port on
    #          the instance's primary node, and is probably
    #          hypervisor-specific.
    #
    log.debug("Getting console for vm %s", vm)

    console = {}
    console['kind'] = 'vnc'

    with pooled_rapi_client(vm) as client:
        i = client.GetInstance(vm.backend_vm_id)

    if i['hvparams']['serial_console']:
        raise Exception("hv parameter serial_console cannot be true")
    console['host'] = i['pnode']
    console['port'] = i['network_port']

    return console


def get_instance_info(vm):
    with pooled_rapi_client(vm) as client:
        return client.GetInstanceInfo(vm.backend_vm_id)


def create_network(network, backends=None, connect=True):
    """Create and connect a network."""
    if not backends:
        backends = Backend.objects.exclude(offline=True)

    log.debug("Creating network %s in backends %s", network, backends)

    for backend in backends:
        create_jobID = _create_network(network, backend)
        if connect:
            connect_network(network, backend, create_jobID)


def _create_network(network, backend):
    """Create a network."""

    network_type = network.public and 'public' or 'private'

    tags = network.backend_tag
    if network.dhcp:
        tags.append('nfdhcpd')

    if network.public:
        conflicts_check = True
    else:
        conflicts_check = False

    try:
        bn = BackendNetwork.objects.get(network=network, backend=backend)
        mac_prefix = bn.mac_prefix
    except BackendNetwork.DoesNotExist:
        raise Exception("BackendNetwork for network '%s' in backend '%s'"\
                        " does not exist" % (network.id, backend.id))

    with pooled_rapi_client(backend) as client:
        return client.CreateNetwork(network_name=network.backend_id,
                                    network=network.subnet,
                                    network6=network.subnet6,
                                    gateway=network.gateway,
                                    gateway6=network.gateway6,
                                    network_type=network_type,
                                    mac_prefix=mac_prefix,
                                    conflicts_check=conflicts_check,
                                    tags=tags)


def connect_network(network, backend, depend_job=None, group=None):
    """Connect a network to nodegroups."""
    log.debug("Connecting network %s to backend %s", network, backend)

    mode = "routed" if "ROUTED" in network.type else "bridged"

    if network.public:
        conflicts_check = True
    else:
        conflicts_check = False

    depend_jobs = [depend_job] if depend_job else []
    with pooled_rapi_client(backend) as client:
        if group:
            client.ConnectNetwork(network.backend_id, group, mode,
                                  network.link, conflicts_check, depend_jobs)
        else:
            for group in client.GetGroups():
                client.ConnectNetwork(network.backend_id, group, mode,
                                      network.link, conflicts_check,
                                      depend_jobs)


def delete_network(network, backends=None, disconnect=True):
    if not backends:
        backends = Backend.objects.exclude(offline=True)

    log.debug("Deleting network %s from backends %s", network, backends)

    for backend in backends:
        disconnect_jobIDs = []
        if disconnect:
            disconnect_jobIDs = disconnect_network(network, backend)
        _delete_network(network, backend, disconnect_jobIDs)


def _delete_network(network, backend, depend_jobs=[]):
    with pooled_rapi_client(backend) as client:
        return client.DeleteNetwork(network.backend_id, depend_jobs)


def disconnect_network(network, backend, group=None):
    log.debug("Disconnecting network %s to backend %s", network, backend)

    with pooled_rapi_client(backend) as client:
        if group:
            return [client.DisconnectNetwork(network.backend_id, group)]
        else:
            jobs = []
            for group in client.GetGroups():
                job = client.DisconnectNetwork(network.backend_id, group)
                jobs.append(job)
            return jobs


def connect_to_network(vm, network, address=None):
    nic = {'ip': address, 'network': network.backend_id}

    log.debug("Connecting vm %s to network %s(%s)", vm, network, address)

    with pooled_rapi_client(vm) as client:
        return client.ModifyInstance(vm.backend_vm_id, nics=[('add',  nic)],
                                     hotplug=settings.GANETI_USE_HOTPLUG,
                                     dry_run=settings.TEST)


def disconnect_from_network(vm, nic):
    op = [('remove', nic.index, {})]

    log.debug("Removing nic of VM %s, with index %s", vm, str(nic.index))

    with pooled_rapi_client(vm) as client:
        return client.ModifyInstance(vm.backend_vm_id, nics=op,
                                     hotplug=settings.GANETI_USE_HOTPLUG,
                                     dry_run=settings.TEST)


def set_firewall_profile(vm, profile):
    try:
        tag = _firewall_tags[profile]
    except KeyError:
        raise ValueError("Unsopported Firewall Profile: %s" % profile)

    log.debug("Setting tag of VM %s to %s", vm, profile)

    with pooled_rapi_client(vm) as client:
        # Delete all firewall tags
        for t in _firewall_tags.values():
            client.DeleteInstanceTags(vm.backend_vm_id, [t],
                                      dry_run=settings.TEST)

        client.AddInstanceTags(vm.backend_vm_id, [tag], dry_run=settings.TEST)

        # XXX NOP ModifyInstance call to force process_net_status to run
        # on the dispatcher
        client.ModifyInstance(vm.backend_vm_id,
                         os_name=settings.GANETI_CREATEINSTANCE_KWARGS['os'])


def get_ganeti_instances(backend=None, bulk=False):
    instances = []
    for backend in get_backends(backend):
        with pooled_rapi_client(backend) as client:
            instances.append(client.GetInstances(bulk=bulk))

    return reduce(list.__add__, instances, [])


def get_ganeti_nodes(backend=None, bulk=False):
    nodes = []
    for backend in get_backends(backend):
        with pooled_rapi_client(backend) as client:
            nodes.append(client.GetNodes(bulk=bulk))

    return reduce(list.__add__, nodes, [])


def get_ganeti_jobs(backend=None, bulk=False):
    jobs = []
    for backend in get_backends(backend):
        with pooled_rapi_client(backend) as client:
            jobs.append(client.GetJobs(bulk=bulk))
    return reduce(list.__add__, jobs, [])

##
##
##


def get_backends(backend=None):
    if backend:
        return [backend]
    return Backend.objects.filter(offline=False)


def get_physical_resources(backend):
    """ Get the physical resources of a backend.

    Get the resources of a backend as reported by the backend (not the db).

    """
    nodes = get_ganeti_nodes(backend, bulk=True)
    attr = ['mfree', 'mtotal', 'dfree', 'dtotal', 'pinst_cnt', 'ctotal']
    res = {}
    for a in attr:
        res[a] = 0
    for n in nodes:
        # Filter out drained, offline and not vm_capable nodes since they will
        # not take part in the vm allocation process
        if n['vm_capable'] and not n['drained'] and not n['offline']\
           and n['cnodes']:
            for a in attr:
                res[a] += int(n[a])
    return res


def update_resources(backend, resources=None):
    """ Update the state of the backend resources in db.

    """

    if not resources:
        resources = get_physical_resources(backend)

    backend.mfree = resources['mfree']
    backend.mtotal = resources['mtotal']
    backend.dfree = resources['dfree']
    backend.dtotal = resources['dtotal']
    backend.pinst_cnt = resources['pinst_cnt']
    backend.ctotal = resources['ctotal']
    backend.updated = datetime.now()
    backend.save()


def get_memory_from_instances(backend):
    """ Get the memory that is used from instances.

    Get the used memory of a backend. Note: This is different for
    the real memory used, due to kvm's memory de-duplication.

    """
    with pooled_rapi_client(backend) as client:
        instances = client.GetInstances(bulk=True)
    mem = 0
    for i in instances:
        mem += i['oper_ram']
    return mem

##
## Synchronized operations for reconciliation
##


def create_network_synced(network, backend):
    result = _create_network_synced(network, backend)
    if result[0] != 'success':
        return result
    result = connect_network_synced(network, backend)
    return result


def _create_network_synced(network, backend):
    with pooled_rapi_client(backend) as client:
        job = _create_network(network, backend)
        result = wait_for_job(client, job)
    return result


def connect_network_synced(network, backend):
    if network.type in ('PUBLIC_ROUTED', 'CUSTOM_ROUTED'):
        mode = 'routed'
    else:
        mode = 'bridged'
    with pooled_rapi_client(backend) as client:
        for group in client.GetGroups():
            job = client.ConnectNetwork(network.backend_id, group, mode,
                                        network.link)
            result = wait_for_job(client, job)
            if result[0] != 'success':
                return result

    return result


def wait_for_job(client, jobid):
    result = client.WaitForJobChange(jobid, ['status', 'opresult'], None, None)
    status = result['job_info'][0]
    while status not in ['success', 'error', 'cancel']:
        result = client.WaitForJobChange(jobid, ['status', 'opresult'],
                                        [result], None)
        status = result['job_info'][0]

    if status == 'success':
        return (status, None)
    else:
        error = result['job_info'][1]
        return (status, error)
