import configparser
import itertools
import os
import unicodedata

from oauthlib.oauth2 import BackendApplicationClient
import pysnow
from pysnow import exceptions
from requests_oauthlib import OAuth2Session


# ====================== Environment / Global Variables =======================
# Configuration file access variables.
CONFIG = configparser.ConfigParser()
CONFIG_PATH = '/../configs/2022_diko_project_config.ini'
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
CONFIG.read(SCRIPT_PATH + CONFIG_PATH)

# ServiceNow API credentials.
SNOW_INSTANCE = CONFIG['ServiceNow Info']['instance']
SNOW_USERNAME = CONFIG['ServiceNow Info']['username']
SNOW_PASSWORD = CONFIG['ServiceNow Info']['password']
SNOW_CMDB_PATH = CONFIG['ServiceNow Info']['cmdb-table']
SNOW_CLIENT = pysnow.Client(instance=SNOW_INSTANCE,
                            user=SNOW_USERNAME,
                            password=SNOW_PASSWORD)

# Cisco Support API credentials.
CISCO_CLIENT_ID = CONFIG['Cisco Info']['client-id']
CISCO_CLIENT_SECRET = CONFIG['Cisco Info']['client-secret']
CISCO_TOKEN_URL = CONFIG['Cisco Info']['token-url']
CISCO_BASE_WARRANTY_URL = CONFIG['Cisco Info']['base-warranty-url']
CISCO_BASE_EOX_URL = CONFIG['Cisco Info']['base-eox-url']

# Dell TechDirect (Warranty) API credentials.
DELL_CLIENT_ID = CONFIG['Dell Info']['client-id']
DELL_CLIENT_SECRET = CONFIG['Dell Info']['client-secret']
DELL_TOKEN_URL = CONFIG['Dell Info']['token-url']
DELL_BASE_WARRANTY_URL = CONFIG['Dell Info']['base-warranty-url']


# ================================= Functions =================================
# Get all Cisco records from ServiceNow and return it as a dictionary. The
# key is the Cisco device's serial number and the value is the record.
def get_snow_cisco_records() -> dict[str, dict[str, str]]:
    print('Getting all Cisco records from ServiceNow...')

    # Get all Cisco records from ServiceNow.
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_cisco_query = (pysnow.QueryBuilder().
                        field('name').order_ascending().
                        AND().
                        field('manufacturer').contains('Cisco').
                        OR().
                        field('manufacturer').contains('Meraki')
                        )
    snow_cisco_resp = snow_cmdb_table.get(
        query=snow_cisco_query,
        fields=['sys_id', 'name', 'serial_number', 'asset_tag',
                'u_active_support_contract', 'warranty_expiration',
                'u_end_of_life', 'u_valid_warranty_data']
    )
    snow_cisco_devs = snow_cisco_resp.all()

    # Go through all Cisco records and extract valid records.
    snow_cisco_dict = dict()
    no_sn = 0
    collisions = 0
    for cisco_dev in snow_cisco_devs:
        # Check if there is no S/N or an invalid character(s) in the S/N field.
        cis_dev_sn = unicodedata.normalize('NFKD', cisco_dev[
            'serial_number']).replace(' ', '')
        if cis_dev_sn == '' or '/' in cis_dev_sn or '\\' in cis_dev_sn:
            # Check the 'asset_tag' field for a valid S/N.
            cis_dev_sn = unicodedata.normalize('NFKD', cisco_dev[
                'asset_tag']).replace(' ', '')
            if cis_dev_sn == '' or '/' in cis_dev_sn or '\\' in cis_dev_sn:
                # Invalid S/N found in the asset tag field too.
                update_snow_cisco_invalid_data(cisco_dev, 'Invalid S/N')
                no_sn += 1
                continue

            # Update the 'serial_number' field in ServiceNow from the
            # 'asset_tag' field.
            update_snow_cisco_sn(cisco_dev, cis_dev_sn)

        # Check if this record is a duplicate. Skip if so.
        if cis_dev_sn in snow_cisco_dict.keys():
            collisions += 1
            continue

        # Add this record to the Cisco devices dictionary.
        cisco_dev['serial_number'] = cis_dev_sn
        snow_cisco_dict[cis_dev_sn] = cisco_dev

    # Output information found while iterating through the Cisco records.
    print('I found ' + str(len(snow_cisco_dict.keys())) +
          ' valid Cisco records in ServiceNow')
    print('I could not find a valid S/N for ' + str(no_sn) +
          ' Cisco records in ServiceNow')
    print('I found ' + str(collisions) +
          ' duplicate Cisco records in ServiceNow')
    print('All valid Cisco records retrieved from ServiceNow!')

    return snow_cisco_dict


# Get all Dell records from ServiceNow and return it as a dictionary. The
# key is the Dell device's service tag and the value is the record.
def get_snow_dell_records() -> dict[str, dict[str, str]]:
    print('Getting all Dell records from ServiceNow...')

    # Get all Dell devices from ServiceNow.
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_dell_query = (pysnow.QueryBuilder().
                       field('name').order_ascending().
                       AND().
                       field('manufacturer').contains('Dell')
                       )
    snow_dell_resp = snow_cmdb_table.get(
        query=snow_dell_query,
        fields=['sys_id', 'name', 'serial_number', 'asset_tag',
                'u_active_support_contract', 'warranty_expiration',
                'u_end_of_life', 'u_valid_warranty_data']
    )
    snow_dell_devs = snow_dell_resp.all()

    # Go through all Dell records and extract valid records.
    snow_dell_dict = dict()
    no_sn = 0
    collisions = 0
    for dell_dev in snow_dell_devs:
        # Check if this device has a valid service tag in the S/N field.
        dell_dev_service_tag = unicodedata.normalize('NFKD', dell_dev[
            'serial_number']).replace(' ', '')
        if dell_dev_service_tag == '' or '/' in dell_dev_service_tag or \
           len(dell_dev_service_tag) > 7 or len(dell_dev_service_tag) < 5:
            # Invalid service tag in the 'serial_number' field. Let's check
            # the 'asset_tag' field for a valid service tag.
            dell_dev_service_tag = unicodedata.normalize('NFKD', dell_dev[
                'asset_tag']).replace(' ', '')
            if dell_dev_service_tag == '' or '/' in dell_dev_service_tag or \
               len(dell_dev_service_tag) > 7 or len(dell_dev_service_tag) < 5:
                # Invalid service tag found in the asset_tag field too.
                update_snow_dell_invalid_data(dell_dev, 'Invalid S/N')
                no_sn += 1
                continue

            # Update the 'serial_number' field from the 'asset_tag' field in
            # ServiceNow.
            update_snow_dell_sn(dell_dev, dell_dev_service_tag)

        # Check if this record is a duplicate. Skip if so.
        if dell_dev_service_tag in snow_dell_dict.keys():
            collisions += 1
            continue

        # Add this record to the Dell devices dictionary.
        dell_dev['serial_number'] = dell_dev_service_tag
        snow_dell_dict[dell_dev_service_tag] = dell_dev

    # Output information found while iterating through the Dell records.
    print('I found ' + str(len(snow_dell_dict.keys())) +
          ' valid Dell records in ServiceNow')
    print('I could not find a valid service tag for ' + str(no_sn) +
          ' Dell records in ServiceNow')
    print('I found ' + str(collisions) +
          ' duplicate Dell records in ServiceNow')
    print('All valid Dell records retrieved from ServiceNow!')

    return snow_dell_dict


# Given a dictionary of Cisco devices, update their ServiceNow records with
# warranty and end-of-life information.
def update_snow_cisco_warranties(snow_cisco_devs: dict[str, dict[str, str]]):
    print('Updating all Cisco records in ServiceNow...')

    # Get a Cisco Support API token to establish a connection to the API.
    warranty_client = BackendApplicationClient(client_id=CISCO_CLIENT_ID)
    warranty_oauth = OAuth2Session(client=warranty_client)
    warranty_token = warranty_oauth.fetch_token(
        token_url=CISCO_TOKEN_URL,
        client_id=CISCO_CLIENT_ID,
        client_secret=CISCO_CLIENT_SECRET)
    warranty_client = OAuth2Session(CISCO_CLIENT_ID, token=warranty_token)

    # Get a Cisco EOX API token to establish a connection to the API.
    eox_client = BackendApplicationClient(client_id=CISCO_CLIENT_ID)
    eox_oauth = OAuth2Session(client=eox_client)
    eox_token = eox_oauth.fetch_token(token_url=CISCO_TOKEN_URL,
                                      client_id=CISCO_CLIENT_ID,
                                      client_secret=CISCO_CLIENT_SECRET)
    eox_client = OAuth2Session(CISCO_CLIENT_ID, token=eox_token)

    # Get all provided Cisco device's warranty summaries / End-Of-life
    # information in batches of 20 (This is the maximum the Cisco EOX API
    # allows in 1 batch, which is less than the maximum of 50 for the Cisco
    # Support API in 1 batch)
    for batch in batcher(list(snow_cisco_devs.keys()), 20):
        # Prepare the batch request for Cisco warranties.
        sn_batch = ','.join(batch)
        warranty_url = CISCO_BASE_WARRANTY_URL + sn_batch

        # Get the warranty summary batch and convert it to JSON.
        warranty_resp = warranty_client.get(url=warranty_url)
        warranty_batch_resp = warranty_resp.json()

        # Iterate through this batch and update ServiceNow.
        for cis_dev in warranty_batch_resp['serial_numbers']:
            # Check if the API didn't find a device with this S/N.
            if 'ErrorResponse' in cis_dev.keys():
                # Check if the Cisco API gave back a weird S/N. Skip if so.
                if cis_dev['sr_no'] not in snow_cisco_devs.keys():
                    print('Cisco API error - weird S/N returned: ' +
                          cis_dev['sr_no'])
                    continue

                # Update the 'u_valid_warranty_data' field in ServiceNow to
                # false.
                update_snow_cisco_invalid_data(
                    snow_cisco_devs[cis_dev['sr_no']], 'Cisco Support API '
                                                       'Error Response')
                continue

            # Update this record.
            update_snow_cisco_record(cis_dev,
                                     snow_cisco_devs[cis_dev['sr_no']])

        # Prepare the batch request for Cisco EOX.
        eox_url = CISCO_BASE_EOX_URL + sn_batch

        # Get the EOX batch and convert it to JSON.
        eox_resp = eox_client.get(url=eox_url,
                                  params={
                                      'responseencoding': 'json'
                                  })
        eox_batch_resp = eox_resp.json()

        # Check if this is a valid batch...
        if 'EOXRecord' not in eox_batch_resp.keys():
            print('Invalid EOXRecord found')
            continue

        # Iterate through this batch and update ServiceNow.
        for cis_devs in eox_batch_resp['EOXRecord']:
            eol_str = cis_devs['LastDateOfSupport']['value']

            # There could be multiple records with the same EoL information,
            # so we need to loop through each one.
            for cis_dev_sn in cis_devs['EOXInputValue'].split(','):
                # Check if this device has no End-Of-Life information.
                if eol_str == '':
                    update_snow_cisco_no_eol(snow_cisco_devs[cis_dev_sn])
                    continue

                # Update this record.
                update_snow_cisco_eol(snow_cisco_devs[cis_dev_sn], eol_str)

    print('All Cisco records updated in ServiceNow!')


# Given a dictionary of Dell devices, update their ServiceNow records with
# warranty information.
def update_snow_dell_warranties(snow_dell_devs: dict[str, dict[str, str]]):
    print('Updating all Dell records in ServiceNow...')

    # Get a Dell TechDirect API token to establish a connection to the API.
    client = BackendApplicationClient(client_id=DELL_CLIENT_ID)
    oauth = OAuth2Session(client=client)
    token = oauth.fetch_token(token_url=DELL_TOKEN_URL,
                              client_id=DELL_CLIENT_ID,
                              client_secret=DELL_CLIENT_SECRET)
    client = OAuth2Session(DELL_CLIENT_ID, token=token)

    # Get all provided Dell device's warranty summaries in batches of 100.
    # This is the maximum the Dell TechDirect API allows.
    for batch in batcher(list(snow_dell_devs.keys()), 100):
        # Prepare the batch request for Dell warranties.
        sn_batch = ','.join(batch)

        # Get the warranty batch and convert it to JSON.
        warranty_resp = client.get(url=DELL_BASE_WARRANTY_URL,
                                   headers={
                                       'Accept': 'application/json'
                                   },
                                   params={
                                       'servicetags': sn_batch
                                   })
        batch_resp = warranty_resp.json()

        # Iterate through this batch and update ServiceNow.
        for dell_dev in batch_resp:
            # Check if the API didn't find a device with this service tag.
            if dell_dev['id'] is None:
                # Weird exception...
                if dell_dev['serviceTag'] == 'AMALONE':
                    continue

                # Update the 'u_valid_warranty_data' field in ServiceNow to
                # false.
                update_snow_dell_invalid_data(
                    snow_dell_devs[dell_dev['serviceTag']],
                    'Dell Warranty API Error Response')
                continue

            # Update this record.
            update_snow_dell_record(dell_dev,
                                    snow_dell_devs[dell_dev['serviceTag']])

    print('All Dell records updated in ServiceNow!')


# Return specified batches of an iterable object.
# Credit: @georg from stackoverflow, with slight modifications
# Link: https://stackoverflow.com/a/28022548
def batcher(iterable, batch_size):
    # Make an iterator object from the iterable.
    iterator = iter(iterable)

    # Return each batch one at a time using yield.
    while True:
        batch = tuple(itertools.islice(iterator, batch_size))
        if not batch:
            break
        yield batch


# Given a Cisco device and the related ServiceNow record, update ServiceNow
# if the records don't match.
def update_snow_cisco_record(cis_dev, snow_cis_dev):
    # Make variable to store any updates needed in ServiceNow.
    snow_update = {}

    # Check if this Cisco device has a warranty or is covered by a support
    # contract.
    if cis_dev['warranty_end_date'] == '' and cis_dev['is_covered'] != 'YES':
        if snow_cis_dev['u_valid_warranty_data'] != 'false':
            snow_cis_dev['u_valid_warranty_data'] = 'false'
            snow_update['u_valid_warranty_data'] = 'false'
    else:
        if snow_cis_dev['u_valid_warranty_data'] != 'true':
            snow_cis_dev['u_valid_warranty_data'] = 'true'
            snow_update['u_valid_warranty_data'] = 'true'

    # Check if the warranty end date is not in ServiceNow.
    if snow_cis_dev['warranty_expiration'] != cis_dev['warranty_end_date']:
        snow_cis_dev['warranty_expiration'] = cis_dev['warranty_end_date']
        snow_update['warranty_expiration'] = cis_dev['warranty_end_date']

    # Make sure SNow reflects that this warranty data is valid.
    if cis_dev['is_covered'] != 'YES':
        if snow_cis_dev['u_active_support_contract'] != 'false':
            snow_cis_dev['u_active_support_contract'] = 'false'
            snow_update['u_active_support_contract'] = 'false'
    else:
        if snow_cis_dev['u_active_support_contract'] != 'true':
            snow_cis_dev['u_active_support_contract'] = 'true'
            snow_update['u_active_support_contract'] = 'true'

    # Update ServiceNow if needed.
    if snow_update:
        snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
        print('Updating Cisco record: ' + snow_cis_dev['name'])

        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'name': snow_cis_dev['name'],
                    'serial_number': snow_cis_dev['serial_number']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Cisco record has a duplicate(s) and can not be updated!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            return
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Cisco record could not be found!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            return

        print('Finished updating Cisco record: ' + snow_cis_dev['name'])


# Given a Dell device and the related ServiceNow record, update ServiceNow
# if the records don't match.
def update_snow_dell_record(dell_dev, snow_dell_dev):
    # Make variable to store any updates needed in ServiceNow.
    snow_update = {}

    # Check if this Dell device has a warranty end date.
    if len(dell_dev['entitlements']) == 0:
        update_snow_dell_no_warranty(dell_dev, snow_dell_dev)
        return

    # Get the warranty end as a string.
    dell_warranty_end = \
        dell_dev['entitlements'][len(dell_dev['entitlements']) - 1][
            'endDate'][:10]

    # Check if the warranty end date is not in ServiceNow.
    if snow_dell_dev['warranty_expiration'] != dell_warranty_end:
        snow_dell_dev['warranty_expiration'] = dell_warranty_end
        snow_update['warranty_expiration'] = dell_warranty_end

    # Check this field.
    if snow_dell_dev['u_valid_warranty_data'] != 'true':
        snow_dell_dev['u_valid_warranty_data'] = 'true'
        snow_update['u_valid_warranty_data'] = 'true'

    # Update ServiceNow if needed.
    if snow_update:
        snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
        print('Updating Dell record: ' + snow_dell_dev['name'])

        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'name': snow_dell_dev['name'],
                    'serial_number': snow_dell_dev['serial_number']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Dell record has duplicate and can not be updated!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Dell record could not be found!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])

        print('Finished updating Dell record: ' + snow_dell_dev['name'])


# Given a Dell device with no warranty and the related ServiceNow record,
# update ServiceNow if the records don't match.
def update_snow_dell_no_warranty(dell_dev, snow_dell_dev):
    print('No warranty detected: ' + dell_dev['serviceTag'])
    snow_update = {}

    # Check if the warranty end date is not in ServiceNow.
    if snow_dell_dev['warranty_expiration'] != '':
        snow_dell_dev['warranty_expiration'] = ''
        snow_update['warranty_expiration'] = ''

    # Make sure SNow reflects that this warranty data is not valid.
    if snow_dell_dev['u_valid_warranty_data'] != 'false':
        snow_dell_dev['u_valid_warranty_data'] = 'false'
        snow_update['u_valid_warranty_data'] = 'false'

    # Update ServiceNow if needed.
    if snow_update:
        snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
        print('Updating Dell record: ' + snow_dell_dev['name'])

        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'name': snow_dell_dev['name'],
                    'serial_number': snow_dell_dev['serial_number']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Dell record has duplicate and can not be updated!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Dell record could not be found!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])

        print('Finished updating Dell record: ' + snow_dell_dev['name'])


# Update the 'serial_number' field to a valid serial number in ServiceNow
# for a given Cisco device.
def update_snow_cisco_sn(snow_cis_dev, new_sn):
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    print('S/N found in the asset tag field! Updating S/N field for Cisco '
          'record: ' + snow_cis_dev['name'])

    # Try to update this record.
    try:
        snow_cmdb_table.update(
            query={
                'name': snow_cis_dev['name'],
                'asset_tag': snow_cis_dev['asset_tag']
            },
            payload={
                'serial_number': new_sn
            }
        )
    except exceptions.MultipleResults:
        # We got multiple results. Must be a duplicate.
        print('Cisco record has a duplicate and the S/N can not be updated!')
        print('  Name: ' + snow_cis_dev['name'])
        print('  S/N: ' + snow_cis_dev['serial_number'])
        print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
        return
    except exceptions.NoResults:
        # We didn't get any results. We can't update this record.
        print('Cisco record could not be found!')
        print('  Name: ' + snow_cis_dev['name'])
        print('  S/N: ' + snow_cis_dev['serial_number'])
        print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
        return

    print('S/N field for Cisco record ' + snow_cis_dev['name'] +
          ' has been updated successfully!')


# Update the 'serial_number' field to a valid serial number in ServiceNow
# for a given Dell device.
def update_snow_dell_sn(snow_dell_dev, new_sn):
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    print('S/N found in the asset tag field! Updating S/N field for Dell '
          'record: ' + snow_dell_dev['name'])

    # Try to update this record.
    try:
        snow_cmdb_table.update(
            query={
                'name': snow_dell_dev['name'],
                'asset_tag': snow_dell_dev['asset_tag']
            },
            payload={
                'serial_number': new_sn
            }
        )
    except exceptions.MultipleResults:
        # We got multiple results. Must be a duplicate.
        print('Dell record has a duplicate and the S/N can not be updated!')
        print('  Name: ' + snow_dell_dev['name'])
        print('  S/N: ' + snow_dell_dev['serial_number'])
        print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
        return
    except exceptions.NoResults:
        # We didn't get any results. We can't update this record.
        print('Dell record could not be found!')
        print('  Name: ' + snow_dell_dev['name'])
        print('  S/N: ' + snow_dell_dev['serial_number'])
        print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
        return

    print('S/N field for Dell record ' + snow_dell_dev['name'] +
          ' has been updated successfully!')


# Update the invalid warranty field for the given Cisco device in ServiceNow.
def update_snow_cisco_invalid_data(snow_cis_dev, invalid_reason):
    print('Invalid data for Cisco device: ' + snow_cis_dev['name'])
    print('  Reason: ' + invalid_reason)
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_update = {}

    # Check if this field is set correctly.
    if snow_cis_dev['u_valid_warranty_data'] != 'false':
        snow_cis_dev['u_valid_warranty_data'] = 'false'
        snow_update['u_valid_warranty_data'] = 'false'

    # Check if this ServiceNow record needs to be updated.
    if snow_update:
        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'sys_id': snow_cis_dev['sys_id']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Cisco record has duplicate and the valid data '
                  'field can not be updated to false!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Cisco record could not be found!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return

        print('Valid data field for Cisco record ' + snow_cis_dev['name']
              + ' has been updated to false!')


# Update the invalid warranty field for the given Dell device in ServiceNow.
def update_snow_dell_invalid_data(snow_dell_dev, invalid_reason):
    print('Invalid data for Dell device: ' + snow_dell_dev['name'])
    print('  Reason: ' + invalid_reason)
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_update = {}

    # Check if this field is set correctly.
    if snow_dell_dev['u_valid_warranty_data'] != 'false':
        snow_dell_dev['u_valid_warranty_data'] = 'false'
        snow_update['u_valid_warranty_data'] = 'false'

    # Check if this ServiceNow record needs to be updated.
    if snow_update:
        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'sys_id': snow_dell_dev['sys_id']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Dell record has duplicate and the valid data '
                  'field can not be updated!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
            return
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Dell record could not be found!')
            print('  Name: ' + snow_dell_dev['name'])
            print('  S/N: ' + snow_dell_dev['serial_number'])
            print('  Asset Tag: ' + snow_dell_dev['asset_tag'])
            return

        print('Valid data field for Dell record ' + snow_dell_dev[
            'name'] + ' has been updated to false!')


# This function will update the provided record into ServiceNow with
# the provided end-of-life string.
def update_snow_cisco_eol(snow_cis_dev, eol_str):
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_update = {}

    # Check if this field is set correctly.
    if snow_cis_dev['u_end_of_life'] != eol_str:
        snow_cis_dev['u_end_of_life'] = eol_str
        snow_update['u_end_of_life'] = eol_str

    if snow_cis_dev['u_valid_warranty_data'] == 'false':
        snow_cis_dev['u_valid_warranty_data'] = 'true'
        snow_update['u_valid_warranty_data'] = 'true'

    # Check if this ServiceNow record needs to be updated.
    if snow_update:
        print('Updating EoL for Cisco device: ' + snow_cis_dev['name'])

        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'name': snow_cis_dev['name'],
                    'serial_number': snow_cis_dev['serial_number']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Cisco record has duplicate and the EoL field can not be '
                  'updated!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Cisco record could not be found!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return

        print('EoL was updated for Cisco device: ' + snow_cis_dev['name'] +
              '!')


# This function will update the provided record into ServiceNow with no
# end-of-life information.
def update_snow_cisco_no_eol(snow_cis_dev):
    print('No EOL information found for Cisco device: ' + snow_cis_dev['name'])
    snow_cmdb_table = SNOW_CLIENT.resource(api_path=SNOW_CMDB_PATH)
    snow_update = {}

    # Check if this field is set correctly.
    if snow_cis_dev['u_end_of_life'] != '':
        snow_cis_dev['u_end_of_life'] = ''
        snow_update['u_end_of_life'] = ''

    # Check if this ServiceNow record needs to be updated.
    if snow_update:
        print('Updating EoL for Cisco device: ' + snow_cis_dev['name'])

        # Try to update this record.
        try:
            snow_cmdb_table.update(
                query={
                    'name': snow_cis_dev['name'],
                    'serial_number': snow_cis_dev['serial_number']
                },
                payload=snow_update
            )
        except exceptions.MultipleResults:
            # We got multiple results. Must be a duplicate.
            print('Cisco record has duplicate and the EoL field can not be '
                  'updated!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return
        except exceptions.NoResults:
            # We didn't get any results. We can't update this record.
            print('Cisco record could not be found!')
            print('  Name: ' + snow_cis_dev['name'])
            print('  S/N: ' + snow_cis_dev['serial_number'])
            print('  Asset Tag: ' + snow_cis_dev['asset_tag'])
            return

        print('EoL was updated for Cisco device: ' + snow_cis_dev['name'] +
              '!')


# Main method to run the script.
if __name__ == '__main__':
    # Get Cisco devices.
    snow_cisco_records_dict = get_snow_cisco_records()

    # Update Cisco devices in ServiceNow.
    update_snow_cisco_warranties(snow_cisco_records_dict)

    # Get Dell devices.
    snow_dell_records_dict = get_snow_dell_records()

    # Update Dell devices in ServiceNow.
    update_snow_dell_warranties(snow_dell_records_dict)
