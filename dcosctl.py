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


def cordon(args):
    # Get the existing maintenance schedule...
    schedule = _request("GET", args.mesos_url, "maintenance/schedule").json()

    # Modify the windows in-place, appending the new node
    schedule.setdefault("windows", []).append({
        "machine_ids": [
            {
                "hostname": args.hostname,
                "ip": args.hostname
            }
        ],
        "unavailability": {
            "duration": _ns_time(args.duration),
            "start": _ns_time(time.time())
        }
    })

    # ...send the updated schedule back
    _request("POST", args.mesos_url, "maintenance/schedule", json=schedule)


def uncordon(args):
    # Get the existing maintenance schedule...
    schedule = _request("GET", args.mesos_url, "maintenance/schedule").json()

    windows = schedule.get("windows")
    if not windows:
        _log("WARN: No scheduled maintenance windows, nothing to 'uncordon'")
        return

    # Remove all references to the host, cleaning up as we go
    new_windows = []
    for window in windows:
        machine_ids = [mid for mid in window["machine_ids"]
                       if mid["hostname"] != args.hostname]

        # Skip windows with no remaining machine IDs
        if machine_ids:
            new_window = dict(window)
            new_window["machine_ids"] = machine_ids
            new_windows.append(new_window)

    new_schedule = {"windows": new_windows}
    _request("POST", args.mesos_url, "maintenance/schedule", json=new_schedule)


def drain(args):
    _request("POST", args.mesos_url, "machine/down", json=[
        {"hostname": args.hostname, "ip": args.hostname}
    ])


def up(args):
    _request("POST", args.mesos_url, "machine/up", json=[
        {"hostname": args.hostname, "ip": args.hostname}
    ])


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
    args.func(args)


if __name__ == "__main__":
    main()
