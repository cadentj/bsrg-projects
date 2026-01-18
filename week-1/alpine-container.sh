#!/bin/bash

# containers aren't magic
# This script starts a container running the fish shell on Alpine Linux.

# Clean up previous runs
rm -rf container-root fish.tar

# 1. Download the image
wget bit.ly/fish-container -O fish.tar

# 2. Unpack image into a directory
mkdir container-root && cd container-root
tar -xf ../fish.tar

# 3. Generate random cgroup name
cgroup_id="cgroup_$(shuf -i 1000-2000 -n 1)"

# 4. Create cgroups manually (Alpine doesn't have cgroup-tools working properly)
mkdir /sys/fs/cgroup/cpu/$cgroup_id
mkdir /sys/fs/cgroup/cpuacct/$cgroup_id
mkdir /sys/fs/cgroup/memory/$cgroup_id

# 5. Set CPU/memory limits
echo 512 > /sys/fs/cgroup/cpu/$cgroup_id/cpu.shares
echo 1000000000 > /sys/fs/cgroup/memory/$cgroup_id/memory.limit_in_bytes

# 6. Add current shell to cgroups (so everything it spawns inherits limits)
echo $$ > /sys/fs/cgroup/cpu/$cgroup_id/tasks
echo $$ > /sys/fs/cgroup/cpuacct/$cgroup_id/tasks
echo $$ > /sys/fs/cgroup/memory/$cgroup_id/tasks

# 7. Run the container:
#    - unshare: create new namespaces (PID, mount, network, etc.)
#    - chroot: change root filesystem to container-root
#    - mount proc: so ps/top work inside
#    - set hostname: demonstrate UTS namespace isolation
#    - TERM=xterm: fix terminal compatibility for fish
TERM=xterm unshare -fmuipn --mount-proc \
    chroot "$PWD" \
    /bin/sh -c "
        mount -t proc proc /proc &&
        hostname container-fun-times &&
        /usr/bin/fish"