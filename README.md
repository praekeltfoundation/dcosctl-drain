# dcosctl-drain
Python script for easier interaction with Mesos maintenance primitives

Provides `kubectl`-like (but definitely not equivalent) commands for taking
nodes out of a cluster.

**Note** that this script was designed for a very specific purpose, has no
tests, and is kept here purely for posterity.

Specifically designed for use with DC/OS 1.10 Community Edition. Some of this
functionality is present in recent versions of the `dcos` CLI, and more advanced
functionality is also available in recent versions of Mesos.

The script requires Requests and runs on Python 3. It can be installed as
`dcosctl` after `pip`-installing or run directly like `python dcosctl.py`.

## Explanation
The basic process for performing maintenance on a Mesos agent node is as
follows:
1. Define maintenance window for instance (`POST /maintenance/schedule`)
2. When maintenance window active, mark node as down (`POST /machine/down`)
3. Perform maintenance on node
4. Mark node as up (`POST /machine/up`)
5. Clear maintenance window for node (`POST /maintenance/schedule`)

The mapping of these requests to commands is:
* `POST /maintenance/schedule` (add to schedule) -> `dcosctl cordon`
* `POST /machine/down` -> `dcosctl drain`
* `POST /machine/up` -> `dcosctl up` (no real `kubectl` equivalent)
* `POST /maintenance/schedule` (remove from schedule) -> `dcosctl uncordon`

## Assumptions
* The Mesos agent `hostname == ip`.
* `dcosctl uncordon` simply removes a node from **all** maintenance windows in
  the schedule, whether it is in draining mode or not.
* The script needs cleartext/unauthed access to the Mesos master API.
