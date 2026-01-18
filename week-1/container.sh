#!/bin/bash

# containers aren't magic
# These 15 lines of bash will start a container running the fish shell.
# It only runs on Linux because these features are all Linux-only.

wget bit.ly/fish-container -O fish.tar           # 1. download the image
mkdir container-root; cd container-root
tar -xf ../fish.tar                              # 2. unpack image into a directory
cgroup_id="cgroup_$(shuf -i 1000-2000 -n 1)"     # 3. generate random cgroup name
cgcreate -g "cpu,cpuacct,memory:$cgroup_id"      # 4. make a cgroup &
cgset -r cpu.shares=512 "$cgroup_id"             #    set CPU/memory limits
cgset -r memory.limit_in_bytes=1000000000 \
    "$cgroup_id"
cgexec -g "cpu,cpuacct,memory:$cgroup_id" \      # 5. use the cgroup
    unshare -fmuipn --mount-proc \               # 6. make + use some namespaces
    chroot "$PWD" \                              # 7. change root directory
    /bin/sh -c "
        /bin/mount -t proc proc /proc &&         # 8. use the right /proc
        hostname container-fun-times &&          # 9. change the hostname
        /usr/bin/fish"                           # 10. finally, start fish!