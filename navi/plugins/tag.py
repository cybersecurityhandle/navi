import click
import csv
from .database import new_db_connection
from .api_wrapper import request_data, request_no_response, tenb_connection
from .tag_helper import update_tag, confirm_tag_exists, return_tag_uuid
from sqlite3 import Error
import json


def tag_by_tag(c, v, d, cv, cc):
    tag_uuid = 0
    # Start a blank rules list to store current a new tag rule.
    rules_list = []

    # Does the Parent Tag exist?
    parent_answer = confirm_tag_exists(c, v)

    # Is this the parent tag new or current?
    if parent_answer == 'yes':

        # Does the Child Tag Exist?
        child_answer = confirm_tag_exists(cc, cv)

        # Is the child tag new or current?
        if child_answer == 'yes':

            # Update the tag parent tag with the new child tag
            click.echo("Your tag is being updated\n")

            try:
                rules_list.append({"field": "tag.{}".format(cc), "operator": "set-has", "value": str(cv)})
                # Need to grab the Tag UUID of our Parent Tag so we can get more details
                tag_data = request_data('GET', '/tags/values')
                for value in tag_data['values']:
                    if value['category_name'] == str(c):
                        if value['value'] == str(v):
                            try:
                                tag_uuid = value['uuid']
                                # Get filter details
                                tag_sepcs = request_data("GET", "/tags/values/" + tag_uuid)

                                # The filter is a string in the API, pull out the dictionary representation and
                                # Turn the string into a dictionary
                                filter_string = tag_sepcs['filters']['asset']
                                newstring = json.loads(filter_string)

                                # Go through each filter and add it to the rules list for re-application
                                for filters in newstring["and"]:
                                    # To prevent or correct duplicates
                                    if filters not in rules_list:
                                        rules_list.append(filters)
                            except Exception as F:
                                click.echo(F)

                payload = {"category_name": str(c), "value": str(v), "description": str(d), "filters": {"asset": {"or": rules_list}}}
                # Update the Parent Tag with the new child tag information
                data = request_data('PUT', '/tags/values/' + tag_uuid, payload=payload)

                value_uuid = data["uuid"]
                cat_uuid = data['category_uuid']
                click.echo("\nI've Updated your Tag - {} : {}\n".format(c, v))
                click.echo("The Category UUID is : {}\n".format(cat_uuid))
                click.echo("The Value UUID is : {}\n".format(value_uuid))
            except Exception as E:
                click.echo(E)
        else:
            click.echo("The Child Tag does not exist")

    else:
        # If the parent tag doesn't exist, does the child?
        # Check to see if the child tag exists
        child_answer = confirm_tag_exists(cc, cv)
        if child_answer == 'yes':
            # if the child tag does exist, then create the new tag with the existing tag as a child
            try:
                payload = {"category_name": str(c), "value": str(v), "description": str(d), "filters":
                           {"asset": {"or": [{"field": "tag.{}".format(cc), "operator": "set-has", "value": str(cv)}]}}}
                data = request_data('POST', '/tags/values', payload=payload)

                value_uuid = data["uuid"]
                cat_uuid = data['category_uuid']
                click.echo("\nI've created your new Tag - {} : {}\n".format(c, v))
                click.echo("The Category UUID is : {}\n".format(cat_uuid))
                click.echo("The Value UUID is : {}\n".format(value_uuid))

            except Exception as F:
                click.echo(F)
        else:
            click.echo("Your Child Tag doesn't exist.")


def tag_by_ip(ip_list, tag_list, c, v, d):
    # Tagging by IP is limited to 2000 Assets and is only used by the file command
    try:
        payload = {"category_name": str(c), "value": str(v), "description": str(d), "filters":
                   {"asset": {"and": [{"field": "ipv4", "operator": "eq", "value": str(ip_list[1:])}]}}}
        data = request_data('POST', '/tags/values', payload=payload)
        try:
            value_uuid = data["uuid"]
            cat_uuid = data['category_uuid']
            click.echo("\nI've created your new Tag - {} : {}\n".format(c, v))
            click.echo("The Category UUID is : {}\n".format(cat_uuid))
            click.echo("The Value UUID is : {}\n".format(value_uuid))
            click.echo("{} IPs added to the Tag".format(str(len(tag_list))))
        except Exception as E:
            click.echo("Duplicate Tag Category: You may need to delete your tag first\n")
            click.echo("We could not confirm your tag name, is it named weird?\n")
            click.echo(E)
    except:
        click.echo("Duplicate Category")


def tag_by_tenable_uuid(tag_list, c, v, d):
    # Tagging by Tenable UUID is limited to 500 UUIDS
    # Two problems here.  One: There is no PUT equivalant to chunk tenable UUIDs into groups of 500
    # two: the UUID returned from the agent endpoints is not the one needed to add a tag to the asset.
    try:
        payload = {"category_name": str(c), "value": str(v), "description": str(d), "filters":
                   {"asset": {"and": [{"field": "tenable_uuid", "operator": "eq", "value": str(tag_list[1:])}]}}}
        data = request_data('POST', '/tags/values', payload=payload)
        try:
            value_uuid = data["uuid"]
            cat_uuid = data['category_uuid']
            click.echo("\nI've created your new Tag - {} : {}\n".format(c, v))
            click.echo("The Category UUID is : {}\n".format(cat_uuid))
            click.echo("The Value UUID is : {}\n".format(value_uuid))
        except Exception as E:
            click.echo("Duplicate Tag Category: You may need to delete your tag first\n")
            click.echo("We could not confirm your tag name, is it named weird?\n")
            click.echo(E)
    except:
        click.echo("Duplicate Category")


def tag_by_uuid(tag_list, c, v, d):

    # Generator to split IPs into 2000 IP chunks
    def chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    # We Want to bail if the result is 0 Assets
    if not tag_list:
        click.echo("\nYour tag resulted in 0 Assets, therefore the tag wasn't created\n")
        exit()
    else:
        # Before updating confirm if the tag exists
        answer = confirm_tag_exists(c, v)

        # If the Tag does exist, update it by UUID.
        if answer == 'yes':
            # Check to see if the List of UUIDs is over 1999 (API Limit)
            if len(tag_list) > 1999:
                # break the list into 2000 IP chunks
                for chunks in chunks(tag_list, 1999):
                    update_tag(c, v, chunks)
            else:
                # If the Chunk is less than 2000, simply update it.
                update_tag(c, v, tag_list)
        # If the tag doesn't exist. we need to create one.
        else:
            # Create the Tag
            payload = {"category_name": str(c), "value": str(v), "description": str(d)}
            data = request_data('POST', '/tags/values', payload=payload)
            value_uuid = data["uuid"]
            cat_uuid = data['category_uuid']
            click.echo("\nI've created your new Tag - {} : {}\n".format(c, v))
            click.echo("The Category UUID is : {}\n".format(cat_uuid))
            click.echo("The Value UUID is : {}\n".format(value_uuid))

            # Check to see if the List of UUIDs is over 1999 (API Limit)
            if len(tag_list) > 1999:
                try:
                    click.echo("Your Tag list was over 2000 IPs.  Splitting the UUIDs into chunks and updating the tags now")
                    # Break the UUIDs into Chunks and update the tag per chunk
                    for chunks in chunks(tag_list, 1999):
                        update_tag(c, v, chunks)

                except Exception as E:
                    click.echo("An Error Occurred: \n")
                    click.echo(E)
            else:
                try:
                    update_tag(c, v, tag_list)
                except Exception as E:
                    click.echo("An Error Occurred: \n")
                    click.echo(E)


def download_csv_by_plugin_id(scan_id):
    filename = f'{scan_id}-report.csv'
    tio = tenb_connection()

    # Stream the report to disk
    with open(filename, 'wb') as fobj:
        tio.scans.export(scan_id, ('plugin.id', 'eq', '19506'),
                         format='csv', fobj=fobj)
    return filename


def create_uuid_list(filename):
    from csv import DictReader
    uuids = []
    with open(filename) as fobj:
        for row in DictReader(fobj):
            asset_uuid = row['Asset UUID']
            if asset_uuid and asset_uuid != '':
                uuids.append(asset_uuid)
    return uuids


@click.command(help="Create a Tag Category/Value Pair")
@click.option('--c', default='', help="Create a Tag with the following Category name")
@click.option('--v', default='', help="Create a Tag Value; requires --c and Category Name or UUID")
@click.option('--d', default='This Tag was created/updated by navi', help="Description for your Tag")
@click.option('--plugin', default='', help="Create a tag by plugin ID")
@click.option('--name', default='', help="Create a Tag by the text found in the Plugin Name")
@click.option('--group', default='', help="Create a Tag based on a Agent Group - BY Tenable UUID Due To API Limit(500 Agents)")
@click.option('--output', default='', help="Create a Tag based on the text in the output. Requires --plugin")
@click.option('--port', default='', help="Create a Tag based on Assets that have a port open.")
@click.option('--file', default='', help="Create a Tag based on IPs in a CSV file.")
@click.option('--scantime', default='', help="Create a Tag for assets that took longer than supplied minutes")
@click.option('--cc', default='', help="Add a Tag to a new parent tag: Child Category")
@click.option('--cv', default='', help="Add a Tag to a new parent tag: Child Value")
@click.option('--scanid', default='', help="Create a tag by Scan ID")
@click.option('--pipe', default='', help="Create a Tag based on a pipe from a 'navi find query -pipe' command")
def tag(c, v, d, plugin, name, group, output, port, scantime, file, cc, cv, scanid, pipe):
    # start a blank list
    tag_list = []
    ip_list = ""

    if c == '':
        click.echo("Category is required.  Please use the --c command")
        exit()

    if v == '':
        click.echo("Value is required. Please use the --v command")
        exit()

    if output != '' and plugin == '':
        click.echo("You must supply a plugin")
        exit()

    if plugin:
        try:
            database = r"navi.db"
            conn = new_db_connection(database)
            with conn:
                cur = conn.cursor()
                # See if we want to refine our search by the output found in this plugin
                # this needs to have a JOIN statement to reduce the amount
                if output != "":
                    cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_id='" + plugin + "' and output LIKE '%" + output + "%';")
                else:
                    cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_id=%s;" % plugin)

                plugin_data = cur.fetchall()
                for x in plugin_data:
                    ip = x[0]
                    uuid = x[1]
                    # To reduce duplicates check for the UUID in the list.
                    if uuid not in tag_list:
                        tag_list.append(uuid)
                        ip_list = ip_list + "," + ip
                    else:
                        pass
        except Error:
            pass

        tag_by_uuid(tag_list, c, v, d)

    if port != '':
        database = r"navi.db"
        conn = new_db_connection(database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT asset_uuid from vulns where port=" + port + " and (plugin_id='11219' or plugin_id='14272' or plugin_id='14274' or plugin_id='34220' or plugin_id='10335');")

            data = cur.fetchall()

            try:
                for vulns in data:
                    uuid = vulns[0]
                    # To reduce duplicates check for the UUID in the list.
                    if uuid not in tag_list:
                        tag_list.append(uuid)
            except ValueError:
                pass
        tag_by_uuid(tag_list, c, v, d)

    if name != '':
        try:
            database = r"navi.db"
            conn = new_db_connection(database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_name LIKE '%" + name + "%';")

                plugin_data = cur.fetchall()
                for x in plugin_data:
                    ip = x[0]
                    uuid = x[1]
                    if uuid not in tag_list:
                        tag_list.append(uuid)
                        ip_list = ip_list + "," + ip
                    else:
                        pass
        except Error:
            pass

        tag_by_uuid(tag_list, c, v, d)

    if group != '':
        tags_by_commas = ''
        from uuid import UUID
        ip_update = 1
        click.echo("\nDue to a API bug, I'm going to delete the current tag. You may get a 404 error if this is a new tag.")
        # Updating tags is only allowed via tenable ID(UUID); However you can't grab the UUID from the Agent URI
        # Need to research a better solution for this problem.  Need to submit a bug.  Going to just delete the tag for now.
        uuid_to_delete = return_tag_uuid(c, v)
        request_no_response('DELETE', '/tags/values/' + str(uuid_to_delete))
        try:
            querystring = {"limit": "5000"}
            group_data = request_data('GET', '/scanners/1/agent-groups')
            for agent_group in group_data['groups']:
                group_name = agent_group['name']
                group_id = agent_group['id']

                if group_name == group:
                    data = request_data('GET', '/scanners/1/agent-groups/' + str(group_id) + '/agents', params=querystring)
                    ip_list = ''
                    for agent in data['agents']:
                        ip_address = agent['ip']
                        uuid = agent['uuid']
                        new_uuid = UUID(uuid).hex
                        ip_list = ip_list + "," + ip_address
                        tags_by_commas = tags_by_commas + "," + new_uuid
                        tag_list.append(new_uuid)
        except Error:
            click.echo("You might not have agent groups, or you are using Nessus Manager.  ")

        tag_by_tenable_uuid(tags_by_commas, c, v, d)

    if scantime != '':
        database = r"navi.db"
        conn = new_db_connection(database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_id='19506';")

            data = cur.fetchall()
            try:
                for vulns in data:

                    output = vulns[2]

                    # split the output by return
                    parsed_output = output.split("\n")

                    # grab the length so we can grab the seconds
                    length = len(parsed_output)

                    # grab the scan duration- second to the last variable
                    duration = parsed_output[length - 2]

                    # Split at the colon to grab the numerical value
                    seconds = duration.split(" : ")

                    # split to remove "secs"
                    number = seconds[1].split(" ")

                    # grab the number for our minute calculation
                    final_number = number[0]

                    # convert seconds into minutes
                    minutes = int(final_number) / 60

                    # grab assets that match the criteria
                    if minutes > int(scantime):
                        try:
                            ip_list = ip_list + "," + str(vulns[0])
                            tag_list.append(vulns[1])
                        except ValueError:
                            pass
                click.echo()
            except ValueError:
                pass

        tag_by_uuid(tag_list, c, v, d)

    if file != '':
        with open(file, 'r', newline='') as new_file:
            add_ips = csv.reader(new_file)

            for row in add_ips:
                for ips in row:
                    # need to look grab UUIDS per IP for the ablity to update Tags
                    tag_list.append(ips)
                    ip_list = ip_list + "," + ips

        tag_by_ip(ip_list, tag_list, c, v, d)

    if cv != '' and cc != '':
        tag_by_tag(c, v, d, cv, cc)

    if scanid:
        tag_list = []
        try:
            scandata = request_data('GET', '/scans/' + str(scanid))
            try:
                for host in scandata['hosts']:
                    tag_list.append(host['uuid'])

                if len(tag_list) >= 4999:

                    click.echo("\nYou're scan is 5000 IPs or More. Downloading, Parsing and Cleaning up scans to ensure all assets are tagged\n")
                    click.echo("\nTags can take a few minutes to populate in the UI when applied to 1000s of assets\n")
                    filename = download_csv_by_plugin_id(scanid)
                    tag_list = create_uuid_list(filename)
                    tag_by_uuid(tag_list, c, v, d)

                    import os
                    os.remove(filename)
                else:
                    tag_by_uuid(tag_list, c, v, d)
            except TypeError:
                click.echo("Check the scan ID")
            except KeyError:
                click.echo("The scan used is archived, canceled, imported or aborted. Your Tag was not created.")

        except Exception as E:
            click.echo("Check your Scan ID; An Error occurred\n{}".format(E))

    if pipe:
        tag_by_uuid(eval(pipe), c, v, d)
