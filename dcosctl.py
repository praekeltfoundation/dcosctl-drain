#!/usr/bin/env python3
import argparse
import sys
import time

import requests


def _request(method, mesos_url, path, **kwargs):
    url = "{}/{}".format(mesos_url, path)
    response = requests.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def _ns_time(seconds):
    return {"nanoseconds": int(seconds * 10**9)}


def _log(msg):
    print(msg)


def _is_draining(mesos_url, machine_id):
    # http://mesos.apache.org/documentation/latest/maintenance/#draining-mode
    status = _request("GET", mesos_url, "maintenance/status").json()
    draining_machines = status.get("draining_machines", [])
    for machine in draining_machines:
        if machine.get("id") == machine_id:
            return True

    return False


def cordon(mesos_url, machine_id, duration):
    # Check if the node is in draining mode. If it is, it must already be
    # scheduled, in which case Mesos won't allow us to schedule it again. Give
    # up.
    if _is_draining(mesos_url, machine_id):
        _log("WARN: Machine is already in draining mode, cannot add to "
             "maintenance schedule more than once")
        return

    # Get the existing maintenance schedule...
    schedule = _request("GET", mesos_url, "maintenance/schedule").json()

    # Modify the windows in-place, appending the new node
    schedule.setdefault("windows", []).append({
        "machine_ids": [machine_id],
        "unavailability": {
            "duration": _ns_time(duration),
            "start": _ns_time(time.time())
        }
    })

    # ...send the updated schedule back
    _request("POST", mesos_url, "maintenance/schedule", json=schedule)


def uncordon(mesos_url, machine_id):
    # Check if the node is in draining mode. Our 'uncordon' process doesn't
    # care whether or not this is the case, but it may be useful information
    # for the user.
    if not _is_draining(mesos_url, machine_id):
        _log("WARN: Machine was not in draining mode, attempting to remove "
             "from maintenance schedule anyway...")


    # Get the existing maintenance schedule...
    schedule = _request("GET", mesos_url, "maintenance/schedule").json()

    windows = schedule.get("windows")
    if not windows:
        _log("WARN: No scheduled maintenance windows, nothing to 'uncordon'")
        return

    # Remove all references to the host, cleaning up as we go
    new_windows = []
    scheduled = False
    for window in windows:
        machine_ids = window["machine_ids"]
        new_machine_ids = [mid for mid in machine_ids if mid != machine_id]

        # Very lazy, but probably fine given that Python should just check the
        # lengths of the lists rather than doing a full comparison
        if new_machine_ids != machine_ids:
            scheduled = True

        # Skip windows with no remaining machine IDs
        if new_machine_ids:
            new_window = dict(window)
            new_window["machine_ids"] = new_machine_ids
            new_windows.append(new_window)

    if not scheduled:
        _log("WARN: Hostname not found in existing maintenance windows, "
             "nothing to 'uncordon'")
        return

    new_schedule = {"windows": new_windows}
    _request("POST", mesos_url, "maintenance/schedule", json=new_schedule)


def drain(mesos_url, machine_id):
    _request("POST", mesos_url, "machine/down", json=[machine_id])


def up(mesos_url, machine_id):
    _request("POST", mesos_url, "machine/up", json=[machine_id])


def _add_hostname_arg(parser):
    parser.add_argument("hostname", help="Hostname of node")


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        ("Commands for working with the Mesos maintenance API for old "
         "versions of DC/OS"))
    parser.add_argument("--mesos-url", default="http://localhost:5050",
                        help="URL for the Mesos master")
    subparsers = parser.add_subparsers(help='sub-command help')

    cordon_parser = subparsers.add_parser(
        "cordon", help="'Cordon' a node: schedule it for maintenance")
    _add_hostname_arg(cordon_parser)
    cordon_parser.set_defaults(func=cordon)
    cordon_parser.add_argument(
        "--duration", type=float, default=3600.0,
        help=("Number of seconds to put the node into maintenance mode "
              "(starting from now)"))

    uncordon_parser = subparsers.add_parser(
        "uncordon",
        help="'Uncordon' a node: remove it from the maintenance schedule")
    _add_hostname_arg(uncordon_parser)
    uncordon_parser.set_defaults(func=uncordon)

    drain_parser = subparsers.add_parser(
        "drain", help="'Drain' a node: mark the machine as down")
    _add_hostname_arg(drain_parser)
    drain_parser.set_defaults(func=drain)

    up_parser = subparsers.add_parser(
        "up", help="Mark a node as up: the opposite of drain")
    _add_hostname_arg(up_parser)
    up_parser.set_defaults(func=up)

    args = parser.parse_args(argv)

    machine_id = {"hostname": args.hostname, "ip": args.hostname}
    if args.func == cordon:
        args.func(args.mesos_url, machine_id, args.duration)
    else:
        args.func(args.mesos_url, machine_id)


if __name__ == "__main__":
    main()
