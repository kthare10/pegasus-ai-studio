#!/usr/bin/env python3
"""Create the FABRIC slice for the PegasusAI Studio Approach-B prototype.

Topology (single site, one L2 data network for the HTCondor pool):

    studio-cp    10.10.0.10   k3s server + JupyterHub + KubeSpawner pods   (public IPv4)
    condor-cm    10.10.0.20   collector + negotiator + CCB + shared_port
    condor-exec1 10.10.0.30   startd (job runner)
    [studio-w1]  10.10.0.11   optional k3s agent (more room for pods)
    [condor-exec2] 10.10.0.31 optional second execute node

The data plane is one L2 network with static private IPs — stable addresses are
what make CCB + shared_port deterministic. Each VM also has the default FABRIC
management interface (outbound Internet for apt/pip/docker pull/CILogon), and
studio-cp gets a routable public IPv4 (FABNetv4Ext) for the Studio/Hub UI.

Run from a FABRIC JupyterHub notebook or any host with fabric credentials.
Tune SITE / node sizes / WORKERS / EXTRA_EXEC at the top.
"""

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib

# ---- knobs ----------------------------------------------------------------
SLICE_NAME = "pegasusai-studio-approachB"
SITE = "STAR"                 # pick a site with capacity (STAR/WASH/MASS/...)
IMAGE = "default_ubuntu_24"   # noble — matches the :approach-b pod image (HTCondor 25.x)
SUBNET = "10.10.0.0/24"
WORKERS = 0                   # extra k3s agent nodes (0 or 1 for the prototype)
EXTRA_EXEC = 0                # extra execute nodes beyond condor-exec1

NODES = {
    "studio-cp":    dict(cores=16, ram=64, disk=200, ip="10.10.0.10", public=True),
    "condor-cm":    dict(cores=4,  ram=8,  disk=40,  ip="10.10.0.20"),
    "condor-exec1": dict(cores=32, ram=64, disk=300, ip="10.10.0.30"),
}
for i in range(WORKERS):
    NODES[f"studio-w{i+1}"] = dict(cores=16, ram=64, disk=200, ip=f"10.10.0.{11+i}")
for i in range(EXTRA_EXEC):
    NODES[f"condor-exec{i+2}"] = dict(cores=32, ram=64, disk=300, ip=f"10.10.0.{31+i}")


def main():
    f = fablib()
    f.show_config()
    slice = f.new_slice(name=SLICE_NAME)

    net = slice.add_l2network(name="poolnet", subnet=SUBNET)

    for name, spec in NODES.items():
        node = slice.add_node(
            name=name, site=SITE, cores=spec["cores"], ram=spec["ram"],
            disk=spec["disk"], image=IMAGE,
        )
        iface = node.add_component(model="NIC_Basic", name="poolnic").get_interfaces()[0]
        net.add_interface(iface)
        iface.set_mode("config")
        iface.set_ip_addr(spec["ip"])
        if spec.get("public"):
            # routable public IPv4 for the Studio/Hub ingress on the control node
            node.add_fabnet(net_type="IPv4Ext")

    slice.submit()
    print("\nSlice submitted. After it boots:")
    print("  1. On each node, set the pool NIC IP (fablib does this with set_ip_addr).")
    print("  2. provision-common.sh on condor-cm + condor-exec*; provision-cm.sh 10.10.0.20")
    print("     on the CM; copy /tmp/execute.token to each exec and run provision-exec.sh.")
    print("  3. provision-k3s.sh on studio-cp (+ agents) for M2+.")
    print("  See deploy/approach-b/fabric/README.md for the full runbook.")


if __name__ == "__main__":
    main()
