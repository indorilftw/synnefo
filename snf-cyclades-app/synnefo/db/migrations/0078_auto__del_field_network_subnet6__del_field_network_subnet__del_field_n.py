# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Network.subnet6'
        db.delete_column('db_network', 'subnet6')

        # Deleting field 'Network.subnet'
        db.delete_column('db_network', 'subnet')

        # Deleting field 'Network.gateway'
        db.delete_column('db_network', 'gateway')

        # Deleting field 'Network.dhcp'
        db.delete_column('db_network', 'dhcp')

        # Deleting field 'Network.pool'
        db.delete_column('db_network', 'pool_id')

        # Deleting field 'Network.gateway6'
        db.delete_column('db_network', 'gateway6')

        # Adding field 'Network.external_router'
        db.add_column('db_network', 'external_router',
                      self.gf('django.db.models.fields.BooleanField')(default=False),
                      keep_default=False)

    def backwards(self, orm):
        # Adding field 'Network.subnet6'
        db.add_column('db_network', 'subnet6',
                      self.gf('django.db.models.fields.CharField')(max_length=64, null=True),
                      keep_default=False)

        # Adding field 'Network.subnet'
        db.add_column('db_network', 'subnet',
                      self.gf('django.db.models.fields.CharField')(max_length=32, null=True),
                      keep_default=False)

        # Adding field 'Network.gateway'
        db.add_column('db_network', 'gateway',
                      self.gf('django.db.models.fields.CharField')(max_length=32, null=True),
                      keep_default=False)

        # Adding field 'Network.dhcp'
        db.add_column('db_network', 'dhcp',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'Network.pool'
        db.add_column('db_network', 'pool',
                      self.gf('django.db.models.fields.related.OneToOneField')(related_name='network', unique=True, null=True, to=orm['db.IPPoolTable']),
                      keep_default=False)

        # Adding field 'Network.gateway6'
        db.add_column('db_network', 'gateway6',
                      self.gf('django.db.models.fields.CharField')(max_length=64, null=True),
                      keep_default=False)

        # Deleting field 'Network.external_router'
        db.delete_column('db_network', 'external_router')

    models = {
        'db.backend': {
            'Meta': {'ordering': "['clustername']", 'object_name': 'Backend'},
            'clustername': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'ctotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'dfree': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'disk_templates': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'drained': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'dtotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'hash': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'hypervisor': ('django.db.models.fields.CharField', [], {'default': "'kvm'", 'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0', 'unique': 'True'}),
            'mfree': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'mtotal': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'offline': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'password_hash': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            'pinst_cnt': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'port': ('django.db.models.fields.PositiveIntegerField', [], {'default': '5080'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True', 'blank': 'True'})
        },
        'db.backendnetwork': {
            'Meta': {'unique_together': "(('network', 'backend'),)", 'object_name': 'BackendNetwork'},
            'backend': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'networks'", 'on_delete': 'models.PROTECT', 'to': "orm['db.Backend']"}),
            'backendjobid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'backendjobstatus': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendlogmsg': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'backendopcode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendtime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1, 1, 1, 0, 0)'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mac_prefix': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'backend_networks'", 'to': "orm['db.Network']"}),
            'operstate': ('django.db.models.fields.CharField', [], {'default': "'PENDING'", 'max_length': '30'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'db.bridgepooltable': {
            'Meta': {'object_name': 'BridgePoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.flavor': {
            'Meta': {'unique_together': "(('cpu', 'ram', 'disk', 'disk_template'),)", 'object_name': 'Flavor'},
            'cpu': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'disk': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'disk_template': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ram': ('django.db.models.fields.IntegerField', [], {'default': '0'})
        },
        'db.floatingip': {
            'Meta': {'object_name': 'FloatingIP'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipv4': ('django.db.models.fields.IPAddressField', [], {'unique': 'True', 'max_length': '15', 'db_index': 'True'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'floating_ips'", 'null': 'True', 'to': "orm['db.VirtualMachine']"}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'floating_ips'", 'to': "orm['db.Network']"}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'floating_ips'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'db.ippooltable': {
            'Meta': {'object_name': 'IPPoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {}),
            'subnet': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'ip_pools'", 'null': 'True', 'to': "orm['db.Subnet']"})
        },
        'db.macprefixpooltable': {
            'Meta': {'object_name': 'MacPrefixPoolTable'},
            'available_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'base': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'offset': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'reserved_map': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'size': ('django.db.models.fields.IntegerField', [], {})
        },
        'db.network': {
            'Meta': {'object_name': 'Network'},
            'action': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '32', 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'drained': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'external_router': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'flavor': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'floating_ip_pool': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True'}),
            'mac_prefix': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'machines': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['db.VirtualMachine']", 'through': "orm['db.NetworkInterface']", 'symmetrical': 'False'}),
            'mode': ('django.db.models.fields.CharField', [], {'max_length': '16', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'network'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'PENDING'", 'max_length': '32'}),
            'tags': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'db_index': 'True'})
        },
        'db.networkinterface': {
            'Meta': {'unique_together': "(('network', 'ipv4'),)", 'object_name': 'NetworkInterface'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'dirty': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'firewall_profile': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'index': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'ipv4': ('django.db.models.fields.CharField', [], {'max_length': '15', 'null': 'True'}),
            'ipv6': ('django.db.models.fields.CharField', [], {'max_length': '100', 'null': 'True'}),
            'mac': ('django.db.models.fields.CharField', [], {'max_length': '32', 'unique': 'True', 'null': 'True'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'nics'", 'to': "orm['db.VirtualMachine']"}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'nics'", 'to': "orm['db.Network']"}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'ACTIVE'", 'max_length': '32'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'db.quotaholderserial': {
            'Meta': {'ordering': "['serial']", 'object_name': 'QuotaHolderSerial'},
            'accept': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'pending': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'resolved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'serial': ('django.db.models.fields.BigIntegerField', [], {'primary_key': 'True', 'db_index': 'True'})
        },
        'db.subnet': {
            'Meta': {'object_name': 'Subnet'},
            'cidr': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'dhcp': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'dns_nameservers': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'gateway': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True'}),
            'host_routes': ('synnefo.db.fields.SeparatedValuesField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ipversion': ('django.db.models.fields.IntegerField', [], {'default': '4'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'network': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'subnets'", 'to': "orm['db.Network']"})
        },
        'db.virtualmachine': {
            'Meta': {'object_name': 'VirtualMachine'},
            'action': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '30', 'null': 'True'}),
            'backend': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'virtual_machines'", 'null': 'True', 'on_delete': 'models.PROTECT', 'to': "orm['db.Backend']"}),
            'backend_hash': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'backendjobid': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True'}),
            'backendjobstatus': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendlogmsg': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'backendopcode': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'backendtime': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1, 1, 1, 0, 0)'}),
            'buildpercentage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'deleted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'flavor': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['db.Flavor']", 'on_delete': 'models.PROTECT'}),
            'hostid': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'imageid': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'operstate': ('django.db.models.fields.CharField', [], {'default': "'BUILD'", 'max_length': '30'}),
            'serial': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'virtual_machine'", 'null': 'True', 'on_delete': 'models.SET_NULL', 'to': "orm['db.QuotaHolderSerial']"}),
            'suspended': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'task': ('django.db.models.fields.CharField', [], {'max_length': '64', 'null': 'True'}),
            'task_job_id': ('django.db.models.fields.BigIntegerField', [], {'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'userid': ('django.db.models.fields.CharField', [], {'max_length': '100', 'db_index': 'True'})
        },
        'db.virtualmachinediagnostic': {
            'Meta': {'ordering': "['-created']", 'object_name': 'VirtualMachineDiagnostic'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'details': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'machine': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'diagnostics'", 'to': "orm['db.VirtualMachine']"}),
            'message': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'source_date': ('django.db.models.fields.DateTimeField', [], {'null': 'True'})
        },
        'db.virtualmachinemetadata': {
            'Meta': {'unique_together': "(('meta_key', 'vm'),)", 'object_name': 'VirtualMachineMetadata'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meta_key': ('django.db.models.fields.CharField', [], {'max_length': '50'}),
            'meta_value': ('django.db.models.fields.CharField', [], {'max_length': '500'}),
            'vm': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'metadata'", 'to': "orm['db.VirtualMachine']"})
        }
    }

    complete_apps = ['db']
