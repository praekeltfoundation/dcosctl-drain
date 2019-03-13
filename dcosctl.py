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


class ScheduleError(RuntimeError):
    pass


def cordon(mesos_url, machine_id, duration):
    # Check if the node is in draining mode. If it is, it must already be
    # scheduled, in which case Mesos won't allow us to schedule it again. Give
    # up.
    if _is_draining(mesos_url, machine_id):
        raise ScheduleError("Machine is already in draining mode, cannot add "
                            "to maintenance schedule more than once")

    # Get the existing maintenance schedule...
    schedule = _request("GET", mesos_url, "maintenance/schedule").json()

    windows = schedule.setdefault("windows", [])
    for window in windows:
        if machine_id in window["machine_ids"]:
            raise ScheduleError(
                "Machine already scheduled in a maintenance window, cannot "
                "schedule again")

    # Modify the windows in-place, appending the new node
    windows.append({
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
        raise ScheduleError(
            "No scheduled maintenance windows, nothing to 'uncordon'")

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
        raise ScheduleError("Hostname not found in existing maintenance "
                            "windows, nothing to 'uncordon'")

    new_schedule = {"windows": new_windows}
    _request("POST", mesos_url, "maintenance/schedule", json=new_schedule)


def drain(mesos_url, machine_id):
    _request("POST", mesos_url, "machine/down", json=[machine_id])


def up(mesos_url, machine_id):
    _request("POST", mesos_url, "machine/up", json=[machine_id])


def _add_machine_args(parser):
    parser.add_argument("ip", help="IP of the node")
    parser.add_argument(
        "--hostname", help="Hostname of the node (if different from IP)")


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(
        ("Commands for working with the Mesos maintenance API for old "
         "versions of DC/OS"))
    parser.add_argument("--mesos-url", default="http://localhost:5050",
                        help="URL for the Mesos master")
    subparsers = parser.add_subparsers(help='sub-command help')

    cordon_parser = subparsers.add_parser(
        "cordon", help="'Cordon' a node: schedule it for maintenance")
    _add_machine_args(cordon_parser)
    cordon_parser.set_defaults(func=cordon)
    cordon_parser.add_argument(
        "--duration", type=float, default=3600.0,
        help=("Number of seconds to put the node into maintenance mode "
              "(starting from now)"))

    uncordon_parser = subparsers.add_parser(
        "uncordon",
        help="'Uncordon' a node: remove it from the maintenance schedule")
    _add_machine_args(uncordon_parser)
    uncordon_parser.set_defaults(func=uncordon)

    drain_parser = subparsers.add_parser(
        "drain", help="'Drain' a node: mark the machine as down")
    _add_machine_args(drain_parser)
    drain_parser.set_defaults(func=drain)

    up_parser = subparsers.add_parser(
        "up", help="Mark a node as up: the opposite of drain")
    _add_machine_args(up_parser)
    up_parser.set_defaults(func=up)

    args = parser.parse_args(argv)

    hostname = args.hostname if args.hostname else args.ip
    machine_id = {"ip": args.ip, "hostname": hostname}

    try:
        if args.func == cordon:
            args.func(args.mesos_url, machine_id, args.duration)
        else:
            args.func(args.mesos_url, machine_id)
    except ScheduleError as e:
        # Convert these more informational errors into messages rather than big
        # stacktraces.
        _log("ERROR: {}".format(str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
